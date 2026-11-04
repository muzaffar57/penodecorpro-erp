#!/usr/bin/env python3
"""
test_keshbek253.py — kech186 (zip 253: do'kon 3-bosqich «KESHBEK», ERP tomoni + do'kon kabineti API si).

NIMA UCHUN KERAK
  Egasi QARORLARI («Onlayn do'kon rejasi» 30.10, AskUserQuestion 04.11): keshbek = usta KPI % × buyurtma foydasi, «Tayyor» bo'lganda;
  usta KPI foizi o'zgarsa — FAQAT yangi buyurtmalarga (har buyurtmada qotadi); «Keshbek berildi» — naqd (kassadan) / keyingi xarid
  to'loviga (TO'LOV, chegirma emas) / oldin berilgan; qoldiq = barcha yillar hisoblangani − berilgan, qoldiqdan ko'p berib bo'lmaydi;
  usta tasdiqlanguncha bergan buyurtmasi tasdiqda ustaga bog'lanadi. ASL kodda (zip 252) foiz retroaktiv, berilgan yozilmaydi, tasdiqdagi
  bog'lash yo'q (O'LCHANGAN — `work/k253/probe253.py`) — test yiqiladi (qulamaydi).
BO'LIMLAR
  S — tayyorgarlik. Q — foiz qotishi (buyurtma, sotuv, usta almashishi, «Tayyor» dan chiqish, migratsiya). H — hisob joylari (bot, KPI
  sahifasi, tafsilot, oylik, «Tayyor» javobi). B — «Keshbek berildi» (usullar, chegaralar, kassa / to'lov, bog'lam himoyasi, o'chirish,
  takror, tekshiruv, jurnal, bot). T — hisob tasdig'ida buyurtmalarni bog'lash. D — do'kon kabineti API si. Z — ikkinchi korxona, yo'llar
  ruxsati, sahifa, zaxira / tiklash / o'chirish.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432`.
ISHLATISH: python3 tools/test_keshbek253.py
"""
import os
import io
import sys
import tempfile
import contextlib
from datetime import datetime, timedelta

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = f"keshbek253_{os.getpid()}"
_T = tempfile.mkdtemp(prefix="t253_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't253.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "DOKON_BOT_TOKEN", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
    import services                                # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import (UserRole, User, Master, Project, Inventory, Recipe, RecipeIngredient, Order, OrderStatus, Payment,  # noqa: E402
                    CashTransaction, FinishedProductSale, ActivityLog)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"
UstaKeshbek = getattr(models, "UstaKeshbek", None)
DokonMijoz = getattr(models, "DokonMijoz", None)
DokonBuyurtma = getattr(models, "DokonBuyurtma", None)
YIL = tashkent_date().year
OY = (datetime.utcnow() + timedelta(hours=5)).month


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
    """Bazadan o'qish; xato (asl kodda model / ustun yo'q) — None (test yiqiladi, qulamaydi)."""
    d = SessionLocal()
    try:
        return fn(d)
    except Exception:                      # noqa: BLE001
        d.rollback()
        return None
    finally:
        d.close()


def crud_fn(nom, *a, **k):
    f = getattr(crud, nom, None)
    if f is None:
        return None
    d = SessionLocal()
    try:
        return f(d, *a, **k)
    except Exception as e:                 # noqa: BLE001
        d.rollback()
        return e
    finally:
        d.close()


TG = []
main._send_telegram = lambda *a, **k: TG.append(" ".join(str(x) for x in a)) or True
BOT = []
main._tg_post_message = lambda token, chat_id, text, reply_markup=None: BOT.append((str(chat_id), text))
main._tg_javob = lambda token, chat_id, text, *a, **k: BOT.append((str(chat_id), text))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Tayyorgarlik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
s.add(Company(id=2, name="T253 Begona"))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t253_admin", PAROL, UserRole.ADMIN, "T253 Admin", company_id=1)
    auth.create_user(s, "t253_plat", PAROL, UserRole.ADMIN, "T253 Platforma", company_id=1)
    auth.create_user(s, "t253_b", PAROL, UserRole.ADMIN, "T253 B", company_id=2)
s.query(User).filter(User.username == "t253_plat").first().is_platform_admin = True
PENO = Inventory(company_id=1, item_name="T253 Peno", unit="blok", stock_quantity=100000, price_per_unit=500000, volume_per_unit=1.0,
                 is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="T253 Kley", unit="kg", stock_quantity=100000, price_per_unit=2000, category="Kimyo")
s.add_all([PENO, KLEY])
s.flush()
REC = Recipe(company_id=1, name="T253 retsept", batch_size_kg=100.0)
s.add(REC)
s.flush()
s.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
U1 = Master(company_id=1, name="Qotgan usta", phone="+998931110001", telegram_id="5301", kpi_percent=10.0, is_active=True)
U2 = Master(company_id=1, name="Ikkinchi usta", phone="+998931110002", kpi_percent=5.0, is_active=True)
UB = Master(company_id=2, name="Begona usta", phone="+998931110003", kpi_percent=7.0, is_active=True)
s.add_all([U1, U2, UB])
s.commit()
ID = {"peno": PENO.id, "rec": REC.id, "u1": U1.id, "u2": U2.id, "ub": UB.id}
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t253_admin")
CP = mijoz("t253_plat")
CB = mijoz("t253_b")
NC = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_pn = [0]


def loyiha():
    _pn[0] += 1
    d = SessionLocal()
    try:
        p = Project(company_id=1, client_name=f"T253 mijoz {_pn[0]}", project_name=f"T253 loyiha {_pn[0]}", total_budget=0, total_paid=0)
        d.add(p)
        d.commit()
        return p.id
    finally:
        d.close()


