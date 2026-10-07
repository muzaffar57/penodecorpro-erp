#!/usr/bin/env python3
"""
test_taklif.py — kech126 (zip 148) darvozasi: «⚡ TEZ HISOB / 📝 TAKLIF» (EGASI QARORLARI 07.10 10:5x, QAYTA SO'RALMAYDI).

EGASINING MUAMMOSI: mijoz keladi, tezda hisoblab hujjat berish kerak — hozir avval loyiha, keyin buyurtma ochish shart.
QARORLAR: (1) taklif SAQLANADI («Takliflar» ro'yxati — mijoz ismi / telefoni bilan), «olaman» desa bitta tugma bilan loyiha va
buyurtma ochiladi, qayta yozilmaydi; (2) hujjat — «Buyurtma hisobi» ko'rinishida, sarlavha «TAKLIF (HISOB-KITOB)», pastida «Narxlar
3 kun amal qiladi»; (3) ombor TEGILMAYDI — taklifda faqat «omborda yetmaydi» ogohlantirishi; (4) taklifni «Buyurtmalar: Yaratish»
ruxsati borlar yozadi. Egasi savoliga javob (11:12): taklif avtomatik o'chirilmaydi — muddat o'tsa «muddati o'tgan», bekor — qo'lda.

BO'LIMLAR
  A — yaratish: raqam (korxona bo'yicha «T-0001»), muddat (+3 kun), jurnal; HISOB buyurtma bilan AYNAN — har detal turi (profil +
      ichki detal, panel, donali, blok, loy sotish, MRP mahsuloti, tayyor mahsulot), tiyinli narxlar, chegirma
  B — HECH NARSA yozilmaydi: buyurtma, loyiha, ombor qoldig'i, harakatlar, tayyor mahsulot, raqam hisoblagichlari, Moliya, Telegram;
      ogohlantirish tekshiruvi «Tayyor loy» pozitsiyasini yaratmaydi
  C — PDF: «TAKLIF (HISOB-KITOB)», «Narxlar 3 kun amal qiladi», raqam, mijoz, sana — taklif sanasi; jadval va summalar buyurtma
      hujjati bilan AYNAN; to'lov / qarz / imzo yo'q
  D — tekshiruvlar (400 / 422, hech narsa yozilmaydi, raqam band qilinmaydi): mijoz, telefon, bo'sh detal, tur, sig'im, loy,
      begona / yo'q havolalar (usta, retsept, penoplast, tayyor mahsulot, mahsulot turi)
  E — «omborda yetmaydi» ogohlantirishi (penoplast, tayyor mahsulot, loy) — `POST /api/orders` 409 ro'yxati bilan AYNAN
  F — ro'yxat: qidiruv (ism, telefon raqamlari, raqam), filtrlar va sonlar, muddati o'tgan, sahifalash
  G — tahrir (faqat «yangi»; muddat qayta +3 kun), H — bekor qilish (faqat qo'lda; keyin tahrir / rasmiylashtirish yo'q)
  I — rasmiylashtirish: yangi loyiha (ism / telefon taklifdan) + buyurtma — narxlar AYNAN, ombor oddiy buyurtmadek; mavjud loyiha;
      qoralama; yetishmovchilik 409 → HECH NARSA (yangi loyiha ham) → tasdiq bilan; ikki marta — 409; begona loyiha 404; loyiha
      ruxsatisiz yangi loyiha — 403; muddati o'tgan taklif ham
  J — korxona izolyatsiyasi; K — ruxsatlar (Admin, Menejer — ha; Moliyachi, Omborchi — yo'q; faqat ko'rish ruxsati)
  L — buyurtma butunlay o'chirilsa — bog'lam uziladi, raqam qoladi; M — zaxira (eksport / tiklash / tozalash)
  N — /orders sahifasi (tugmalar, son); P — PG parallel (raqam; bitta taklifni bir vaqtda ikki marta rasmiylashtirish); S — statik

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi (P bo'limi faqat PG da); `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 147) qarshi QULAMAYDI — yiqiladi (yangi nomlar `getattr`, HTTP istisno — 599).
    python3 tools/test_taklif.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_taklif.py
Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import re
import sys
import io
import json
import inspect
import tempfile
import threading
import subprocess
import contextlib
from datetime import datetime, timedelta

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "taklif_test"
_DB = os.path.join(tempfile.gettempdir(), "taklif_test.db")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    if os.path.exists(_DB):
        os.remove(_DB)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, services, models, schemas   # noqa: E402

from database import SessionLocal                  # noqa: E402
from production_models import Company, ProductType, ProductionOrder   # noqa: E402
from models import (                               # noqa: E402
    UserRole, User, Rol, Project, Order, OrderItem, Inventory, InventoryMovement, Recipe, RecipeIngredient, FinishedProduct,
    StockSource, ProductionStatus, ActivityLog, Payment, CashTransaction, Master,
)
from fastapi.testclient import TestClient          # noqa: E402

Taklif = getattr(models, "Taklif", None)           # asl kodda yo'q — test QULAMAYDI, tekshiruvlar yiqiladi

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF] " if os.environ.get("TENANT_FILTER") else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"
        self.content = b""
        self.headers = {}

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def xavfsiz(fn, standart=None):
    try:
        return fn()
    except Exception:                      # noqa: BLE001
        return standart


def teng(a, b, eps=0.005):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


def fayl(nom):
    try:
        return open(os.path.join(ROOT, nom), encoding="utf-8").read()
    except Exception:                      # noqa: BLE001
        return ""


def manba(obj, nom):
    try:
        return inspect.getsource(getattr(obj, nom))
    except Exception:                      # noqa: BLE001
        return ""


def pdf_matn(bayt):
    """PDF matni (qatorlar): pypdf, bo'lmasa poppler `pdftotext`; ikkalasi ham bo'lmasa — bo'sh (tekshiruv yiqiladi)."""
    try:
        import pypdf
        return "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(bayt)).pages)
    except Exception:                      # noqa: BLE001
        pass
    try:
        return subprocess.run(["pdftotext", "-layout", "-", "-"], input=bayt, capture_output=True, timeout=60).stdout.decode()
    except Exception:                      # noqa: BLE001
        return ""


def qatorlar(matn):
    return [q.strip() for q in (matn or "").splitlines() if q.strip()]


def jadval_qismi(matn):
    """Detallar jadvali va summa qatorlari: «Jami (so'm)» sarlavhasidan keyin «TO'LOV SUMMASI:» va uning qiymatigacha."""
    q = qatorlar(matn)
    try:
        i = q.index("Jami (so'm)")
        j = q.index("TO'LOV SUMMASI:")
        return q[i + 1:j + 2]
    except ValueError:
        return None


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (A, asosiy), 2-korxona (B, begona)
#   Penoplast: 1 blok (1 m³) = 1 000 000; loy retsepti R1: 100 kg = 50 kg Akril (10 000) + 50 kg Kley (20 000)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="TK Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "TK_admin", "Parol123!", UserRole.ADMIN, "TK Admin", company_id=1)
    auth.create_user(_db, "TK_admin_b", "Parol123!", UserRole.ADMIN, "TK Admin B", company_id=2)
    auth.create_user(_db, "TK_menejer", "Parol123!", UserRole.MANAGER, "TK Menejer", company_id=1)
    auth.create_user(_db, "TK_moliya", "Parol123!", UserRole.ACCOUNTANT, "TK Moliyachi", company_id=1)
    auth.create_user(_db, "TK_ombor", "Parol123!", UserRole.WAREHOUSE, "TK Omborchi", company_id=1)
    auth.create_user(_db, "TK_buyurtmachi", "Parol123!", UserRole.MANAGER, "TK Buyurtmachi", company_id=1)
    auth.create_user(_db, "TK_koruvchi", "Parol123!", UserRole.MANAGER, "TK Ko'ruvchi", company_id=1)
# «Buyurtmalar: Ko'rish + Yaratish» (loyiha YARATISH yo'q) va «Buyurtmalar: Ko'rish» — maxsus rollar
_r_buy = Rol(company_id=1, nom="TK faqat buyurtma", ruxsatlar=json.dumps({"buyurtma": ["korish", "yaratish"], "loyiha": ["korish"]}))
_r_kor = Rol(company_id=1, nom="TK faqat ko'rish", ruxsatlar=json.dumps({"buyurtma": ["korish"]}))
_db.add_all([_r_buy, _r_kor])
_db.commit()
_db.query(User).filter(User.username == "TK_buyurtmachi").update({"rol_id": _r_buy.id})
_db.query(User).filter(User.username == "TK_koruvchi").update({"rol_id": _r_kor.id})
PRJ = Project(company_id=1, project_number="PRJ-001", client_name="TK Eski Mijoz", project_name="TK eski loyiha", total_budget=0,
              total_paid=0)
# nazorat buyurtmasi uchun alohida loyiha: bir loyihada 8 s ichida AYNAN shu tarkibli buyurtma «takroriy yuborish» deb qaytariladi
PRJ_K = Project(company_id=1, project_number="PRJ-002", client_name="TK Nazorat", project_name="TK nazorat loyihasi", total_budget=0,
                total_paid=0)