def buyurtma(mid, narx=500000, uzunlik=10):
    t = {"project_id": loyiha(), "order_type": "product", "loy_kg": 10, "recipe_id": ID["rec"],
         "items": [{"name": "D253", "category": "profil", "width": 20, "thickness": 10, "length": uzunlik, "quantity": 1,
                    "unit_price": narx, "is_coated": True, "penoplast_id": ID["peno"], "recipe_id": ID["rec"]}]}
    if mid:
        t["master_id"] = mid
    with contextlib.redirect_stdout(io.StringIO()):
        r = CA.post("/api/orders", json=t, params={"confirm_shortage": "true"})
    return js(r).get("id")


def tayyor(oid):
    with contextlib.redirect_stdout(io.StringIO()):
        return CA.post(f"/api/orders/{oid}/ready", params={"loy_kg": "10"})


def foiz(oid):
    return bazadan(lambda d: d.get(Order, oid).usta_kpi_foizi)


def foyda(oid):
    return float(js(CA.get(f"/api/orders/{oid}/profit")).get("foyda") or 0)


def kpi_put(mid, p):
    return CA.put(f"/api/masters/{mid}/kpi", json={"kpi_percent": p}).status_code


def bot_yillik(mid):
    return round(bazadan(lambda d: crud.get_master_yearly_cashback(d, mid, YIL, company_id=1)["jami_bonus"]) or 0)


def kpi_sahifa(mid):
    x = [m for m in js(CA.get(f"/api/masters/kpi-report?year={YIL}")).get("masters", []) if m.get("id") == mid]
    return x[0].get("gift_amount") if x else None


def oylik(mid):
    nom = bazadan(lambda d: d.get(Master, mid).name)
    k = bazadan(lambda d: services.calculate_monthly_master_kpi(d, YIL, OY, company_id=1)) or {}
    x = [b for b in (k.get("breakdown") or []) if b.get("master_name") == nom]
    return x[0].get("kpi_amount") if x else 0


def tafsilot(mid):
    return sum(r.get("kpi_amount") or 0 for r in js(CA.get(f"/api/masters/{mid}/kpi-detail?year={YIL}")) or [])


O1 = buyurtma(ID["u1"])
_r1 = tayyor(O1)
F1 = foyda(O1)
K1 = round(F1 * 0.10)
check("S1 tayyorgarlik: usta 10 %, buyurtma «Tayyor» (200), foyda > 0", O1 and _r1.status_code == 200 and F1 > 0, (O1, _r1.status_code, F1))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. KPI foizi «Tayyor» paytida qotadi (egasi QARORI 04.11 «Faqat yangilari»)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("Q1 «Tayyor» buyurtmada foiz qotdi — 10", foiz(O1) == 10.0, foiz(O1))
_q2a = (bot_yillik(ID["u1"]), kpi_sahifa(ID["u1"]), oylik(ID["u1"]), tafsilot(ID["u1"]))
_kp = kpi_put(ID["u1"], 20)
_q2b = (bot_yillik(ID["u1"]), kpi_sahifa(ID["u1"]), oylik(ID["u1"]), tafsilot(ID["u1"]))
check("Q2 foiz 10 → 20: bot / KPI sahifasi / oylik «Usta bonusi» / tafsilot — o'zgarmadi (asl: hammasi ×2)",
      _kp == 200 and _q2a == (K1, K1, K1, K1) and _q2b == _q2a, (_kp, _q2a, _q2b, K1))
O2 = buyurtma(ID["u1"])
tayyor(O2)
F2 = foyda(O2)
K2 = round(F2 * 0.20)
check("Q3 yangi buyurtma «Tayyor» — yangi foizda (20); yig'indi = 10 % × F1 + 20 % × F2 (har joyda)",
      foiz(O2) == 20.0 and abs(bot_yillik(ID["u1"]) - (K1 + K2)) <= 1 and abs(kpi_sahifa(ID["u1"]) - (K1 + K2)) <= 1
      and abs(oylik(ID["u1"]) - (K1 + K2)) <= 1 and abs(tafsilot(ID["u1"]) - (K1 + K2)) <= 1,
      (foiz(O2), bot_yillik(ID["u1"]), kpi_sahifa(ID["u1"]), oylik(ID["u1"]), tafsilot(ID["u1"]), K1 + K2))
kpi_put(ID["u1"], 0)
check("Q4 hozirgi foizi 0 bo'lsa ham oldingi buyurtmalar keshbegi qoladi (oylik hisobot ro'yxatida usta bor)",
      abs(bot_yillik(ID["u1"]) - (K1 + K2)) <= 1 and abs(oylik(ID["u1"]) - (K1 + K2)) <= 1, (bot_yillik(ID["u1"]), oylik(ID["u1"])))
kpi_put(ID["u1"], 10)


def usta_qoy(oid, mid):
    d = SessionLocal()
    try:
        o = d.get(Order, oid)
        o.master_id = mid
        d.commit()
    finally:
        d.close()


O3 = buyurtma(None)
tayyor(O3)
_a = foiz(O3)
usta_qoy(O3, ID["u2"])
check("Q5 ustasiz «Tayyor» — foiz NULL; keyin usta qo'yildi — o'sha ustaning foizi (5)", _a is None and foiz(O3) == 5.0, (_a, foiz(O3)))
usta_qoy(O3, ID["u1"])
check("Q6 «Tayyor» buyurtmada usta almashdi — yangi ustaning foizi (10)", foiz(O3) == 10.0, foiz(O3))


def holat_qoy(oid, st):
    d = SessionLocal()
    try:
        d.get(Order, oid).status = st
        d.commit()
    finally:
        d.close()


holat_qoy(O3, OrderStatus.IN_PROGRESS)
_b = foiz(O3)
kpi_put(ID["u1"], 12)
holat_qoy(O3, OrderStatus.READY)
check("Q7 «Tayyor» dan chiqdi — NULL; qayta «Tayyor» — o'sha paytdagi foiz (12)", _b is None and foiz(O3) == 12.0, (_b, foiz(O3)))
holat_qoy(O3, OrderStatus.CANCELLED)
kpi_put(ID["u1"], 10)


def sotuv(mid, summa=200000, tannarx=50000):
    d = SessionLocal()
    try:
        x = FinishedProductSale(company_id=1, product_name="T253 tayyor", quantity=1, unit="dona", unit_price=summa,
                                total_amount=summa, cost_amount=tannarx, master_id=mid, sold_at=datetime.utcnow())
        d.add(x)
        d.commit()
        return x.id
    finally:
        d.close()


S1 = sotuv(ID["u2"])
_s1 = bazadan(lambda d: d.get(FinishedProductSale, S1).usta_kpi_foizi)
kpi_put(ID["u2"], 9)
check("Q8 tayyor mahsulot sotuvi — foiz sotuv paytida qotdi (5); foiz 9 ga o'zgarsa ham sotuv keshbegi 5 % da (7 500)",
      _s1 == 5.0 and bot_yillik(ID["u2"]) == 7500, (_s1, bot_yillik(ID["u2"])))
kpi_put(ID["u2"], 5)


def null_qil():
    from sqlalchemy import update
    import database
    with database.engine.begin() as c:
        c.execute(update(Order).where(Order.id == O1).values(usta_kpi_foizi=None))
        c.execute(update(FinishedProductSale).where(FinishedProductSale.id == S1).values(usta_kpi_foizi=None))


_m = None
try:
    null_qil()
    kpi_put(ID["u1"], 15)
    _m = main._migrate_kpi_qotir253() if hasattr(main, "_migrate_kpi_qotir253") else None
except Exception as e:                     # noqa: BLE001
    _m = e
check("Q9 migratsiya: qotmagan (NULL) «Tayyor» buyurtma / sotuv — ustaning HOZIRGI foizida qotadi; qayta ishga tushirish — 0 ta",
      isinstance(_m, dict) and _m.get("buyurtma", 0) >= 1 and _m.get("sotuv", 0) >= 1 and foiz(O1) == 15.0
      and bazadan(lambda d: d.get(FinishedProductSale, S1).usta_kpi_foizi) == 5.0
      and main._migrate_kpi_qotir253() == {"buyurtma": 0, "sotuv": 0}, (_m, foiz(O1)))
d0 = SessionLocal()
d0.get(Order, O1).usta_kpi_foizi = 10.0
d0.commit()
d0.close()
kpi_put(ID["u1"], 10)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. «Tayyor» javobi va sovg'a davri")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
O4 = buyurtma(ID["u2"])
_r4 = tayyor(O4)
_mk = js(_r4).get("master_kpi") or {}
check("H1 «Tayyor» javobidagi master_kpi — qotgan foizda (5 %) va foyda × 5 %", _mk.get("kpi_percent") == 5.0
      and abs(_mk.get("total_kpi", -1) - round(foyda(O4) * 0.05)) <= 1 and foiz(O4) == 5.0, (_mk, foiz(O4)))
_iid4 = bazadan(lambda d: d.query(models.OrderItem.id).filter(models.OrderItem.order_id == O4).scalar())
kpi_put(ID["u2"], 9)
with contextlib.redirect_stdout(io.StringIO()):
    _rr = CA.post("/api/returns", json={"order_id": O4, "order_item_id": _iid4, "item_name": "x", "quantity": 2, "unit": "m",
                                        "reason": "Ortiqcha", "refund_amount": 100000, "to_stock": True})
    _rid = js(_rr).get("id")
    _rf = CA.post(f"/api/returns/{_rid}/refund").status_code if _rid else None
_rows = js(CA.get(f"/api/masters/{ID['u2']}/kpi-detail?year={YIL}")) or []
_qr = [x for x in _rows if "↩" in (x.get("order_number") or "")]
check("H2 qaytarish (foiz 5 → 9 dan keyin) — o'sha buyurtma QOTGAN foizida (5 %): tafsilot qatori, bot / KPI sahifasi / oylik yig'indisi",
      _rr.status_code == 200 and _rf == 200 and _qr and (_qr[0].get("profit") or 0) != 0
      and _qr[0].get("kpi_amount") == round(_qr[0]["profit"] * 5 / 100)
      and abs(bot_yillik(ID["u2"]) - sum(x.get("kpi_amount") or 0 for x in _rows)) <= 2
      and abs(kpi_sahifa(ID["u2"]) - bot_yillik(ID["u2"])) <= 1 and abs(oylik(ID["u2"]) - bot_yillik(ID["u2"])) <= 1,
      (_rr.status_code, _rr.text[:200], _rf, _qr, bot_yillik(ID["u2"]), kpi_sahifa(ID["u2"]), oylik(ID["u2"])))
kpi_put(ID["u2"], 5)
K_U2 = bot_yillik(ID["u2"])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. «Keshbek berildi» — usullar, chegaralar, kassa / to'lov, o'chirish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
KB = "/api/masters/{}/keshbek"
_h0 = js(CA.get(KB.format(ID["u1"])))
YOZ1 = K1 + K2
check("B1 holat: yozilgan = barcha yillar keshbegi (bot bilan AYNAN), berilgan 0, qoldiq = yozilgan, joriy yil ro'yxatda",
      abs(_h0.get("yozilgan", -1) - YOZ1) <= 1 and _h0.get("berilgan") == 0 and _h0.get("qoldiq") == _h0.get("yozilgan")
      and any(y.get("yil") == YIL for y in _h0.get("yillar") or []), _h0)