PENO = Inventory(company_id=1, item_name="TK Penoplast 14P", unit="blok", stock_quantity=1000, price_per_unit=1_000_000,
                 volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
PENO_KAM = Inventory(company_id=1, item_name="TK Penoplast 25P (kam)", unit="blok", stock_quantity=0.05, price_per_unit=1_500_000,
                     volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
AKR = Inventory(company_id=1, item_name="TK Akril", unit="kg", stock_quantity=10_000, price_per_unit=10_000, category="Kimyo")
KLEY = Inventory(company_id=1, item_name="TK Kley", unit="kg", stock_quantity=10_000, price_per_unit=20_000, category="Kimyo")
QUM = Inventory(company_id=1, item_name="TK Kvars qumi", unit="kg", stock_quantity=1, price_per_unit=1_000, category="Boshqa")
PENO_B = Inventory(company_id=2, item_name="TK B Penoplast", unit="blok", stock_quantity=100, price_per_unit=400_000,
                   volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
PRJ_B = Project(company_id=2, project_number="PRJ-001", client_name="TK B Mijoz", project_name="TK B loyiha", total_budget=0,
                total_paid=0)
USTA = Master(company_id=1, name="TK Usta", phone="+998901234567")
USTA_B = Master(company_id=2, name="TK B Usta", phone="+998901234568")
PT = ProductType(company_id=1, name="TK Travertin", unit="dona", input_template="quantity_only", pricing_formula="unit_based")
PT_B = ProductType(company_id=2, name="TK B tur", unit="dona", input_template="quantity_only", pricing_formula="unit_based")
_db.add_all([PRJ, PRJ_K, PENO, PENO_KAM, AKR, KLEY, QUM, PENO_B, PRJ_B, USTA, USTA_B, PT, PT_B])
_db.commit()
R1 = Recipe(company_id=1, name="TK loy", batch_size_kg=100.0)
R2 = Recipe(company_id=1, name="TK qumli loy", batch_size_kg=100.0)
R_B = Recipe(company_id=2, name="TK B loy", batch_size_kg=100.0)
_db.add_all([R1, R2, R_B])
_db.commit()
_db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=AKR.id, quantity_kg=50.0),
             RecipeIngredient(recipe_id=R1.id, inventory_id=KLEY.id, quantity_kg=50.0),
             RecipeIngredient(recipe_id=R2.id, inventory_id=QUM.id, quantity_kg=100.0)])
FP = FinishedProduct(company_id=1, name="TK Tayyor karniz", category="profil", is_coated=False, quantity=50, produced_quantity=50,
                     unit="metr", unit_price=20_000, cost_price=500_000, source=StockSource.PRODUCED, penoplast_id=PENO.id,
                     production_status=ProductionStatus.READY)
FP_B = FinishedProduct(company_id=2, name="TK B tayyor", category="profil", is_coated=False, quantity=10, produced_quantity=10,
                       unit="metr", unit_price=20_000, cost_price=100_000, source=StockSource.PRODUCED, penoplast_id=PENO_B.id,
                       production_status=ProductionStatus.READY)
_db.add_all([FP, FP_B])
_db.commit()
ID = dict(prj=PRJ.id, prj_k=PRJ_K.id, peno=PENO.id, peno_kam=PENO_KAM.id, akr=AKR.id, kley=KLEY.id, qum=QUM.id, peno_b=PENO_B.id,
          prj_b=PRJ_B.id, usta=USTA.id, usta_b=USTA_B.id, pt=PT.id, pt_b=PT_B.id, r1=R1.id, r2=R2.id, r_b=R_B.id,
          fp=FP.id, fp_b=FP_B.id)
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