def ber(mid, tana, c=None):
    return (c or CA).post(KB.format(mid), json=tana)


def kassa(mid=None):
    return bazadan(lambda d: [(float(x.amount), x.category, x.hisob_id) for x in d.query(CashTransaction)
                              .filter(CashTransaction.company_id == 1).order_by(CashTransaction.id).all()]) or []


_kz = len(kassa())
r = ber(ID["u1"], {"summa": 10000, "usul": "naqd", "hisob": "karta", "izoh": "qo'lga"})
_d = js(r)
_d["holat"] = js(CA.get(KB.format(ID["u1"])))
_karta = bazadan(lambda d: [h.id for h in crud.pul_hisoblari(d, 1) if h.turi == "karta"][0])
_k = kassa()
check("B2 naqd (Karta hisobidan) 10 000 — 200; «Usta KPI to'landi» −10 000 Karta dan; berilgan 10 000, qoldiq kamaydi",
      r.status_code == 200 and len(_k) == _kz + 1 and _k[-1] == (-10000.0, "usta_kpi", _karta)
      and (_d.get("holat") or {}).get("berilgan") == 10000 and abs((_d.get("holat") or {}).get("qoldiq", 0) - (YOZ1 - 10000)) <= 1,
      (r.status_code, r.text[:300], _k[-1:], _karta))
_kid_naqd = _d.get("id")
r = ber(ID["u1"], {"summa": YOZ1, "usul": "naqd"})
check("B3 qoldiqdan ko'p — 409, hech narsa yozilmadi", r.status_code == 409 and len(kassa()) == _kz + 1
      and js(CA.get(KB.format(ID["u1"]))).get("berilgan") == 10000, (r.status_code, r.text[:200]))
O5 = buyurtma(None, narx=300000)
_raqam5 = bazadan(lambda d: d.get(Order, O5).order_number)
_qarz5 = bazadan(lambda d: float(d.get(Order, O5).debt_amount))
d0 = SessionLocal()
d0.get(Order, O5).status = OrderStatus.IN_PROGRESS
d0.commit()
d0.close()
_naqd = bazadan(lambda d: [h.id for h in crud.pul_hisoblari(d, 1) if h.turi == "naqd"][0])
r = ber(ID["u1"], {"summa": 15000, "usul": "buyurtma", "buyurtma": _raqam5})
_d = js(r)
_pay = bazadan(lambda d: [(float(p.amount), p.hisob_id, p.notes) for p in d.query(Payment).filter(Payment.order_id == O5).all()]) or []
_k = kassa()
check("B4 buyurtma to'loviga 15 000 — buyurtmaga +15 000 to'lov («Keshbek hisobidan», Naqd pul), o'sha hisobdan −15 000 «Usta KPI "
      "to'landi» (kassada sof 0); qarz 15 000 ga kamaydi; narx o'zgarmadi",
      r.status_code == 200 and len(_pay) == 1 and _pay[0][0] == 15000.0 and _pay[0][1] == _naqd and "Keshbek hisobidan" in (_pay[0][2] or "")
      and _k[-1] == (-15000.0, "usta_kpi", _naqd)
      and abs(bazadan(lambda d: float(d.get(Order, O5).debt_amount)) - (_qarz5 - 15000)) < 0.01
      and abs(bazadan(lambda d: float(d.get(Order, O5).total_amount)) - 300000) < 0.01, (r.status_code, r.text[:300], _pay, _k[-1:]))
_kid_buy = _d.get("id")
_pid = bazadan(lambda d: d.query(Payment.id).filter(Payment.order_id == O5).scalar())
r = ber(ID["u1"], {"summa": 5000, "usul": "buyurtma", "buyurtma": "YOQ-999"})
r2 = ber(ID["u2"], {"summa": min(K_U2, 1000), "usul": "buyurtma", "buyurtma": _raqam5})
check("B5 yo'q buyurtma — 404; ikkinchi to'lov (boshqa usta) qarz ichida — 200", r.status_code == 404 and r2.status_code == 200,
      (r.status_code, r2.status_code, r2.text[:200]))
O6 = buyurtma(None, narx=20000, uzunlik=1)
d0 = SessionLocal()
d0.get(Order, O6).status = OrderStatus.IN_PROGRESS
d0.commit()
_raqam6 = d0.get(Order, O6).order_number
_qarz6 = float(d0.get(Order, O6).debt_amount)
d0.close()
r = ber(ID["u1"], {"summa": _qarz6 + 1, "usul": "buyurtma", "buyurtma": _raqam6})
check("B6 buyurtma qarzidan ko'p — 409 (to'lov yozilmadi)", r.status_code == 409
      and bazadan(lambda d: d.query(Payment).filter(Payment.order_id == O6).count()) == 0, (r.status_code, r.text[:200], _qarz6))
d0 = SessionLocal()
d0.get(Order, O6).status = OrderStatus.CANCELLED
d0.commit()
d0.close()
r = ber(ID["u1"], {"summa": 100, "usul": "buyurtma", "buyurtma": _raqam6})
check("B7 bekor qilingan buyurtmaga — 409", r.status_code == 409, (r.status_code, r.text[:200]))
_kz = len(kassa())
_kecha = (tashkent_date() - timedelta(days=30)).isoformat()
r = ber(ID["u1"], {"summa": 2000, "usul": "oldin", "sana": _kecha, "izoh": "2026 yozida"})
_tar = js(CA.get(KB.format(ID["u1"]))).get("tarix") or []
check("B8 oldin berilgan (sana bilan) — kassaga TA'SIR YO'Q; tarixda sana / usul / izoh",
      r.status_code == 200 and len(kassa()) == _kz and _tar and any(x.get("usul") == "oldin" and (x.get("sana") or "").startswith(
          (datetime.fromisoformat(_kecha + "T07:00:00")).strftime("%Y-%m-%d")) and x.get("izoh") == "2026 yozida" for x in _tar),
      (r.status_code, r.text[:200], _tar[:2]))
_ert = (tashkent_date() + timedelta(days=2)).isoformat()
_bad = [ber(ID["u1"], t).status_code for t in (
    {"summa": True, "usul": "naqd"}, {"summa": "100", "usul": "naqd"}, {"summa": -5, "usul": "naqd"}, {"summa": 0, "usul": "naqd"},
    {"summa": 1.234, "usul": "naqd"}, {"summa": float("1e15"), "usul": "naqd"}, {"summa": 100, "usul": "chegirma"},
    {"summa": 100, "usul": "naqd", "x": 1}, {"summa": 100, "usul": "oldin", "sana": _ert}, {"summa": 100, "usul": "oldin", "sana": "04.11.2026"},
    {"summa": 100, "usul": "naqd", "sana": _kecha}, {"summa": 100, "usul": "oldin", "hisob": "naqd"},
    {"summa": 100, "usul": "naqd", "buyurtma": _raqam5}, {"summa": 100, "usul": "naqd", "izoh": "x" * 201})]
check("B9 noto'g'ri tana (bool / matn / manfiy / 0 / 3 xona kasr / juda katta / noma'lum usul / ortiqcha kalit / ertangi sana / sana "
      "shakli / usulga mos bo'lmagan maydon / uzun izoh) — hammasi 400", _bad == [400] * 14, _bad)
_n0 = bazadan(lambda d: d.query(UstaKeshbek).count())
r1 = ber(ID["u1"], {"summa": 777, "usul": "naqd"})
r2 = ber(ID["u1"], {"summa": 777, "usul": "naqd"})
check("B10 takror yuborish (8 s ichida aynan shu) — ikkinchisi `duplicate: true`, bitta yozuv", r1.status_code == 200
      and js(r2).get("duplicate") is True and bazadan(lambda d: d.query(UstaKeshbek).count()) == (_n0 or 0) + 1, (r1.text[:150], r2.text[:150]))
r = CA.delete(f"/api/payments/{_pid}")
_ctx = bazadan(lambda d: d.query(UstaKeshbek.cash_tx_id).filter(UstaKeshbek.id == _kid_naqd).scalar())
r2 = CA.delete(f"/api/finance/cash-transactions/{_ctx}")
check("B11 keshbekka bog'langan to'lovni / kassa yozuvini alohida o'chirish — 409 (o'chmadi)", r.status_code == 409 and r2.status_code == 409
      and bazadan(lambda d: d.get(Payment, _pid) is not None and d.get(CashTransaction, _ctx) is not None), (r.status_code, r2.status_code))
_h1 = js(CA.get(KB.format(ID["u1"])))
r = CA.delete(f"/api/masters/keshbek/{_kid_buy}")
_h2 = js(CA.get(KB.format(ID["u1"])))
check("B12 keshbek yozuvini o'chirish — to'lov va kassa yozuvi birga o'chdi, buyurtma qarzi qaytdi, qoldiq +15 000",
      r.status_code == 200 and bazadan(lambda d: d.get(Payment, _pid)) is None
      and abs(_h2.get("qoldiq", 0) - (_h1.get("qoldiq", 0) + 15000)) < 0.01
      and abs(bazadan(lambda d: float(d.get(Order, O5).debt_amount)) - (_qarz5 - min(K_U2, 1000))) < 0.01, (r.status_code, r.text[:200], _h1, _h2))
_log = bazadan(lambda d: [(a.action, a.new_value) for a in d.query(ActivityLog).filter(ActivityLog.action == "keshbek_berildi").all()]) or []
check("B13 jurnal: «keshbek_berildi» (AUDIT_AMALLARI da), matnda summa, usul, qoldiq", "keshbek_berildi" in crud.AUDIT_AMALLARI
      and _log and "10 000" in _log[0][1] and "qoldiq" in _log[0][1], _log[:2])
BOT.clear()
try:
    with contextlib.redirect_stdout(io.StringIO()):
        main._usta_boti_javobi({"update_id": 1, "message": {"message_id": 1, "date": 1, "text": "💰 Bonuslarim",
                                                           "from": {"id": 5301, "is_bot": False, "first_name": "U"},
                                                           "chat": {"id": 5301, "type": "private"}}}, "123:soxta", korxona_id=1)
except Exception as _e:                    # noqa: BLE001
    BOT.append(("xato", repr(_e)))
_qol = js(CA.get(KB.format(ID["u1"]))).get("qoldiq")
check("B14 bot «Bonuslarim» — «Olinmagan qoldiq» qatori (kabinet bilan bitta hisob)",
      any("Olinmagan qoldiq" in x[1] and services.son_korinish(int(round(_qol or 0)), 0) in x[1] for x in BOT), (BOT[-1:], _qol))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. review253 tuzatishlari (H1, M3, M4, L1, L3, L4, L5)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
OR1 = buyurtma(None, narx=200000, uzunlik=4)
d0 = SessionLocal()
d0.get(Order, OR1).status = OrderStatus.IN_PROGRESS
_rq1 = d0.get(Order, OR1).order_number
d0.commit()
d0.close()
r = ber(ID["u1"], {"summa": 3000, "usul": "buyurtma", "buyurtma": _rq1})
_kr1 = js(r).get("id")
_pr1 = bazadan(lambda d: d.query(Payment.id).filter(Payment.order_id == OR1).scalar())
with contextlib.redirect_stdout(io.StringIO()):
    _rd = CA.delete(f"/api/orders/{OR1}")