C, _s1 = _kir("TK_admin")
CB, _s2 = _kir("TK_admin_b")
CN, _s3 = _kir("TK_menejer")
CF, _s4 = _kir("TK_moliya")
CW, _s5 = _kir("TK_ombor")
CBY, _s6 = _kir("TK_buyurtmachi")
CKR, _s7 = _kir("TK_koruvchi")
if (_s1, _s2, _s3, _s4, _s5, _s6, _s7) != (302,) * 7:
    print(f"LOGIN BO'LMADI: {(_s1, _s2, _s3, _s4, _s5, _s6, _s7)}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

# Telegram — HAQIQIY yuborilmaydi, sanaladi (taklif hech narsa yubormasligi kerak)
TG = []
for _nom in ("_send_telegram", "_send_telegram_to", "_send_telegram_document", "_send_telegram_to_qoplamachi"):
    if hasattr(main, _nom):
        setattr(main, _nom, (lambda n: (lambda *a, **k: TG.append((n, a[:1]))))(_nom))

_BUGUN = (datetime.utcnow() + timedelta(hours=5)).date()          # noqa: DTZ003 — Toshkent sanasi (server kabi)
YIL, OY = _BUGUN.year, _BUGUN.month


def tana_toliq(**qosh):
    """Har detal turi bor buyurtma tanasi (loyihasiz): profil (qoplamali, ichki detal bilan), panel (tiyinli narx), donali,
    blok, loy sotish, MRP mahsuloti, tayyor mahsulot. Loy rejasi 3 kg — retsept R1."""
    t = {"order_type": "product", "recipe_id": ID["r1"], "master_id": ID["usta"], "base_price": 1_200_000, "loy_kg": 3,
         "deadline": f"{(_BUGUN + timedelta(days=10)).isoformat()}T00:00:00", "items": [
             {"name": "TK Karniz 20x10", "category": "profil", "width": 20, "thickness": 10, "length": 7, "quantity": 1,
              "unit_price": 168_000.004, "is_coated": True, "penoplast_id": ID["peno"],
              "sub_details": [{"name": "Rebristo", "category": "profil", "width": 5, "thickness": 5, "length": 7, "quantity": 1,
                               "is_coated": False}]},
             {"name": "TK Panel 30x5", "category": "panel", "width": 30, "thickness": 5, "quantity": 333, "unit_price": 10.335,
              "is_coated": False, "penoplast_id": ID["peno"]},
             {"name": "TK Kafel dona", "category": "dona", "width": 10, "thickness": 10, "length": 1, "quantity": 7,
              "unit_price": 0.125, "unit_price_for_volume": 1000, "price_per_m3": 1_200_000, "is_coated": False,
              "penoplast_id": ID["peno"], "notes": "dona_yield=4"},
             {"name": "TK Blok kesma", "category": "blok", "quantity": 12.5, "unit_price": 10_000, "is_coated": False,
              "penoplast_id": ID["peno"], "notes": "blok_narxi=400000,blok_yield=40"},
             {"name": "TK Loy 25 kg", "category": "loy_sotish", "quantity": 25, "unit_price": 15_000, "recipe_id": ID["r1"],
              "is_coated": False},
             {"name": "TK Travertin plita", "category": "mrp_product", "quantity": 3, "unit_price": 45_000.5,
              "product_type_id": ID["pt"], "is_coated": False},
             {"name": "TK Tayyor karniz 2 m", "category": "profil", "width": 20, "thickness": 10, "length": 2, "quantity": 1,
              "unit_price": 40_000, "finished_product_id": ID["fp"], "penoplast_id": ID["peno"], "is_coated": False},
         ]}
    t.update(qosh)
    return t


def tana_oddiy(nom="TK Oddiy karniz", uzunlik=10, narx=120_000, peno=None, **qosh):
    t = {"order_type": "product", "items": [
        {"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": uzunlik, "quantity": 1, "unit_price": narx,
         "is_coated": False, "penoplast_id": peno or ID["peno"]}]}
    t.update(qosh)
    return t


def taklif(c=None, mijoz="Ali Valiyev", telefon="+998 90 111 22 33", buyurtma=None):
    r = req(c or C, "post", "/api/takliflar", json={"mijoz": mijoz, "telefon": telefon, "buyurtma": buyurtma or tana_oddiy()})
    d = js(r) or {}
    t = d.get("taklif") if isinstance(d, dict) else None
    return r, (t or {}), (d.get("ogohlantirishlar") if isinstance(d, dict) else None)


def tk_db(tid):
    if Taklif is None or not tid:
        return None
    s = SessionLocal()
    try:
        return s.get(Taklif, tid)
    finally:
        s.close()


def tka(tid, maydon):
    """Taklif maydoni (taklif yo'q / asl kod — None; test QULAMAYDI)."""
    return getattr(tk_db(tid), maydon, None)


def tk_max(cid):
    """Korxonadagi eng katta taklif tartib raqami (yo'q — 0)."""
    if Taklif is None:
        return -1
    s = SessionLocal()
    try:
        return max([0] + [t.seq for t in s.query(Taklif).filter(Taklif.company_id == cid).all()])
    finally:
        s.close()


def tk_soni(cid=None):
    if Taklif is None:
        return -1
    s = SessionLocal()
    try:
        q = s.query(Taklif)
        if cid is not None:
            q = q.filter(Taklif.company_id == cid)
        return q.count()
    finally:
        s.close()


def holat():
    """Taklif tegmasligi kerak bo'lgan hamma narsa: buyurtma / detal / loyiha / harakat / to'lov / kassa / ishlab chiqarish soni,
    har material qoldig'i, tayyor mahsulot qoldig'i va bandi, loyiha / buyurtma raqam hisoblagichlari."""
    s = SessionLocal()
    try:
        r = {}
        for nom, M in (("orders", Order), ("order_items", OrderItem), ("projects", Project), ("movements", InventoryMovement),
                       ("payments", Payment), ("cash", CashTransaction), ("po", ProductionOrder), ("inventory", Inventory),
                       ("fp", FinishedProduct)):
            r[nom] = s.query(M).count()
        r["stock"] = sorted((i.id, round(float(i.stock_quantity or 0), 6)) for i in s.query(Inventory).all())
        r["fpq"] = sorted((f.id, round(float(f.quantity or 0), 6), round(float(f.reserved_quantity or 0), 6))
                          for f in s.query(FinishedProduct).all())
        r["loy_seq"] = sorted((c.id, c.oxirgi_loyiha_seq) for c in s.query(Company).all())
        r["buy_seq"] = sorted((p.id, p.oxirgi_buyurtma_seq) for p in s.query(Project).all())
        return r
    finally:
        s.close()


def oylik():
    s = SessionLocal()
    try:
        return json.dumps(services.get_monthly_report(s, YIL, OY, company_id=1), sort_keys=True, default=str)
    except Exception as e:                 # noqa: BLE001
        return f"XATO {type(e).__name__}: {e}"
    finally:
        s.close()


def faoliyat(amal, eid=None):
    s = SessionLocal()
    try:
        q = s.query(ActivityLog).filter(ActivityLog.entity_type == "taklif", ActivityLog.action == amal)
        if eid is not None:
            q = q.filter(ActivityLog.entity_id == eid)
        return [(a.company_id, a.entity_label, a.old_value, a.new_value, a.performed_by) for a in q.order_by(ActivityLog.id).all()]
    finally:
        s.close()


# ══════════════════════════════════════════════════════════════
section("A. Yaratish — raqam, muddat, jurnal; hisob buyurtma bilan AYNAN (har detal turi)")
# ══════════════════════════════════════════════════════════════
rA, tA, ogA = taklif(mijoz="  Ali Valiyev ", telefon=" +998 90 111 22 33 ", buyurtma=tana_toliq(agreed_amount=350_000))
TA = tA.get("id")
check("A1 POST /api/takliflar — 200; raqam «T-0001», holat «yangi», mijoz / telefon (bo'shliqlar olib tashlangan)",
      rA.status_code == 200 and tA.get("raqam") == "T-0001" and tA.get("holat") == "yangi" and tA.get("mijoz") == "Ali Valiyev"
      and tA.get("telefon") == "+998 90 111 22 33" and tA.get("seq") == 1, (rA.status_code, rA.text[:400]))
check("A2 amal qilish muddati — Toshkent bugungi sanasi + 3 kun; muddati o'tmagan; yaratgan — foydalanuvchi to'liq ismi",
      tA.get("amal_muddati") == (_BUGUN + timedelta(days=3)).isoformat() and tA.get("muddati_otgan") is False
      and tA.get("yaratgan") == "TK Admin" and getattr(crud, "TAKLIF_MUDDAT_KUN", None) == 3, tA)
# Xuddi shu tana — oddiy buyurtma (loyiha bilan)
rO = req(C, "post", "/api/orders", params={"confirm_shortage": "true"}, json={**tana_toliq(agreed_amount=350_000), "project_id": ID["prj"]})
dO = js(rO) or {}
OID = dO.get("id") if isinstance(dO, dict) else None
dg = js(req(C, "get", f"/api/takliflar/{TA}")) or {}
_o = js(req(C, "get", f"/api/orders/{OID}")) if OID else {}
_o = _o or {}
check("A3 nazorat: o'sha tana bilan oddiy buyurtma — 200", rO.status_code == 200 and OID, (rO.status_code, rO.text[:300]))
_ti, _oi = (dg.get("items") or []), (_o.get("items") or [])
check("A4 HAR detal (7 tur): taklifdagi 1 birlik narxi va detal jami = buyurtmaga yozilgan qiymat (tiyin aniqligida)",
      len(_ti) == 7 and len(_oi) == 7
      and all(teng(a.get("unit_price"), b.get("unit_price"), 0.001) and teng(a.get("total_price"), b.get("total_price"), 0.001)
              for a, b in zip(_ti, _oi)),
      [(a.get("name"), a.get("unit_price"), a.get("total_price"), b.get("unit_price"), b.get("total_price")) for a, b in zip(_ti, _oi)])
check("A5 taklif jami / kelishilgan = buyurtma jami / kelishilgan (chegirma bilan)",
      teng(tA.get("jami"), _o.get("total_amount"), 0.001) and teng(tA.get("kelishilgan"), _o.get("agreed_amount"), 0.001)
      and teng(dg.get("total_amount"), _o.get("total_amount"), 0.001) and teng(dg.get("kelishilgan"), _o.get("agreed_amount"), 0.001)
      and float(tA.get("kelishilgan") or 0) < float(tA.get("jami") or 0),
      (tA.get("jami"), tA.get("kelishilgan"), _o.get("total_amount"), _o.get("agreed_amount")))
# tiyin qoidasi: 333 × 10.335 → narx 10.34, jami 3 443.22 (yaxlitlanmagan narxdan 3 441.56 EMAS); 7 × 0.125 → 0.13 / 0.91
_pan = next((x for x in _ti if x.get("category") == "panel"), {})
_don = next((x for x in _ti if x.get("category") == "dona"), {})
check("A6 tiyin qoidasi: panel 333 × 10,335 → narx 10,34, jami 3 443,22; donali 7 × 0,125 → 0,13 / 0,91",
      teng(_pan.get("unit_price"), 10.34, 0.0001) and teng(_pan.get("total_price"), 3443.22, 0.0001)
      and teng(_don.get("unit_price"), 0.13, 0.0001) and teng(_don.get("total_price"), 0.91, 0.0001), (_pan, _don))
_bo = js(req(C, "post", "/api/takliflar", json={"mijoz": "Chegirmasiz", "telefon": None, "buyurtma": tana_oddiy(agreed_amount=None)})) or {}
_bo0 = js(req(C, "post", "/api/takliflar", json={"mijoz": "Nol summa", "telefon": None, "buyurtma": tana_oddiy(agreed_amount=0)})) or {}
check("A7 kelishilgan summa berilmasa (null) yoki 0 — jamiga teng (buyurtma qoidasi `agreed_amount or jami`)",
      teng((_bo.get("taklif") or {}).get("kelishilgan"), 120_000) and teng((_bo0.get("taklif") or {}).get("kelishilgan"), 120_000),
      (_bo, _bo0))
_rb, _tb, _ = taklif(c=CB, mijoz="B mijoz", buyurtma=tana_oddiy(peno=ID["peno_b"]))
check("A8 raqam korxona bo'yicha: A da keyingilari T-0002, T-0003; B ning birinchisi — T-0001",
      (_bo.get("taklif") or {}).get("raqam") == "T-0002" and (_bo0.get("taklif") or {}).get("raqam") == "T-0003"
      and _rb.status_code == 200 and _tb.get("raqam") == "T-0001", (_bo.get("taklif"), _tb))
_fa = faoliyat("created", TA)
check("A9 Faoliyat jurnali: «Taklif T-0001 · Ali Valiyev» yaratildi — jami / kelishilgan va detallar soni, korxona 1",
      len(_fa) == 1 and _fa[0][0] == 1 and _fa[0][1] == "Taklif T-0001 · Ali Valiyev" and "7 ta detal" in (_fa[0][3] or "")
      and "kelishilgan" in (_fa[0][3] or "") and _fa[0][4] == "TK Admin", _fa)
check("A10 audit amali «rasmiylashtirildi» o'zbekcha ro'yxatda (`AUDIT_AMALLARI`)",
      "rasmiylashtirildi" in getattr(crud, "AUDIT_AMALLARI", {}), None)
check("A11 taklif tanasi saqlanadi: 7 detal (ichki detal, izohlar, havolalar bilan), retsept, usta, loy, asosiy narx, muddat",
      len(_ti) == 7 and (_ti[0].get("sub_details") or [{}])[0].get("name") == "Rebristo" and _ti[2].get("notes") == "dona_yield=4"
      and _ti[6].get("finished_product_id") == ID["fp"] and dg.get("recipe_id") == ID["r1"] and dg.get("master_id") == ID["usta"]
      and teng(dg.get("loy_kg"), 3) and teng(dg.get("base_price"), 1_200_000)
      and str(dg.get("deadline") or "").startswith((_BUGUN + timedelta(days=10)).isoformat())
      and (dg.get("_taklif") or {}).get("raqam") == "T-0001", {k: dg.get(k) for k in ("recipe_id", "master_id", "loy_kg", "deadline")})

# ══════════════════════════════════════════════════════════════
section("B. Taklif HECH NARSA yozmaydi (ombor, loyiha, buyurtma, raqamlar, Moliya, Telegram)")
# ══════════════════════════════════════════════════════════════
H1 = holat()
_tg0 = len(TG)
_rB, _tB, _ = taklif(mijoz="Loyli mijoz", buyurtma=tana_oddiy(nom="TK Qoplamali", recipe_id=ID["r2"], loy_kg=10,
                                                             items=[{**tana_oddiy()["items"][0], "is_coated": True}]))
TB = _tB.get("id")
req(C, "get", f"/api/takliflar/{TB}/pdf")
req(C, "get", "/api/takliflar")
req(C, "put", f"/api/takliflar/{TB}", json={"mijoz": "Loyli mijoz", "telefon": None,
                                            "buyurtma": tana_oddiy(nom="TK Qoplamali 2", recipe_id=ID["r2"], loy_kg=12)})
H2 = holat()
_farq = {k: (H1[k], H2[k]) for k in H1 if H1[k] != H2[k]}
check("B1 yaratish + PDF + ro'yxat + tahrir: buyurtma, detal, loyiha, harakat, to'lov, kassa, ishlab chiqarish, material soni, "
      "HAR material qoldig'i, tayyor mahsulot (qoldiq, band), loyiha / buyurtma raqam hisoblagichlari — AYNAN",
      _rB.status_code == 200 and not _farq, _farq or (_rB.status_code, _rB.text[:300]))
_s = SessionLocal()
_tayyor_loy = _s.query(Inventory).filter(Inventory.company_id == 1, Inventory.item_name.like("%TK qumli loy%")).count()
_s.close()
check("B2 loy ogohlantirishi tekshiruvi «Tayyor loy (TK qumli loy)» pozitsiyasini YARATMAYDI (ombor jadvaliga qator qo'shilmaydi)",
      _tayyor_loy == 0 and H1["inventory"] == H2["inventory"], (_tayyor_loy, H1["inventory"], H2["inventory"]))
check("B3 Telegram — hech narsa yuborilmadi", len(TG) == _tg0, TG[_tg0:])
_m_bugun = oylik()
taklif(mijoz="Moliya tekshiruvi", buyurtma=tana_oddiy(nom="TK Moliya karniz"))
check("B4 Moliya (oylik hisobot, joriy oy): yangi taklifdan keyin AYNAN", oylik() == _m_bugun, None)

# ══════════════════════════════════════════════════════════════
section("C. PDF — «TAKLIF (HISOB-KITOB)», «Narxlar 3 kun amal qiladi»; jadval va summalar buyurtma hujjati bilan AYNAN")
# ══════════════════════════════════════════════════════════════
pT = req(C, "get", f"/api/takliflar/{TA}/pdf")
pO = req(C, "get", f"/api/orders/{OID}/pdf") if OID else _Xato("buyurtma yo'q")
mT, mO = pdf_matn(pT.content), pdf_matn(pO.content)
check("C1 PDF — 200, application/pdf, «inline; filename=\"taklif_T-0001.pdf\"»",
      pT.status_code == 200 and pT.content[:4] == b"%PDF" and "pdf" in (pT.headers.get("content-type") or "")
      and 'filename="taklif_T-0001.pdf"' in (pT.headers.get("content-disposition") or "")
      and (pT.headers.get("content-disposition") or "").startswith("inline"), (pT.status_code, pT.headers))
check("C2 sarlavha «TAKLIF (HISOB-KITOB)», raqam «# T-0001», mijoz, telefon, «TAKLIF RAQAMI»; «BUYURTMA HISOBI» yo'q",
      "TAKLIF (HISOB-KITOB)" in mT and "# T-0001" in mT and "Ali Valiyev" in mT and "+998 90 111 22 33" in mT
      and "TAKLIF RAQAMI" in mT and "BUYURTMA HISOBI" not in mT, mT[:500])
check("C3 pastida «Narxlar 3 kun amal qiladi» (egasi qarori); to'lov / qarz / imzo / loyiha / usta qatori YO'Q",
      "Narxlar 3 kun amal qiladi" in mT and "QARZ QOLDI" not in mT and "To'langan" not in mT and "Imzo" not in mT
      and "LOYIHA" not in mT and "USTA" not in mT and "Taklif: T-0001" in mT, mT[-400:])
_jT, _jO = jadval_qismi(mT), jadval_qismi(mO)
check("C4 detallar jadvali (nomi, birligi, miqdori, birlik narxi, jami) va summa qatorlari (Umumiy jami, Chegirma, TO'LOV SUMMASI) — "
      "buyurtma hujjati bilan AYNAN", _jT and _jT == _jO, {"taklif": _jT, "buyurtma": _jO})
check("C5 sana — bugungi Toshkent sanasi (taklif sanasi)", f"Sana: {_BUGUN.strftime('%d.%m.%Y')}" in mT, mT[:200])
# Taklif sanasi o'tgan kunda — PDF sanasi o'sha kun (bugun EMAS), ro'yxatda «muddati o'tgan»
if Taklif is not None and TB:
    _s = SessionLocal()
    _t = _s.get(Taklif, TB)
    _t.yaratilgan = datetime.utcnow() - timedelta(days=6)
    _t.tahrirlangan = None
    _t.amal_muddati = _BUGUN - timedelta(days=3)
    _s.commit()
    _s.close()
_d6 = (_BUGUN - timedelta(days=6)).strftime("%d.%m.%Y")
mB = pdf_matn(req(C, "get", f"/api/takliflar/{TB}/pdf").content)
check("C6 PDF sanasi — taklif saqlangan kun (6 kun oldin), bugun emas", f"Sana: {_d6}" in mB and "TAKLIF (HISOB-KITOB)" in mB, mB[:300])
check("C7 PDF da izoh (taklif hujjatida ko'rinadi) — «Izoh:»",
      "Yetkazib berish alohida" in pdf_matn(req(C, "get", "/api/takliflar/{}/pdf".format(
          (taklif(mijoz="Izohli", buyurtma=tana_oddiy(notes="Yetkazib berish alohida"))[1] or {}).get("id"))).content), None)
check("C8 static: PDF matni muddat konstantasi bilan mos («Narxlar 3 kun» — `crud.TAKLIF_MUDDAT_KUN` = 3)",
      f"Paragraph(\"Narxlar {getattr(crud, 'TAKLIF_MUDDAT_KUN', 0)} kun amal qiladi\"" in fayl("pdf_service.py"), None)

# ══════════════════════════════════════════════════════════════
section("D. Tekshiruvlar — rad (400 / 422), HECH NARSA yozilmaydi, raqam band qilinmaydi")
# ══════════════════════════════════════════════════════════════
_n0, _h0 = tk_soni(), holat()


def rad(tana_, kod=(400,)):
    r = req(C, "post", "/api/takliflar", json=tana_)
    return r.status_code in kod, (r.status_code, r.text[:200])


_it0 = tana_oddiy()["items"][0]
_ishlar = [
    ("D1 mijoz ismi bo'sh", {"mijoz": "", "buyurtma": tana_oddiy()}, (400, 422)),
    ("D2 mijoz ismi faqat bo'shliq / 1 harf", {"mijoz": "  A  ", "buyurtma": tana_oddiy()}, (400,)),
    ("D3 telefon 20 belgidan uzun", {"mijoz": "Ali", "telefon": "+998 90 111 22 33 44 55", "buyurtma": tana_oddiy()}, (400, 422)),
    ("D4 detal yo'q", {"mijoz": "Ali", "buyurtma": {"order_type": "product", "items": []}}, (400,)),
    ("D5 detal turi bo'sh", {"mijoz": "Ali", "buyurtma": tana_oddiy(items=[{**_it0, "category": ""}])}, (400,)),
    ("D6 sig'im (detal jami 9 999 999 999,99 dan katta)",
     {"mijoz": "Ali", "buyurtma": tana_oddiy(items=[{**_it0, "unit_price": 9_000_000_000, "quantity": 5}])}, (400,)),
    ("D7 loy 10 kg — qoplama retseptisiz", {"mijoz": "Ali", "buyurtma": tana_oddiy(loy_kg=10)}, (400,)),
    ("D8 loy — matn «5»", {"mijoz": "Ali", "buyurtma": tana_oddiy(loy_kg="5")}, (400, 422)),
    ("D9 manfiy narx", {"mijoz": "Ali", "buyurtma": tana_oddiy(items=[{**_it0, "unit_price": -5}])}, (400, 422)),
    ("D10 begona korxona penoplasti", {"mijoz": "Ali", "buyurtma": tana_oddiy(peno=ID["peno_b"])}, (400,)),
    ("D11 yo'q penoplast", {"mijoz": "Ali", "buyurtma": tana_oddiy(peno=987654)}, (400,)),
    ("D12 begona usta", {"mijoz": "Ali", "buyurtma": tana_oddiy(master_id=ID["usta_b"])}, (400,)),
    ("D13 begona retsept", {"mijoz": "Ali", "buyurtma": tana_oddiy(recipe_id=ID["r_b"])}, (400,)),
    ("D14 begona tayyor mahsulot", {"mijoz": "Ali", "buyurtma": tana_oddiy(items=[{**_it0, "finished_product_id": ID["fp_b"]}])}, (400,)),
    ("D15 begona mahsulot turi", {"mijoz": "Ali", "buyurtma": tana_oddiy(items=[
        {"name": "X tur", "category": "mrp_product", "quantity": 1, "unit_price": 10, "product_type_id": ID["pt_b"]}])}, (400,)),
    ("D16 detal retsepti begona (loy sotish)", {"mijoz": "Ali", "buyurtma": tana_oddiy(items=[
        {"name": "Loy", "category": "loy_sotish", "quantity": 5, "unit_price": 100, "recipe_id": ID["r_b"]}])}, (400,)),
    ("D17 tanasiz (buyurtma yo'q)", {"mijoz": "Ali"}, (422,)),
]
for _nom, _t, _k in _ishlar:
    _ok, _det = rad(_t, _k)
    check(f"{_nom} — rad", _ok, _det)
check("D18 rad etilganlardan keyin: taklif yaratilmadi, boshqa hech narsa o'zgarmadi",
      tk_soni() == _n0 and holat() == _h0, (tk_soni(), _n0))
_oldingi = tk_max(1)
_rn, _tn, _ = taklif(mijoz="Raqam tekshiruvi")
check("D19 rad etilganlar raqam band qilmaydi — keyingi taklif raqami ketma-ket (bo'shliqsiz)",
      _rn.status_code == 200 and _oldingi > 0 and _tn.get("seq") == _oldingi + 1 and _tn.get("raqam") == f"T-{_oldingi + 1:04d}",
      (_tn, _oldingi))
check("D20 xabar o'zbekcha va aniq: begona penoplast — «penoplast (plotnost) topilmadi»",
      "penoplast (plotnost) topilmadi" in (js(req(C, "post", "/api/takliflar", json={"mijoz": "Ali", "buyurtma": tana_oddiy(peno=ID["peno_b"])}))
                                         or {}).get("detail", ""), None)

# ══════════════════════════════════════════════════════════════
section("E. «Omborda yetmaydi» — faqat ogohlantirish (saqlanadi), ro'yxat `POST /api/orders` 409 bilan AYNAN")
# ══════════════════════════════════════════════════════════════
_kam = tana_oddiy(nom="TK Katta karniz", uzunlik=100, peno=ID["peno_kam"], recipe_id=ID["r2"], loy_kg=50,
                  items=[{"name": "TK Katta karniz", "category": "profil", "width": 20, "thickness": 10, "length": 100, "quantity": 1,
                          "unit_price": 2_000_000, "is_coated": True, "penoplast_id": ID["peno_kam"]},
                         {"name": "TK Tayyor ko'p", "category": "profil", "width": 20, "thickness": 10, "length": 80, "quantity": 1,
                          "unit_price": 1_600_000, "finished_product_id": ID["fp"], "penoplast_id": ID["peno"], "is_coated": False}])
_he = holat()
_re, _te, _oge = taklif(mijoz="Kam ombor", buyurtma=_kam)
TE = _te.get("id")
_r409 = req(C, "post", "/api/orders", json={**_kam, "project_id": ID["prj"]})
_d409 = (js(_r409) or {}).get("detail") or {}
check("E1 taklif saqlandi (200) — ogohlantirishlar: penoplast, tayyor mahsulot, loy xomashyosi",
      _re.status_code == 200 and isinstance(_oge, list) and any("TK Penoplast 25P" in x for x in _oge)
      and any("TK Tayyor karniz" in x for x in _oge) and any("TK Kvars qumi" in x for x in _oge), (_re.status_code, _oge))
check("E2 ogohlantirishlar — buyurtma yaratishdagi 409 «stock_shortage_warning» ro'yxati bilan AYNAN",
      _r409.status_code == 409 and isinstance(_d409, dict) and _d409.get("shortages") == _oge, (_r409.status_code, _d409, _oge))
_hx = holat()
_es, _ys = dict(_he["stock"]), dict(_hx["stock"])
check("E3 ombor / tayyor mahsulot o'zgarmadi (taklif ham, rad etilgan buyurtma ham; buyurtmaning o'z yetishmovchilik tekshiruvi bo'sh "
      "«Tayyor loy» pozitsiyasini ochishi mumkin — avvalgi qoida, qoldig'i 0)",
      {k: v for k, v in _hx.items() if k not in ("inventory", "stock")} == {k: v for k, v in _he.items() if k not in ("inventory", "stock")}
      and all(_ys.get(k) == v for k, v in _es.items()) and all(v == 0 for k, v in _ys.items() if k not in _es),
      {k: (_es.get(k), _ys.get(k)) for k in set(_es) | set(_ys) if _es.get(k) != _ys.get(k)})
check("E4 ogohlantirishsiz taklif — bo'sh ro'yxat", isinstance(ogA, list) and taklif(mijoz="Yetarli")[2] == [], ogA)

# ══════════════════════════════════════════════════════════════
section("F. Ro'yxat — qidiruv, filtrlar, sonlar, muddati o'tgan, sahifalash")
# ══════════════════════════════════════════════════════════════
_l = js(req(C, "get", "/api/takliflar")) or {}
_lt = _l.get("takliflar") or []
check("F1 ro'yxat — eng yangisi tepada, faqat A korxonasiniki; har qatorda raqam, mijoz, summa, holat, muddat, detallar",
      _lt and _lt[0].get("seq") == max(x.get("seq") for x in _lt) and all(x.get("raqam", "").startswith("T-") for x in _lt)
      and not any(x.get("mijoz") == "B mijoz" for x in _lt) and all("detallar_soni" in x and "amal_muddati" in x for x in _lt),
      [(x.get("raqam"), x.get("mijoz")) for x in _lt][:6])
_q1 = js(req(C, "get", "/api/takliflar", params={"q": "ALI VAL"})) or {}
_q2 = js(req(C, "get", "/api/takliflar", params={"q": "901112233"})) or {}
_q3 = js(req(C, "get", "/api/takliflar", params={"q": "T-0001"})) or {}
_q4 = js(req(C, "get", "/api/takliflar", params={"q": "2"})) or {}
check("F2 qidiruv: ism (katta-kichik harf farqsiz), telefon raqamlari (bo'shliqsiz), raqam «T-0001», tartib raqami «2»",
      [x.get("raqam") for x in _q1.get("takliflar") or []] == ["T-0001"]
      and "T-0001" in [x.get("raqam") for x in _q2.get("takliflar") or []]
      and [x.get("raqam") for x in _q3.get("takliflar") or []] == ["T-0001"]
      and "T-0002" in [x.get("raqam") for x in _q4.get("takliflar") or []],
      (_q1.get("takliflar"), [x.get("raqam") for x in _q2.get("takliflar") or []], _q3.get("sonlar"), _q4.get("sonlar")))
_fo = js(req(C, "get", "/api/takliflar", params={"filtr": "muddati_otgan"})) or {}
check("F3 «Muddati o'tgan» filtri — muddati o'tgan taklif (C6 dagi) va faqat u; belgi `muddati_otgan`",
      [x.get("id") for x in _fo.get("takliflar") or []] == [TB] and (_fo.get("takliflar") or [{}])[0].get("muddati_otgan") is True,
      [x.get("raqam") for x in _fo.get("takliflar") or []])
_so = _l.get("sonlar") or {}
check("F4 sonlar: hammasi = amalda + muddati o'tgan + rasmiylashtirilgan + bekor; muddati o'tgan = 1",
      _so.get("hammasi") == sum(_so.get(k, 0) for k in ("faol", "muddati_otgan", "rasmiylashtirildi", "bekor"))
      and _so.get("muddati_otgan") == 1 and _so.get("hammasi") == len(_lt), _so)
check("F5 taklif AVTOMATIK o'chirilmaydi: muddati o'tgan taklif bazada, PDF va tafsiloti ochiladi",
      tk_db(TB) is not None and req(C, "get", f"/api/takliflar/{TB}").status_code == 200
      and req(C, "get", f"/api/takliflar/{TB}/pdf").status_code == 200, None)
_s = SessionLocal()
_sah = xavfsiz(lambda: crud.takliflar_royxati(_s, 1, hajm=2, sahifa=2), {})
_sah9 = xavfsiz(lambda: crud.takliflar_royxati(_s, 1, hajm=2, sahifa=999), {})
_s.close()
check("F6 sahifalash: 2 tadan — 2-sahifada 2 ta, sahifalar soni to'g'ri; katta sahifa raqami — oxirgi sahifaga keltiriladi",
      len(_sah.get("takliflar") or []) == 2 and _sah.get("sahifa") == 2 and _sah.get("sahifalar") == (len(_lt) + 1) // 2
      and _sah9.get("sahifa") == _sah.get("sahifalar"), (_sah.get("sahifa"), _sah.get("sahifalar"), _sah9.get("sahifa")))
check("F7 noto'g'ri filtr — «hammasi»; noto'g'ri sahifa — 422 (son emas)",
      (js(req(C, "get", "/api/takliflar", params={"filtr": "yoq"})) or {}).get("filtr") == "hammasi"
      and req(C, "get", "/api/takliflar", params={"sahifa": "x"}).status_code == 422, None)

# ══════════════════════════════════════════════════════════════
section("G. Tahrir — faqat «yangi»; hisob qayta; muddat yana 3 kun")
# ══════════════════════════════════════════════════════════════
_rg = req(C, "put", f"/api/takliflar/{TB}", json={"mijoz": "Loyli mijoz (yangi)", "telefon": "+998 91 000 00 01",
                                                  "buyurtma": tana_oddiy(nom="TK Tahrir karniz", uzunlik=5, narx=60_000)})
_tg = (js(_rg) or {}).get("taklif") or {}
check("G1 muddati o'tgan taklifni tahrirlash — 200; jami qayta (60 000), mijoz / telefon yangi, muddat — bugun + 3 kun, belgisi yo'q",
      _rg.status_code == 200 and teng(_tg.get("jami"), 60_000) and _tg.get("mijoz") == "Loyli mijoz (yangi)"
      and _tg.get("telefon") == "+998 91 000 00 01" and _tg.get("amal_muddati") == (_BUGUN + timedelta(days=3)).isoformat()
      and _tg.get("muddati_otgan") is False and _tg.get("tahrirlagan") == "TK Admin" and _tg.get("raqam") == tka(TB, "raqam"),
      (_rg.status_code, _rg.text[:300]))
mG = pdf_matn(req(C, "get", f"/api/takliflar/{TB}/pdf").content)
check("G2 tahrirdan keyin PDF — yangi sana (bugun), yangi detal; eski detal yo'q",
      f"Sana: {_BUGUN.strftime('%d.%m.%Y')}" in mG and "TK Tahrir karniz" in mG and "TK Qoplamali" not in mG, mG[:400])
_fu = faoliyat("updated", TB)
check("G3 Faoliyat jurnali: «tahrirlandi» — eski va yangi summa", _fu and "60 000" in (_fu[-1][3] or "") and _fu[-1][2],
      _fu[-1:] if _fu else _fu)
check("G4 begona korxona taklifini tahrirlash — 404; yo'q taklif — 404",
      req(CB, "put", f"/api/takliflar/{TB}", json={"mijoz": "Hack", "buyurtma": tana_oddiy(peno=ID["peno_b"])}).status_code == 404
      and req(C, "put", "/api/takliflar/987654", json={"mijoz": "Yo'q", "buyurtma": tana_oddiy()}).status_code == 404
      and tka(TB, "mijoz") == "Loyli mijoz (yangi)", None)
_rgx = req(C, "put", f"/api/takliflar/{TB}", json={"mijoz": "Loyli", "buyurtma": tana_oddiy(peno=ID["peno_b"])})
check("G5 tahrirda noto'g'ri tana (begona penoplast) — 400, taklif o'zgarmadi",
      _rgx.status_code == 400 and teng(tka(TB, "jami"), 60_000) and tka(TB, "mijoz") == "Loyli mijoz (yangi)", (_rgx.status_code, _rgx.text[:200]))

# ══════════════════════════════════════════════════════════════
section("H. Bekor qilish — faqat qo'lda, faqat «yangi»; keyin tahrir / rasmiylashtirish yo'q")
# ══════════════════════════════════════════════════════════════
_rh, _th, _ = taklif(mijoz="Bekor mijoz", buyurtma=tana_oddiy(nom="TK Bekor karniz"))
TH = _th.get("id")
check("H1 begona korxona bekor qila olmaydi — 404", req(CB, "post", f"/api/takliflar/{TH}/bekor").status_code == 404
      and (tk_db(TH) and tka(TH, "holat")) == "yangi", None)
_rb1 = req(C, "post", f"/api/takliflar/{TH}/bekor")
check("H2 bekor — 200, holat «bekor», kim / qachon yozildi; taklif o'chirilmadi",
      _rb1.status_code == 200 and ((js(_rb1) or {}).get("taklif") or {}).get("holat") == "bekor" and tk_db(TH) is not None
      and tka(TH, "bekor_qilgan") == "TK Admin" and tka(TH, "bekor_vaqti") is not None, (_rb1.status_code, _rb1.text[:200]))
_rb2 = req(C, "post", f"/api/takliflar/{TH}/bekor")
_rb3 = req(C, "put", f"/api/takliflar/{TH}", json={"mijoz": "Bekor mijoz", "buyurtma": tana_oddiy()})
_rb4 = req(C, "post", f"/api/takliflar/{TH}/rasmiylashtir", json={"loyiha_id": ID["prj"], "buyurtma": tana_oddiy(
    deadline=f"{_BUGUN.isoformat()}T00:00:00")})
check("H3 bekor qilingan taklif: qayta bekor / tahrir / rasmiylashtirish — 409 (sabab bilan), hech narsa o'zgarmadi",
      (_rb2.status_code, _rb3.status_code, _rb4.status_code) == (409, 409, 409)
      and "bekor" in str(((js(_rb4) or {}).get("detail") or {}).get("message", "")).lower() and tka(TH, "holat") == "bekor",
      [(_rb2.status_code, _rb2.text[:120]), (_rb3.status_code, _rb3.text[:120]), (_rb4.status_code, _rb4.text[:160])])
check("H4 Faoliyat jurnali — «bekor qilindi»", len(faoliyat("cancelled", TH)) == 1, faoliyat("cancelled", TH))

# ══════════════════════════════════════════════════════════════
section("I. Rasmiylashtirish — bitta tranzaksiyada loyiha + buyurtma; narxlar AYNAN; ombor oddiy buyurtmadek")
# ══════════════════════════════════════════════════════════════
_ri, _ti0, _ = taklif(mijoz="Rasmiy Mijoz", telefon="+998 93 555 66 77", buyurtma=tana_toliq(agreed_amount=360_000))
TI = _ti0.get("id")
_dti = js(req(C, "get", f"/api/takliflar/{TI}")) or {}
_bu_tana = {k: v for k, v in _dti.items() if k in ("order_type", "recipe_id", "master_id", "base_price", "loy_kg", "deadline",
                                                   "agreed_amount", "notes")}
_bu_tana["items"] = [{k: v for k, v in it.items() if k != "total_price"} for it in (_dti.get("items") or [])]
# nazorat: AYNAN shu tana bilan oddiy buyurtma — ombor qancha yechilishi
_hk0 = holat()
_rk = req(C, "post", "/api/orders", params={"confirm_shortage": "true"}, json={**_bu_tana, "project_id": ID["prj_k"]})
_hk1 = holat()
_stk = {a[0]: round(b[1] - a[1], 6) for a, b in zip(_hk0["stock"], _hk1["stock"]) if a[0] == b[0] and a[1] != b[1]}
_n_prj0, _h_i0 = holat()["projects"], holat()
_ri1 = req(C, "post", f"/api/takliflar/{TI}/rasmiylashtir", params={"confirm_shortage": "true"}, json={
    "yangi_loyiha": {"project_name": "Rasmiy Mijoz — uy fasadi", "client_name": "Rasmiy Mijoz", "client_phone": "+998 93 555 66 77"},
    "buyurtma": _bu_tana})
_do = js(_ri1) or {}
_h_i1 = holat()
_stt = {a[0]: round(b[1] - a[1], 6) for a, b in zip(_h_i0["stock"], _h_i1["stock"]) if a[0] == b[0] and a[1] != b[1]}
OI = _do.get("id") if isinstance(_do, dict) else None
_s = SessionLocal()
_oi_db = _s.get(Order, OI) if OI else None
_prj_i = _oi_db.project if _oi_db else None
_rows = [(float(i.unit_price), float(i.total_price), i.name) for i in sorted(_oi_db.items, key=lambda x: x.id)] if _oi_db else []
_prj_vals = (_prj_i.project_name, _prj_i.client_name, _prj_i.client_phone, _prj_i.project_number) if _prj_i else None
_oi_vals = (float(_oi_db.total_amount), float(_oi_db.agreed_amount), _oi_db.status.value, _oi_db.master_id,
            _oi_db.qoplama_retsept_id) if _oi_db else None
_s.close()
check("I1 yangi loyiha bilan rasmiylashtirish — 200 (buyurtma javobi); YANGI loyiha: nomi, mijoz va telefon (taklifdan), raqam PRJ-…",
      _ri1.status_code == 200 and OI and _h_i1["projects"] == _n_prj0 + 1
      and _prj_vals and _prj_vals[:3] == ("Rasmiy Mijoz — uy fasadi", "Rasmiy Mijoz", "+998 93 555 66 77")
      and str(_prj_vals[3]).startswith("PRJ-"), (_ri1.status_code, _ri1.text[:400], _prj_vals))
check("I2 buyurtma detallari narxi / jami, buyurtma jami va kelishilgan summa — TAKLIFDAGI bilan AYNAN; holat «jarayonda», usta, retsept",
      _oi_vals and len(_rows) == 7
      and all(teng(r[0], it.get("unit_price"), 0.001) and teng(r[1], it.get("total_price"), 0.001)
              for r, it in zip(_rows, _dti.get("items") or []))
      and teng(_oi_vals[0], _ti0.get("jami"), 0.001) and teng(_oi_vals[1], _ti0.get("kelishilgan"), 0.001)
      and _oi_vals[2] == "in_progress" and _oi_vals[3] == ID["usta"] and _oi_vals[4] == ID["r1"], (_oi_vals, _rows[:3]))
check("I3 ombordan yechilgani (penoplast, loy xomashyosi, loy sotish, tayyor mahsulot) — o'sha tanali ODDIY buyurtma bilan AYNAN",
      _rk.status_code == 200 and _stk and _stk == _stt
      and [(a[0], round(b[1] - a[1], 6)) for a, b in zip(_hk0["fpq"], _hk1["fpq"])]
      == [(a[0], round(b[1] - a[1], 6)) for a, b in zip(_h_i0["fpq"], _h_i1["fpq"])], (_stk, _stt))
_tki = tk_db(TI)
check("I4 taklif: holat «rasmiylashtirildi», buyurtma (id, raqam), kim / qachon",
      _tki is not None and _tki.holat == "rasmiylashtirildi" and _tki.order_id == OI and _tki.order_raqam == (_do or {}).get("order_number")
      and _tki.rasmiylashtirgan == "TK Admin" and _tki.rasmiylashtirilgan is not None, _tki)
_fr = faoliyat("rasmiylashtirildi", TI)
check("I5 Faoliyat jurnali — «rasmiylashtirildi»: buyurtma raqami va yangi loyiha",
      len(_fr) == 1 and (_do or {}).get("order_number", "?") in (_fr[0][3] or "") and "Rasmiy Mijoz — uy fasadi" in (_fr[0][3] or ""), _fr)
_h_i2 = holat()
_ri2 = req(C, "post", f"/api/takliflar/{TI}/rasmiylashtir", params={"confirm_shortage": "true"},
           json={"loyiha_id": ID["prj"], "buyurtma": _bu_tana})
check("I6 ikkinchi marta rasmiylashtirish — 409 (buyurtma raqami bilan), yangi buyurtma / loyiha YO'Q",
      _ri2.status_code == 409 and (_do or {}).get("order_number", "?") in str((js(_ri2) or {}).get("detail")) and holat() == _h_i2,
      (_ri2.status_code, _ri2.text[:200]))
# mavjud loyiha, qoralama
_rj, _tj, _ = taklif(mijoz="Mavjud loyihaga", buyurtma=tana_oddiy(nom="TK Qoralama karniz"))
_hj0 = holat()
_rj1 = req(C, "post", f"/api/takliflar/{_tj.get('id')}/rasmiylashtir", json={
    "loyiha_id": ID["prj"], "buyurtma": tana_oddiy(nom="TK Qoralama karniz", is_draft=True, deadline=f"{_BUGUN.isoformat()}T00:00:00")})
_hj1 = holat()
check("I7 mavjud loyiha + qoralama: 200, buyurtma o'sha loyihada, holat «draft»; loyiha qo'shilmadi, ombor tegilmadi",
      _rj1.status_code == 200 and (js(_rj1) or {}).get("project_id") == ID["prj"] and (js(_rj1) or {}).get("status") == "draft"
      and _hj1["projects"] == _hj0["projects"] and _hj1["stock"] == _hj0["stock"] and _hj1["orders"] == _hj0["orders"] + 1,
      (_rj1.status_code, _rj1.text[:300]))
# yetishmovchilik — 409 → HECH NARSA (yangi loyiha ham) → tasdiq bilan
_hk = holat()
_rk1 = req(C, "post", f"/api/takliflar/{TE}/rasmiylashtir", json={
    "yangi_loyiha": {"project_name": "Kam ombor loyihasi", "client_name": "Kam ombor", "client_phone": None}, "buyurtma": _kam})
check("I8 ombor yetmaydi — 409 «stock_shortage_warning» (o'sha ro'yxat); YANGI LOYIHA HAM, buyurtma ham yozilmadi, taklif «yangi»",
      _rk1.status_code == 409 and ((js(_rk1) or {}).get("detail") or {}).get("type") == "stock_shortage_warning"
      and holat() == _hk and tka(TE, "holat") == "yangi", (_rk1.status_code, _rk1.text[:300]))
_rk2 = req(C, "post", f"/api/takliflar/{TE}/rasmiylashtir", params={"confirm_shortage": "true"}, json={
    "yangi_loyiha": {"project_name": "Kam ombor loyihasi", "client_name": "Kam ombor", "client_phone": None}, "buyurtma": _kam})
check("I9 «Ha, davom etaman» (confirm_shortage) — 200: loyiha + buyurtma, taklif rasmiylashtirildi",
      _rk2.status_code == 200 and holat()["projects"] == _hk["projects"] + 1 and tka(TE, "holat") == "rasmiylashtirildi",
      (_rk2.status_code, _rk2.text[:300]))
# begona loyiha, noto'g'ri tanlar
_rl, _tl, _ = taklif(mijoz="Begona loyiha", buyurtma=tana_oddiy(nom="TK Begona"))
TL = _tl.get("id")
_hl = holat()
_rl1 = req(C, "post", f"/api/takliflar/{TL}/rasmiylashtir", json={"loyiha_id": ID["prj_b"], "buyurtma": tana_oddiy(nom="TK Begona")})
_rl2 = req(C, "post", f"/api/takliflar/{TL}/rasmiylashtir", json={"buyurtma": tana_oddiy(nom="TK Begona")})
_rl3 = req(C, "post", f"/api/takliflar/{TL}/rasmiylashtir", json={
    "loyiha_id": ID["prj"], "yangi_loyiha": {"project_name": "Ikki", "client_name": "Ikki"}, "buyurtma": tana_oddiy()})
_rl4 = req(C, "post", f"/api/takliflar/{TL}/rasmiylashtir", json={
    "yangi_loyiha": {"project_name": "Turi bo'sh", "client_name": "Begona loyiha"},
    "buyurtma": tana_oddiy(items=[{**_it0, "category": ""}])})
_rl5 = req(C, "post", f"/api/takliflar/{TL}/rasmiylashtir", json={
    "yangi_loyiha": {"project_name": "X", "client_name": "Begona loyiha"}, "buyurtma": tana_oddiy()})
check("I10 begona korxona loyihasi — 404; loyiha tanlanmagan / ikkalasi — 400; detal turi bo'sh (yangi loyiha bilan) — 400; "
      "loyiha nomi 1 harf — 422; HECH NARSA yozilmadi (yangi loyiha ham), taklif «yangi»",
      (_rl1.status_code, _rl2.status_code, _rl3.status_code, _rl4.status_code, _rl5.status_code) == (404, 400, 400, 400, 422)
      and holat() == _hl and tka(TL, "holat") == "yangi",
      [(r.status_code, r.text[:100]) for r in (_rl1, _rl2, _rl3, _rl4, _rl5)])
_hb = holat()
_rl6 = req(CBY, "post", f"/api/takliflar/{TL}/rasmiylashtir", json={
    "yangi_loyiha": {"project_name": "Ruxsatsiz loyiha", "client_name": "Begona loyiha"}, "buyurtma": tana_oddiy(nom="TK Begona")})
check("I11 «Loyihalar: Yaratish» ruxsati YO'Q foydalanuvchi yangi loyiha bilan — 403 (sabab bilan), hech narsa yozilmadi",
      _rl6.status_code == 403 and "Loyihalar: Yaratish" in str((js(_rl6) or {}).get("detail")) and holat() == _hb,
      (_rl6.status_code, _rl6.text[:200]))
_rl7 = req(CBY, "post", f"/api/takliflar/{TL}/rasmiylashtir", json={
    "loyiha_id": ID["prj"], "buyurtma": tana_oddiy(nom="TK Begona", deadline=f"{_BUGUN.isoformat()}T00:00:00")})
check("I12 o'sha foydalanuvchi MAVJUD loyiha bilan — 200 (buyurtma yaratish ruxsati yetarli)",
      _rl7.status_code == 200 and tka(TL, "holat") == "rasmiylashtirildi", (_rl7.status_code, _rl7.text[:200]))
# muddati o'tgan taklif
_rm, _tm, _ = taklif(mijoz="Kech qolgan", buyurtma=tana_oddiy(nom="TK Kech"))
if Taklif is not None and _tm.get("id"):
    _s = SessionLocal()
    _t = _s.get(Taklif, _tm.get("id"))
    _t.amal_muddati = _BUGUN - timedelta(days=4)
    _s.commit()
    _s.close()
_rm1 = req(C, "post", f"/api/takliflar/{_tm.get('id')}/rasmiylashtir", json={"loyiha_id": ID["prj"], "buyurtma": tana_oddiy(nom="TK Kech")})
check("I13 muddati o'tgan taklif ham rasmiylashtiriladi (egasi javobi 11:12)", _rm1.status_code == 200, (_rm1.status_code, _rm1.text[:200]))
check("I14 rasmiylashtirilgan taklif tahrirlanmaydi / bekor qilinmaydi — 409",
      req(C, "put", f"/api/takliflar/{TI}", json={"mijoz": "X Y", "buyurtma": tana_oddiy()}).status_code == 409
      and req(C, "post", f"/api/takliflar/{TI}/bekor").status_code == 409 and tka(TI, "holat") == "rasmiylashtirildi", None)

# ══════════════════════════════════════════════════════════════
section("J. Korxona izolyatsiyasi")
# ══════════════════════════════════════════════════════════════
_hJ = holat()
_jr = [req(CB, "get", f"/api/takliflar/{TA}").status_code, req(CB, "get", f"/api/takliflar/{TA}/pdf").status_code,
       req(CB, "put", f"/api/takliflar/{TA}", json={"mijoz": "B Hack", "buyurtma": tana_oddiy(peno=ID["peno_b"])}).status_code,
       req(CB, "post", f"/api/takliflar/{TA}/bekor").status_code,
       req(CB, "post", f"/api/takliflar/{TA}/rasmiylashtir", json={"loyiha_id": ID["prj_b"], "buyurtma": tana_oddiy(peno=ID["peno_b"])}).status_code]
check("J1 B korxona A ning taklifini ko'ra / PDF / tahrirlay / bekor / rasmiylashtira olmaydi — hammasi 404; A taklifi o'zgarmadi",
      _jr == [404] * 5 and tka(TA, "holat") == "yangi" and tka(TA, "mijoz") == "Ali Valiyev" and holat() == _hJ, _jr)
_lb = js(req(CB, "get", "/api/takliflar")) or {}
check("J2 B ro'yxatida faqat o'z taklifi (T-0001 «B mijoz»), sonlar ham faqat o'ziniki",
      [(x.get("raqam"), x.get("mijoz")) for x in _lb.get("takliflar") or []] == [("T-0001", "B mijoz")]
      and (_lb.get("sonlar") or {}).get("hammasi") == 1, _lb.get("takliflar"))
_lbq = js(req(CB, "get", "/api/takliflar", params={"q": "Ali"})) or {}
check("J3 B qidiruvida A ning mijozi topilmaydi", not (_lbq.get("takliflar") or []) and isinstance(_lbq.get("sonlar"), dict), _lbq)

# ══════════════════════════════════════════════════════════════
section("K. Ruxsatlar — «Buyurtmalar: Ko'rish» (ro'yxat, PDF), «Buyurtmalar: Yaratish» (yozish, tahrir, bekor, rasmiylashtirish)")
# ══════════════════════════════════════════════════════════════
_rn1, _tn1, _ = taklif(c=CN, mijoz="Menejer mijozi", buyurtma=tana_oddiy(nom="TK Menejer karniz"))
check("K1 Menejer — taklif yozadi (200), ro'yxat va PDF ochadi", _rn1.status_code == 200
      and req(CN, "get", "/api/takliflar").status_code == 200 and req(CN, "get", f"/api/takliflar/{TA}/pdf").status_code == 200,
      (_rn1.status_code, _rn1.text[:200]))
_hK = holat()
_n_k = tk_soni()
_kk = {
    "Moliyachi": [req(CF, "post", "/api/takliflar", json={"mijoz": "M", "buyurtma": tana_oddiy()}).status_code,
                  req(CF, "get", "/api/takliflar").status_code, req(CF, "get", f"/api/takliflar/{TA}/pdf").status_code],
    "Omborchi": [req(CW, "post", "/api/takliflar", json={"mijoz": "O", "buyurtma": tana_oddiy()}).status_code,
                 req(CW, "get", "/api/takliflar").status_code, req(CW, "post", f"/api/takliflar/{TA}/bekor").status_code],
    "Faqat ko'rish": [req(CKR, "get", "/api/takliflar").status_code, req(CKR, "get", f"/api/takliflar/{TA}/pdf").status_code,
                      req(CKR, "post", "/api/takliflar", json={"mijoz": "K", "buyurtma": tana_oddiy()}).status_code,
                      req(CKR, "put", f"/api/takliflar/{TA}", json={"mijoz": "K", "buyurtma": tana_oddiy()}).status_code,
                      req(CKR, "post", f"/api/takliflar/{TA}/bekor").status_code,
                      req(CKR, "post", f"/api/takliflar/{TA}/rasmiylashtir", json={"loyiha_id": ID["prj"], "buyurtma": tana_oddiy()}).status_code],
}
check("K2 Moliyachi va Omborchi (buyurtma ruxsati yo'q) — 403; «faqat ko'rish» — ro'yxat / PDF 200, yozish / tahrir / bekor / "
      "rasmiylashtirish 403; hech narsa yozilmadi",
      _kk == {"Moliyachi": [403, 403, 403], "Omborchi": [403, 403, 403], "Faqat ko'rish": [200, 200, 403, 403, 403, 403]}
      and holat() == _hK and tk_soni() == _n_k, _kk)

# ══════════════════════════════════════════════════════════════
section("L. Buyurtma butunlay o'chirilsa — taklif bog'lami uziladi, raqami ro'yxatda qoladi")
# ══════════════════════════════════════════════════════════════
_oid_j = (js(_rj1) or {}).get("id")
_tj_id = _tj.get("id")
_s = SessionLocal()
_okL = xavfsiz(lambda: crud.delete_order(_s, _oid_j, soft=False, performed_by="test"), "xato")
_s.close()
_tjd = tk_db(_tj_id)
_lj = next((x for x in (js(req(C, "get", "/api/takliflar", params={"q": "Mavjud loyihaga"})) or {}).get("takliflar") or []), {})
check("L1 qoralama buyurtma butunlay o'chirildi → taklif `order_id` NULL, `order_raqam` qoladi; ro'yxatda «buyurtma_bor» — yo'q",
      _okL is True and _tjd is not None and _tjd.order_id is None and _tjd.order_raqam and _tjd.holat == "rasmiylashtirildi"
      and _lj.get("buyurtma_bor") is False and _lj.get("order_raqam") == _tjd.order_raqam, (_okL, _tjd, _lj))
_oid_m = (js(_rm1) or {}).get("id")
_s = SessionLocal()
_okS = xavfsiz(lambda: crud.delete_order(_s, _oid_m, soft=True, performed_by="test"), "xato")
_s.close()
_lm = next((x for x in (js(req(C, "get", "/api/takliflar", params={"q": "Kech qolgan"})) or {}).get("takliflar") or []), {})
_s = SessionLocal()
_okP = xavfsiz(lambda: crud.permanent_delete_order(_s, _oid_m, performed_by="test"), "xato")
_s.close()
check("L2 yumshoq o'chirilgan buyurtma (Savatda) — ro'yxatda «buyurtma_bor» yo'q; Savatdan butunlay o'chirilsa — bog'lam NULL",
      _okS is True and _lm.get("buyurtma_bor") is False and _okP is True and tka(_tm.get("id"), "order_id") is None
      and tka(_tm.get("id"), "order_raqam"), (_okS, _lm.get("buyurtma_bor"), _okP))

# ══════════════════════════════════════════════════════════════
section("M. Zaxira: eksport → tiklash (raqamlar, holat, bog'lam), keyingi raqam; tozalash — faqat o'z korxonasi")
# ══════════════════════════════════════════════════════════════
_s = SessionLocal()
_exp = xavfsiz(lambda: crud.export_full_backup(_s, company_id=1), {})
_s.close()
_tkz = (_exp.get("tables") or {}).get("takliflar") or []
_oldin = sorted((t.get("raqam"), t.get("holat"), t.get("order_id"), t.get("order_raqam"), t.get("mijoz")) for t in _tkz)
check("M1 eksportda «takliflar» jadvali — A ning hamma taklifi (B niki yo'q), tana JSON matn, sana matn",
      len(_tkz) == tk_soni(1) and all(t.get("company_id") == 1 for t in _tkz) and all(isinstance(t.get("tana"), str) for t in _tkz)
      and all(isinstance(t.get("amal_muddati"), str) for t in _tkz), len(_tkz))
_s = SessionLocal()
_imp = xavfsiz(lambda: crud.import_full_backup(_s, json.loads(json.dumps(_exp)), company_id=1, replace=True), {"xato": True})
_s.close()
_s = SessionLocal()
_keyin = sorted((t.raqam, t.holat, t.order_id, t.order_raqam, t.mijoz)
                for t in _s.query(Taklif).filter(Taklif.company_id == 1).all()) if Taklif is not None else []
_s.close()
check("M2 tiklash (replace) — muvaffaqiyatli; takliflar AYNAN (raqam, holat, buyurtma bog'lami, mijoz)",
      _imp.get("success") is True and _keyin == _oldin and (_imp.get("per_table") or {}).get("takliflar") == len(_oldin),
      (_imp.get("message") or _imp.get("per_table"), len(_keyin), len(_oldin)))
_rM, _tM, _ = taklif(mijoz="Tiklashdan keyin", buyurtma=tana_oddiy(nom="TK Keyin"))
check("M3 tiklashdan keyin yangi taklif — keyingi raqam (eng kattasi + 1), to'qnashuv yo'q",
      _rM.status_code == 200 and _tM.get("seq") == max([0] + [int(x[0][2:]) for x in _oldin]) + 1, (_rM.status_code, _rM.text[:200]))
_s = SessionLocal()
_rst = xavfsiz(lambda: crud.factory_reset_all_data(_s, company_id=1), {"xato": True})
_s.close()
check("M4 korxonani tozalash — A ning takliflari o'chdi, B niki qoldi", tk_soni(1) == 0 and tk_soni(2) == 1, (tk_soni(1), tk_soni(2), _rst))

# Tozalashdan keyin A da qayta tayyorgarlik (N va P bo'limlari uchun)
_s = SessionLocal()
_p2 = Project(company_id=1, project_number="PRJ-050", client_name="TK Yangi", project_name="TK yangi loyiha", total_budget=0, total_paid=0)
_pe2 = Inventory(company_id=1, item_name="TK Penoplast yangi", unit="blok", stock_quantity=1000, price_per_unit=1_000_000,
                 volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
_s.add_all([_p2, _pe2])
_s.commit()
ID["prj2"], ID["peno2"] = _p2.id, _pe2.id
_s.close()

# ══════════════════════════════════════════════════════════════
section("N. /orders sahifasi — tugmalar va son")
# ══════════════════════════════════════════════════════════════
for _i in range(3):
    taklif(mijoz=f"Sahifa {_i}", buyurtma=tana_oddiy(nom=f"TK Sahifa {_i}", peno=ID["peno2"]))
_rp = req(C, "get", "/orders")
_h = _rp.text if _rp.status_code == 200 else ""
_m = re.search(r'id="tkSoni"[^>]*>(\d+)<', _h)
check("N1 /orders (Admin): «⚡ Tez hisob» va «📝 Takliflar» tugmalari, son = 3 (rasmiylashtirilmagan takliflar)",
      'id="tezHisobBtn"' in _h and 'id="takliflarBtn"' in _h and _m and _m.group(1) == "3" and 'id="takliflarPanel"' in _h,
      (_rp.status_code, _m.group(0) if _m else None))
_hk_ = req(CKR, "get", "/orders").text
check("N2 «faqat ko'rish» roli: «📝 Takliflar» bor, «⚡ Tez hisob» va «Yangi tez hisob» YO'Q; panel `data-yaratish=\"0\"`",
      'id="takliflarBtn"' in _hk_ and 'id="tezHisobBtn"' not in _hk_ and "Yangi tez hisob" not in _hk_
      and 'data-yaratish="0"' in _hk_, None)

# ══════════════════════════════════════════════════════════════
section("P. PG — parallel: raqam; bitta taklifni bir vaqtda ikki marta rasmiylashtirish")
# ══════════════════════════════════════════════════════════════
if PG_URL and Taklif is not None:
    _bar = threading.Barrier(2)
    _nat = []

    def _yarat(i):
        s = SessionLocal()
        try:
            s.info["tenant_company_id"] = 1
            d = schemas.TaklifCreate(mijoz=f"Parallel {i}", telefon=None,
                                     buyurtma=schemas.TaklifBuyurtma(**tana_oddiy(nom=f"TK Parallel {i}", peno=ID["peno2"])))
            _bar.wait(timeout=20)
            t, _ = crud.taklif_yarat(s, 1, d, performed_by="P")
            _nat.append(t.seq)
        except Exception as e:             # noqa: BLE001
            _nat.append(f"{type(e).__name__}: {e}")
        finally:
            s.close()

    _th = [threading.Thread(target=_yarat, args=(i,)) for i in range(2)]
    [x.start() for x in _th]
    [x.join(60) for x in _th]
    check("P1 ikki taklif BIR VAQTDA — ikkalasi saqlandi, raqamlar har xil va ketma-ket", len(_nat) == 2
          and all(isinstance(x, int) for x in _nat) and len(set(_nat)) == 2 and abs(_nat[0] - _nat[1]) == 1, _nat)
    _rq, _tq, _ = taklif(mijoz="Parallel rasmiy", buyurtma=tana_oddiy(nom="TK Parallel rasmiy", peno=ID["peno2"]))
    _hq = holat()
    _bar2 = threading.Barrier(2)
    _nat2 = []

    def _rasm(i):
        c, _ = _kir("TK_admin")
        try:
            _bar2.wait(timeout=20)
            r = c.post(f"/api/takliflar/{_tq.get('id')}/rasmiylashtir", json={
                "yangi_loyiha": {"project_name": f"Parallel loyiha {i}", "client_name": "Parallel rasmiy"},
                "buyurtma": tana_oddiy(nom="TK Parallel rasmiy", peno=ID["peno2"], deadline=f"{_BUGUN.isoformat()}T00:00:00")})
            _nat2.append(r.status_code)
        except Exception as e:             # noqa: BLE001
            _nat2.append(f"{type(e).__name__}: {e}")

    _th2 = [threading.Thread(target=_rasm, args=(i,)) for i in range(2)]
    [x.start() for x in _th2]
    [x.join(90) for x in _th2]
    _hq2 = holat()
    check("P2 bitta taklif BIR VAQTDA ikki marta rasmiylashtirildi — biri 200, biri 409; buyurtma ham, yangi loyiha ham FAQAT bitta",
          sorted(map(str, _nat2)) == ["200", "409"] and _hq2["orders"] == _hq["orders"] + 1 and _hq2["projects"] == _hq["projects"] + 1
          and tka(_tq.get("id"), "holat") == "rasmiylashtirildi", (_nat2, _hq["orders"], _hq2["orders"], _hq["projects"], _hq2["projects"]))

# ══════════════════════════════════════════════════════════════
section("S. Statik — bitta qoida (buyurtma bilan), bitta tranzaksiya, Telegram yo'q")
# ══════════════════════════════════════════════════════════════
_th_src = manba(crud, "taklif_hisobi")
check("S1 `crud.taklif_hisobi` — buyurtma qoidasi yordamchilari (`_buyurtma_narx_jami`, `_pul_yigindi`, `_pul2(… or jami)`)",
      "_buyurtma_narx_jami(" in _th_src and "_pul_yigindi(" in _th_src and '_pul2(getattr(buyurtma, "agreed_amount", None) or jami)' in _th_src,
      _th_src[:200])
_ra_src = manba(main, "api_taklif_rasmiylashtir")
_i_tr, _i_ac, _i_tk = _ra_src.find("with crud.bitta_tranzaksiya(db):"), _ra_src.find("api_create_order(order"), _ra_src.find(
    "crud.taklif_rasmiylashtirildi(")
check("S2 rasmiylashtirish — `api_create_order` ning O'ZI, yangi loyiha va taklif holati BITTA tranzaksiya ichida (qulf bilan)",
      0 < _i_tr < _ra_src.find("crud.create_project(") < _i_ac < _i_tk and "lock=True" in _ra_src, None)
check("S3 taklif yozuvchi funksiyalarda Telegram / ombordan yechish yo'q",
      not any(x in manba(crud, f) for f in ("taklif_yarat", "taklif_tahrirla", "taklif_bekor", "taklif_ogohlantirishlari")
              for x in ("_send_telegram", "deduct_", "_take_finished")) and manba(crud, "taklif_yarat"), None)
check("S4 `_reset_table_order`: taklif buyurtmadan OLDIN o'chiriladi (tiklashda KEYIN qo'shiladi)",
      xavfsiz(lambda: [m.__name__ for m in crud._reset_table_order()].index("Taklif")
              < [m.__name__ for m in crud._reset_table_order()].index("Order"), False), None)
check("S5 korxona qo'riqchisi: `_TENANT_REFS[\"Taklif\"]` — rasmiylashtirilgan buyurtma o'z korxonasiniki",
      ("order_id", "Order") in (getattr(models, "_TENANT_REFS", {}).get("Taklif") or []), None)

try:
    if os.path.exists(_DB):
        os.remove(_DB)
except Exception:                          # noqa: BLE001
    pass
print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