_rp = CA.delete(f"/api/orders/{OR1}/permanent")
check("R1 (H1) keshbek to'lovli (hech narsa topshirilmagan) buyurtmani o'chirish — YUMSHOQ (to'lov saqlandi); «Butunlay o'chirish» — 409",
      _rd.status_code == 200 and js(_rd).get("soft_deleted") is True and bazadan(lambda d: d.get(Payment, _pr1)) is not None
      and _rp.status_code == 409 and bazadan(lambda d: d.get(Order, OR1)) is not None, (_rd.status_code, _rd.text[:200], _rp.status_code))
CA.delete(f"/api/masters/keshbek/{_kr1}")
_rp2 = CA.delete(f"/api/orders/{OR1}/permanent")
check("R2 (H1) keshbek yozuvi o'chirilgach — butunlay o'chirish 200", _rp2.status_code == 200 and bazadan(lambda d: d.get(Order, OR1)) is None,
      (_rp2.status_code, _rp2.text[:200]))
OA, OB = buyurtma(None, narx=100000, uzunlik=2), buyurtma(None, narx=100000, uzunlik=2)
d0 = SessionLocal()
for _o in (OA, OB):
    d0.get(Order, _o).status = OrderStatus.IN_PROGRESS
_ra, _rb = d0.get(Order, OA).order_number, d0.get(Order, OB).order_number
d0.commit()
d0.close()
_r = [ber(ID["u1"], {"summa": 500, "usul": "buyurtma", "buyurtma": _ra}), ber(ID["u1"], {"summa": 500, "usul": "buyurtma", "buyurtma": _rb}),
      ber(ID["u1"], {"summa": 600, "usul": "naqd", "hisob": "naqd"}), ber(ID["u1"], {"summa": 600, "usul": "naqd", "hisob": "bank"}),
      ber(ID["u1"], {"summa": 700, "usul": "oldin", "sana": _kecha}), ber(ID["u1"], {"summa": 700, "usul": "oldin"})]
check("R3 (M3) bir xil summa, boshqa buyurtma / hisob / sana — har biri ALOHIDA yozuv (takror emas); ikkala buyurtmaga to'lov",
      [x.status_code for x in _r] == [200] * 6 and not any(js(x).get("duplicate") for x in _r)
      and bazadan(lambda d: [d.query(Payment).filter(Payment.order_id == x).count() for x in (OA, OB)]) == [1, 1],
      [(x.status_code, js(x).get("duplicate")) for x in _r])
check("R4 (L5) POST javobida hisob tafsiloti yo'q (yillar / foiz / tarix) — faqat id, takror, qoldiq",
      set(js(_r[0])) == {"status", "id", "duplicate", "qoldiq"} and isinstance(js(_r[0]).get("qoldiq"), (int, float)), js(_r[0]))
_bd = bazadan(lambda d: services.calculate_monthly_master_kpi(d, YIL, OY, company_id=1)["breakdown"]) or []
_bdm = {b["master_name"]: b.get("kpi_percent") for b in _bd}
check("R5 (L1) oylik «Usta bonusi» qatorida foiz — hodisalarning QOTGAN foizi (bitta — o'zi, aralash 10 / 20 — None)",
      _bdm.get("Qotgan usta") is None and _bdm.get("Ikkinchi usta") == 5.0, _bd)
_qq = js(CA.get("/api/masters/kpi-keshbek")).get("qoldiqlar") or {}
_hh = {str(m): js(CA.get(KB.format(m))).get("qoldiq") for m in (ID["u1"], ID["u2"])}
check("R6 (L3) KPI sahifasi qoldiqlari (yil hisoboti orqali) — har usta holati bilan AYNAN", all(_qq.get(k) == v for k, v in _hh.items()),
      (_qq, _hh))
# M4: sovg'a davri yopilganda o'tkazma — har hodisa QOTGAN foizida
UG = bazadan(lambda d: d.query(Master.id).filter(Master.name == "Ikkinchi usta").scalar())
_op = bazadan(lambda d: crud.open_gift_period(d, [{"gift_name": "Sovg'a", "threshold_amount": 999999999}], master_ids=[UG], company_id=1))
OG = buyurtma(UG)
tayyor(OG)
_fg = foyda(OG)
kpi_put(UG, 50)
_cl = bazadan(lambda d: crud.close_gift_period(d, force=True, company_id=1))
_cv = bazadan(lambda d: [float(x.profit_amount) for x in d.query(models.MasterGiftPeriodRedemption)
                         .filter(models.MasterGiftPeriodRedemption.kind == "cashback_conversion",
                                 models.MasterGiftPeriodRedemption.master_id == UG).all()])
check("R7 (M4) sovg'a davri yopildi (foiz 5 → 50 dan keyin) — keshbekka o'tkazma = davr foydasi × QOTGAN 5 %",
      (_op or {}).get("success") is not False and (_cl or {}).get("success") is True and _cv and abs(_cv[-1] - round(_fg * 0.05, 2)) <= 1,
      (_op, _cl, _cv, _fg))
kpi_put(UG, 5)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Usta hisobi tasdig'ida tasdiqdan oldingi buyurtmalari ustaga bog'lanadi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
_sq = [0]


def sayt_bog(mj, oid, ulgurji=None):
    _sq[0] += 1
    d = SessionLocal()
    try:
        b = DokonBuyurtma(company_id=1, sb_seq=900 + _sq[0], sb_raqam=f"S-{9000 + _sq[0]}", sb_kalit=f"k253-{_sq[0]:04d}" + "x" * 20,
                          sb_tana_xesh="x" * 64, sb_mijoz="Usta", sb_telefon="+998901112233", sb_viloyat="andijon", sb_jami=100000,
                          sb_chegirmasiz=100000, sb_holat="tasdiqlandi", order_id=oid, mijoz_id=mj, sb_ulgurji=ulgurji)
        d.add(b)
        d.commit()
        return b.sb_raqam
    finally:
        d.close()


d0 = SessionLocal()
MJ = DokonMijoz(company_id=1, mj_tg_id="7253", mj_telefon="+998901112233", mj_ism="Kutgan Usta", mj_turi="usta", mj_holat="kutilmoqda")
d0.add(MJ)
d0.commit()
MJ_ID = MJ.id
d0.close()
OT1 = buyurtma(None)
tayyor(OT1)
OT2 = buyurtma(None)
OT3 = buyurtma(ID["u2"])
OT4 = buyurtma(None)
R_T1, R_T2 = sayt_bog(MJ_ID, OT1), sayt_bog(MJ_ID, OT2)
sayt_bog(MJ_ID, OT3)
sayt_bog(MJ_ID, OT4, ulgurji=True)
r = CA.post(f"/api/sayt-katalogi/mijozlar/{MJ_ID}/tasdiqla", json={"kpi": 4, "yangi_usta": True})
UY = bazadan(lambda d: d.get(DokonMijoz, MJ_ID).master_id)
_ms = bazadan(lambda d: [d.get(Order, x).master_id for x in (OT1, OT2, OT3, OT4)])
check("T1 tasdiq — ustasiz «Tayyor» va jarayondagi buyurtmalar YANGI ustaga bog'landi; boshqa ustaniki va ulgurji — tegilmadi",
      r.status_code == 200 and UY and _ms == [UY, UY, ID["u2"], None], (r.status_code, r.text[:200], UY, _ms))
check("T2 tasdiqdan oldin «Tayyor» bo'lgan buyurtma — foiz tasdiqda kiritilgan KPI da (4) qotdi, keshbek yozildi",
      foiz(OT1) == 4.0 and abs(bot_yillik(UY) - round(foyda(OT1) * 0.04)) <= 1, (foiz(OT1), bot_yillik(UY)))
_jr = bazadan(lambda d: [a.new_value for a in d.query(ActivityLog).filter(ActivityLog.action == "dokon_tasdiq").all()]) or []
check("T3 jurnal: «tasdiqdan oldingi 2 ta buyurtmasi ustaga bog'landi»", any("2 ta buyurtmasi ustaga bog'landi" in (x or "") for x in _jr), _jr[-1:])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Do'kon kabineti — GET /api/dokon/v1/mijoz/keshbek")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
KALIT = js(CA.post("/api/sayt-katalogi/api-kalit", json={})).get("kalit") or ""


def sessiya(mid):
    d = SessionLocal()
    try:
        m = d.get(DokonMijoz, mid)
        t = crud._dk_sessiya_yarat(d, m, datetime.utcnow())
        d.commit()
        return t
    finally:
        d.close()


def kab(ses, kalit=None):
    for _n in ("_DOKON_API_CHEKLOV", "_DOKON_MIJOZ_CHEKLOV"):
        _ch = getattr(crud, _n, None)
        if _ch is not None:
            _ch.tozala()
    h = {"X-Dokon-Kalit": KALIT if kalit is None else kalit}
    if ses is not None:
        h["X-Mijoz-Sessiya"] = ses
    return NC.get("/api/dokon/v1/mijoz/keshbek", headers=h)


SES = sessiya(MJ_ID)
CA.post(KB.format(UY), json={"summa": 100, "usul": "naqd"})
r = kab(SES)
d = js(r)
_kb = d.get("keshbek") or {}
check("D1 tasdiqlangan usta — 200, no-store; yozilgan / berilgan / qoldiq (ERP holati bilan AYNAN)",
      r.status_code == 200 and "no-store" in r.headers.get("cache-control", "")
      and _kb == {k: js(CA.get(KB.format(UY))).get(k) for k in ("yozilgan", "berilgan", "qoldiq")} and _kb.get("berilgan") == 100,
      (r.status_code, r.text[:300]))
check("D2 buyurtmalar: «Tayyor» — keshbek summasi (foyda × 4 %), jarayondagi — «kutilmoqda» (summasiz); boshqa ustaniki / ulgurji — YO'Q",
      (d.get("buyurtmalar") or {}).get(R_T1, {}).get("keshbek") == round(foyda(OT1) * 0.04)
      and (d.get("buyurtmalar") or {}).get(R_T2) == {"keshbek": None, "holat": "kutilmoqda"} and len(d.get("buyurtmalar") or {}) == 2, d)
check("D3 javobda foyda / KPI % / ERP buyurtma raqami / usta id YO'Q; tarixda sana, summa, usul nomi",
      "foyda" not in r.text and "kpi" not in r.text.lower() and "ORD-" not in r.text and "master" not in r.text
      and (d.get("tarix") or [{}])[0].get("summa") == 100 and (d.get("tarix") or [{}])[0].get("usul"), r.text[:400])
check("D4 sessiyasiz / yaroqsiz sessiya — 401; kalitsiz — 401", kab(None).status_code == 401 and kab("pds_" + "A" * 43).status_code == 401
      and kab(SES, kalit="").status_code == 401, (kab(None).status_code, kab("pds_" + "A" * 43).status_code))
d0 = SessionLocal()
MJ2 = DokonMijoz(company_id=1, mj_tg_id="7254", mj_telefon="+998901112244", mj_ism="Magazin", mj_turi="magazin", mj_holat="tasdiqlangan",
                 mj_magazin="Do'kon", mj_shahar="Asaka")
MJ3 = DokonMijoz(company_id=1, mj_tg_id="7255", mj_telefon="+998901112255", mj_ism="Kutgan2", mj_turi="usta", mj_holat="kutilmoqda")
d0.add_all([MJ2, MJ3])
d0.commit()
_m2, _m3 = MJ2.id, MJ3.id
d0.close()
_r2, _r3 = js(kab(sessiya(_m2))), js(kab(sessiya(_m3)))
check("D5 magazin va tasdiqlanmagan usta — keshbek null (raqamlar yo'q)", _r2.get("keshbek") is None and _r2.get("turi") == "magazin"
      and _r3.get("keshbek") is None and _r3.get("holat") == "kutilmoqda", (_r2, _r3))

d0 = SessionLocal()
d0.get(DokonMijoz, MJ_ID).mj_holat = "kutilmoqda"          # blokdan chiqarilgan — ERP ustasi bog'lami saqlanadi, qayta tasdiq kerak
d0.commit()
d0.close()
_r6 = js(kab(SES))
check("D6 ERP ustasi bor, lekin hisob qayta tasdiq kutmoqda — keshbek null (raqamlar yo'q)", _r6.get("keshbek") is None
      and _r6.get("holat") == "kutilmoqda", _r6)
d0 = SessionLocal()
d0.get(DokonMijoz, MJ_ID).mj_holat = "tasdiqlangan"
d0.commit()
d0.close()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Ikkinchi korxona, ruxsat, sahifa, zaxira")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_z = [CB.get(KB.format(ID["u1"])).status_code, CB.post(KB.format(ID["u1"]), json={"summa": 1, "usul": "oldin"}).status_code,
      CB.delete(f"/api/masters/keshbek/{_kid_naqd}").status_code]
check("Z1 B korxonasi A ustasi keshbegini ko'ra / bera / o'chira olmaydi — 404", _z == [404, 404, 404], _z)
_q = js(CA.get("/api/masters/kpi-keshbek")).get("qoldiqlar") or {}
check("Z2 KPI sahifasi qoldiqlari — korxona ustalari (B ustasi yo'q), qiymat holat bilan AYNAN",
      str(ID["ub"]) not in _q and _q.get(str(ID["u1"])) == js(CA.get(KB.format(ID["u1"]))).get("qoldiq"), _q)
_nc = [NC.get(KB.format(ID["u1"])).status_code, NC.get("/api/masters/kpi-keshbek").status_code]
check("Z3 kirmagan — 401 / 303 (yo'llar ochiq emas)", all(x in (401, 303, 307) for x in _nc), _nc)
_html = CA.get("/kpi").text
check("Z4 /kpi sahifasida keshbek oynasi (💸, «Keshbek berildi», usullar, tarix)", all(x in _html for x in (
    'id="keshbekModal"', "openKeshbek(", "saveKeshbek()", "deleteKeshbek(", 'value="buyurtma"', 'value="oldin"', "/api/masters/kpi-keshbek")),
      "")
_bk = bazadan(lambda d: crud.export_full_backup(d, company_id=1)) or {}
_zt = (_bk.get("tables") or {}).get("usta_keshbeklar") or []
_oldin = bazadan(lambda d: sorted((r.master_id, float(r.summa), r.usul, r.izoh) for r in d.query(UstaKeshbek).filter(UstaKeshbek.company_id == 1).all()))
check("Z5 zaxirada usta_keshbeklar BOR (hamma qatorlar)", _oldin and len(_zt) == len(_oldin), (len(_zt), _oldin))
_res = bazadan(lambda d: crud.import_full_backup(d, _bk, company_id=1, replace=True)) or {}
_keyin = bazadan(lambda d: sorted((r.master_id, float(r.summa), r.usul, r.izoh) for r in d.query(UstaKeshbek).filter(UstaKeshbek.company_id == 1).all()))
check("Z6 zaxiradan tiklash — keshbek yozuvlari AYNAN qaytdi (o'tkazib yuborilmadi)",
      _res.get("success") is True and "usta_keshbeklar" not in (_res.get("skipped_tables") or []) and _keyin == _oldin, (_res, _keyin))
for _row in ((_bk.get("tables") or {}).get("orders") or []):          # zip 253 dan oldingi zaxira — ustun yo'q
    _row.pop("usta_kpi_foizi", None)
_res2 = bazadan(lambda d: crud.import_full_backup(d, _bk, company_id=1, replace=True)) or {}
check("Z6b (L4) zip 253 dan oldingi zaxira tiklandi — «Tayyor» buyurtmalar foizi darhol qotdi (NULL yo'q)",
      _res2.get("success") is True and bazadan(lambda d: d.query(Order).filter(Order.company_id == 1, Order.status == OrderStatus.READY,
                                                                              Order.master_id.isnot(None), Order.usta_kpi_foizi.is_(None)).count()) == 0
      and bazadan(lambda d: d.query(Order).filter(Order.company_id == 1, Order.status == OrderStatus.READY, Order.master_id.isnot(None)).count()) > 0,
      _res2)
bazadan(lambda d: crud.factory_reset_all_data(d, company_id=1))
check("Z7 korxona ma'lumotlarini o'chirish — keshbek yozuvlari ham o'chdi",
      bazadan(lambda d: d.query(UstaKeshbek).filter(UstaKeshbek.company_id == 1).count()) == 0, "")

if PG_URL:
    try:
        import database as _dbm253
        _dbm253.engine.dispose()
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
