#!/usr/bin/env python3
"""
test_nomdosh220.py — kech159 (zip 220 «Nomdosh detallar tahriri» — egasi tanlovi 27.10 «Tuzatish + zaxira (Tavsiya)»).

NIMA UCHUN KERAK (O'LCHANGAN — `work/k220/probe220.py` SQLite = PG, `work/k220/ui220.py` Chromium; zip 219 kodi)
  Bir buyurtmada bir xil NOMLI bir xil turdagi ikki detal («Karniz N» 60 m qoplamali 35-plotnost va «Karniz N» 30 m qoplamasiz 25-plotnost) —
  tahrir formasi detallarni saqlangan tartibga TESKARI yuboradi, server nom + tur bo'yicha birinchisiga moslardi: o'zgarishsiz saqlash — 400
  «Topshirilgan miqdordan kam qilib bo'lmaydi!»; miqdor oshirilsa — topshirilgan tarix (qoplama, plotnost) boshqa detalga o'tib, allaqachon
  bajarilgan ish bo'yicha qoplamachi / metrchi haqi kamayardi; formadagi «📦 topshirilgan» belgisi ham nom bo'yicha (ikkalasida bir xil).
BO'LIMLAR
  S — manba (sxema maydoni va chegarasi, moslash bosqichlari tartibi, forma: faqat tahrirda raqam, yuborish, belgi raqam bo'yicha).
  A — server: teskari tartib raqam bilan / raqamsiz (eski sahifa) — o'zgarishsiz saqlash 200, detallar o'z xususiyati va topshirilgani bilan;
      ×2 — har detal o'zida, hisobotdagi bajarilgan ish o'zgarmaydi; blok (bir xil birlik) ham; topshirilgan detal nomini o'zgartirish
      (raqam bilan) — tarix o'sha detalda; boshqa buyurtma detalining raqami — e'tiborsiz (u buyurtma o'zgarmaydi); turi boshqa — raqam
      bo'yicha moslanmaydi; yaratishda raqam e'tiborsiz; noto'g'ri raqam — 422; bir raqam ikki marta — ikkinchisi xususiyat bo'yicha.
  U — HAQIQIY Chromium (SQLite / TF1): tahrir qatorlarida raqam, yuborilgan tanada raqamlar, o'zgarishsiz saqlash muvaffaqiyatli, har nomdosh
      o'z «📦» belgisi bilan, yangi qatorda raqam yo'q, «Nusxa olish» — raqamsiz, JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (S + A).
Asl kodga (zip 219) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_nomdosh220.py
"""
import os
import io
import re
import sys
import json
import time
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
PG_BAZA = "nomdosh220_test"
_T = tempfile.mkdtemp(prefix="k220_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k220.db')}"
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
    import schemas                                 # noqa: E402
    import services                                # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, Master, Order, Recipe, RecipeIngredient    # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    with TestClient(main.app):
        pass

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_f = schemas.OrderItemCreate.model_fields.get("id")
check("S1 `OrderItemCreate.id` — ixtiyoriy (standart None), 1 … 2 147 483 647",
      _f is not None and _f.default is None and 'ge=1' in repr(_f.metadata) and 'le=2147483647' in repr(_f.metadata), _f)
_src = inspect.getsource(crud.update_order_full)
check("S2 `update_order_full`: avval detal RAQAMI (shu buyurtmaniki, turi o'sha), so'ng xususiyatlar («x»), blok birligi, nom + tur",
      "_eski_id220" in _src and 'for _bosqich211 in ("x", 1, 2):' in _src and _src.find("_eski_id220") < _src.find('for _bosqich211 in ("x", 1, 2):'))
check("S3 forma: raqam faqat «Tahrirlash» rejimida (`mode === 'edit' && !isDup && !isTaklif`), `collectItems` uni yuboradi, «📦» belgisi raqam bo'yicha",
      "if (mode === 'edit' && !isDup && !isTaklif && item.id) row.dataset.itemId = String(item.id);" in ORD
      and "if (Number.isFinite(_id220) && _id220 > 0) x.id = _id220;" in ORD and "_dlvRoy220.find(i => i && item.id && i.id === item.id" in ORD)

# ── ma'lumot
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k220_a", PAROL, UserRole.ADMIN, "K220 Admin", company_id=1)
P35 = Inventory(company_id=1, item_name="K220 Penoplast 35", unit="blok", stock_quantity=10_000, price_per_unit=500_000, volume_per_unit=1.0,
                is_penoplast=True, is_default_penoplast=True, category="Penoplast")
P25 = Inventory(company_id=1, item_name="K220 Penoplast 25", unit="blok", stock_quantity=10_000, price_per_unit=400_000, volume_per_unit=1.0,
                is_penoplast=True, category="Penoplast")
PRJ = Project(company_id=1, client_name="K220 mijoz", project_name="K220 loyiha", client_phone="+998901112220", total_budget=0, total_paid=0)
US = Master(company_id=1, name="K220 Usta", phone="+998900002220", kpi_percent=10)
KLEY = Inventory(company_id=1, item_name="K220 Kley", unit="kg", stock_quantity=100_000, price_per_unit=3_000, category="Kimyo")
s.add_all([P35, P25, PRJ, US, KLEY])
s.flush()
REC = Recipe(company_id=1, name="K220 Oq marmar", batch_size_kg=100.0)       # qoplamali detal — retsept majburiy (forma tekshiruvi)
s.add(REC)
s.flush()
s.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
s.commit()
ID = {"P35": P35.id, "P25": P25.id, "PRJ": PRJ.id, "US": US.id, "REC": REC.id}
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
A.post("/login", data={"username": "k220_a", "password": PAROL}, follow_redirects=False)
_r = A.put("/api/settings/categories", data={"codes": "profil,panel,dona,blok,loy_sotish,mrp_product", "v": "2"})
BUGUN = services._tashkent_date()
for _nom, _tana in (("metrchi", {"pay_type": "per_unit", "per_unit_rate": 1000, "per_unit_type": "metr"}),
                    ("qoplamachi", {"pay_type": "fixed_plus_coating", "fixed_amount": 1_000_000, "per_unit_rate": 1500, "per_unit_type": "metr"})):
    A.post("/api/employees", json=dict({"name": f"K220 {_nom}", "ishga_kirgan_sana": "2026-01-01T00:00:00"}, **_tana))


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def xabar(r):
    d = js(r)
    det = d.get("detail", d) if isinstance(d, dict) else d
    return str(det.get("message") if isinstance(det, dict) else det)[:300]


def profil(nom, L, coated, peno, narx_m=60_000, w=20, t=10):
    return {"name": nom, "category": "profil", "width": w, "thickness": t, "length": L, "quantity": 1, "unit_price": narx_m * L,
            "is_coated": coated, "penoplast_id": peno, "price_per_m3": None, "finished_product_id": None}


def blok(nom, chiqishi, kerak, coated, peno):
    bn = 600_000
    return {"name": nom, "category": "blok", "width": None, "thickness": None, "length": kerak / chiqishi, "quantity": kerak,
            "unit_price": round(bn / chiqishi * (2 if coated else 1), 2), "is_coated": coated, "penoplast_id": peno, "price_per_m3": None,
            "finished_product_id": None, "blok_birlik": "metr", "blok_chiqishi": chiqishi, "blok_narxi": None, "blok_koef": 2.0,
            "notes": f"blok_narxi={bn * (2 if coated else 1)},blok_yield={chiqishi}"}


_SANOQ = [0]


def tana(items):
    return {"project_id": ID["PRJ"], "order_type": "product", "recipe_id": ID["REC"], "master_id": ID["US"],
            "deadline": (BUGUN + datetime.timedelta(days=5)).isoformat(), "is_draft": False, "base_price": 0, "loy_kg": None, "items": items}


def yarat(items):
    _SANOQ[0] += 1
    items = list(items) + [profil(f"K220 to'ldiruvchi {_SANOQ[0]}", _SANOQ[0], False, ID["P25"])]   # 8 s takror-himoyasi o'xshatmasin
    r = A.post("/api/orders?confirm_shortage=true", json=tana(items))
    return js(r).get("id") if r.status_code == 200 else None


def topshir(oid):
    h = js(A.get(f"/api/orders/{oid}/delivery-status")).get("items") or []
    items = [{"order_item_id": x["id"], "quantity": x["remaining"]} for x in h if (x.get("remaining") or 0) > 1e-6]
    _SANOQ[0] += 1
    return A.post("/api/deliveries", json={"order_id": oid, "items": items, "received_by": "K220", "notes": f"K220 yuk {_SANOQ[0]}",
                                           "transport_carrier": "", "transport_cost": 0, "transport_payer": "client"}).status_code


def detallar(oid):
    s2 = SessionLocal()
    try:
        o = s2.get(Order, oid)
        return [{"id": it.id, "name": it.name, "cat": it.category, "coated": bool(it.is_coated), "peno": it.penoplast_id,
                 "len": round(float(it.length or 0), 4), "qty": round(float(it.quantity or 0), 4), "del": round(float(it.delivered_qty or 0), 4)}
                for it in sorted(o.items, key=lambda x: x.id)]
    finally:
        s2.close()


def body_from(oid, k=1, ids=True, teskari=True, ozgar=None):
    """Bazadagi detallardan forma kabi tana (k — miqdor ko'paytuvchisi); ozgar(dict) — detal raqami bo'yicha o'zgarishlar."""
    s2 = SessionLocal()
    try:
        o = s2.get(Order, oid)
        out = []
        for it in sorted(o.items, key=lambda x: x.id):
            if it.category == "blok":
                ch = float(it.blok_chiqishi or 1)
                d = blok(it.name, ch, float(it.quantity) * k, bool(it.is_coated), it.penoplast_id)
            else:
                L = float(it.length or 0) * k
                d = profil(it.name, L, bool(it.is_coated), it.penoplast_id, narx_m=(float(it.unit_price or 0) / float(it.length or 1)),
                           w=it.width, t=it.thickness)
            if ids:
                d["id"] = it.id
            if ozgar and it.id in ozgar:
                d.update(ozgar[it.id])
            out.append(d)
    finally:
        s2.close()
    return list(reversed(out)) if teskari else out


def put(oid, items):
    r = A.put(f"/api/orders/{oid}", json=tana(items))
    if r.status_code == 409:
        r = A.put(f"/api/orders/{oid}?confirm_shortage=true", json=tana(items))
    return r


def oy():
    try:
        services.hisobot_xotirasini_tozala()
    except Exception:                      # noqa: BLE001
        pass
    s2 = SessionLocal()
    try:
        r = services.get_monthly_report(s2, BUGUN.year, BUGUN.month, company_id=1)
        return {k: round(float(r.get(k) or 0), 2) for k in ("jami_metr", "jami_m2", "jami_blok", "qoplamachi_bonus_avtomatik",
                                                             "hodimlar_moslashuvchan_xarajat")}
    finally:
        s2.close()


def xus(d):
    return [(x["name"], x["coated"], x["peno"], x["del"]) for x in d]


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A — server: nomdosh detallar tahriri")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
O1 = yarat([profil("Karniz N", 60, True, ID["P35"]), profil("Ustun U", 20, False, ID["P35"], w=15), profil("Karniz N", 30, False, ID["P25"], narx_m=35_000)])
T1 = topshir(O1) if O1 else None
D0 = detallar(O1) if O1 else []
H0 = oy()
r = put(O1, body_from(O1))
D1 = detallar(O1)
check("A1 teskari tartib + raqamlar, hech narsa o'zgarmagan — 200; har detal o'z xususiyati, uzunligi va topshirilgani bilan (asl: 400 «Topshirilgan "
      "miqdordan kam qilib bo'lmaydi»)", O1 and T1 == 200 and r.status_code == 200 and D1 == D0, (r.status_code, xabar(r), D0, D1))
r = put(O1, body_from(O1, ids=False))
D2 = detallar(O1)
check("A2 teskari tartib RAQAMSIZ (eski ochiq sahifa) — xususiyatlar bo'yicha moslanadi: 200, o'zgarishsiz", r.status_code == 200 and D2 == D0,
      (r.status_code, xabar(r), D2))
r = put(O1, body_from(O1, k=2))
D3, H3 = detallar(O1), oy()
check("A3 ×2 (teskari + raqamlar) — har detal o'zida (qoplamali 35 — 120 m, topshirilgan 60; qoplamasiz 25 — 60 m, topshirilgan 30), id lar o'sha; "
      "hisobotdagi bajarilgan ish (metr, qoplamachi bonusi, hodimlar) tahrirda O'ZGARMAYDI (asl: tarix almashib −30 000)",
      r.status_code == 200 and [x["id"] for x in D3] == [x["id"] for x in D0] and xus(D3) == xus(D0)
      and [x["len"] for x in D3] == [x["len"] * 2 for x in D0] and H3 == H0, (r.status_code, xabar(r), D3, H0, H3))
O2 = yarat([blok("Karniz NB", 40, 60, True, ID["P35"]), blok("Karniz NB", 50, 30, False, ID["P25"])])
topshir(O2)
B0, HB0 = detallar(O2), oy()
r1 = put(O2, body_from(O2))
r2 = put(O2, body_from(O2, ids=False))
r3 = put(O2, body_from(O2, k=2))
B3, HB3 = detallar(O2), oy()
check("A4 blok (ikkala nomdosh «metr»): o'zgarishsiz (raqam bilan / raqamsiz) — 200; ×2 — har detal o'zida, hisobot o'zgarmaydi",
      r1.status_code == 200 and r2.status_code == 200 and r3.status_code == 200 and xus(B3) == xus(B0)
      and [x["qty"] for x in B3 if x["cat"] == "blok"] == [x["qty"] * 2 for x in B0 if x["cat"] == "blok"] and HB3 == HB0, (r1.status_code, r2.status_code, r3.status_code, xabar(r3), B3))
_kid = D0[0]["id"]
_d5a = detallar(O1)
r = put(O1, body_from(O1, ozgar={_kid: {"name": "Karniz N qoplamali"}}))
check("A5 TOPSHIRILGAN detal nomini o'zgartirish (raqam bilan ham) — avvalgidek 400 (raqam faqat nomdoshlarni ajratadi; review220 №2: yuk xati "
      "nomi o'zgarmasin), hech narsa o'zgarmadi", r.status_code == 400 and detallar(O1) == _d5a, (r.status_code, xabar(r), detallar(O1)))
O5 = yarat([profil("Yangi Z", 10, False, ID["P25"])])
_z5 = detallar(O5)[0]
r = put(O5, [dict(profil("Yangi Z2", 10, False, ID["P25"]), id=_z5["id"])] + [dict(x) for x in body_from(O5) if x["name"] != "Yangi Z"])
_d5b = detallar(O5)
check("A5b topshirilmagan detal nomi o'zgartirildi (raqam bilan) — avvalgidek: eski detal o'rniga yangi nomli detal (200)",
      r.status_code == 200 and any(x["name"] == "Yangi Z2" for x in _d5b) and not any(x["name"] == "Yangi Z" for x in _d5b),
      (r.status_code, xabar(r), _d5b))
O3 = yarat([profil("Boshqa B", 10, True, ID["P35"])])
D3o = detallar(O3)
_beg = body_from(O1)
_beg.append(dict(profil("Begona", 5, False, ID["P25"]), id=D3o[0]["id"]))
r = put(O1, _beg)
D6 = detallar(O1)
check("A6 boshqa buyurtma detalining raqami — e'tiborsiz: u buyurtma o'zgarmadi, bu buyurtmaga yangi detal qo'shildi (yangi raqam bilan)",
      r.status_code == 200 and detallar(O3) == D3o and any(x["name"] == "Begona" and x["id"] != D3o[0]["id"] for x in D6), (r.status_code, xabar(r), D6))
_ust = next(x for x in D0 if x["name"] == "Ustun U")
_b7 = [x for x in body_from(O1) if x.get("name") != "Begona"]
for x in _b7:
    if x.get("id") == _ust["id"]:
        x.pop("id")
_b7.append({"id": _ust["id"], "name": "Yangi dona", "category": "dona", "width": 10, "thickness": 10, "length": 2, "quantity": 4, "unit_price": 10_000,
            "is_coated": False, "penoplast_id": ID["P25"], "price_per_m3": None, "finished_product_id": None, "notes": "dona_yield=2"})
r = put(O1, _b7)
D7 = detallar(O1)
_u7 = next((x for x in D7 if x["id"] == _ust["id"]), {})
check("A7 raqam turi boshqa detal bilan kelsa (profil raqami «dona» da) — raqam bo'yicha moslanmaydi: «Ustun U» o'zi (nom bo'yicha), «Yangi dona» — yangi",
      r.status_code == 200 and _u7.get("name") == "Ustun U" and _u7.get("cat") == "profil" and _u7.get("del") == _ust["del"]
      and any(x["name"] == "Yangi dona" and x["id"] != _ust["id"] for x in D7), (r.status_code, xabar(r), D7))
_d7b = detallar(O1)
_b7b = [x for x in body_from(O1) if x.get("name") not in ("Begona", "Yangi dona")]
for x in _b7b:
    if x.get("id") == _ust["id"]:
        x.update({"category": "dona", "width": 10, "thickness": 10, "length": 25, "quantity": 50, "notes": "dona_yield=2"})   # miqdor ≥ topshirilgan
r = put(O1, _b7b)
check("A7b bir xil NOM, lekin turi boshqa («Ustun U» profil raqami «dona» bilan) — raqam bo'yicha moslanmaydi: topshirilgan profil «o'chirilgan» "
      "bo'ladi — avvalgidek 400, hech narsa o'zgarmadi", r.status_code == 400 and detallar(O1) == _d7b, (r.status_code, xabar(r), detallar(O1)))
_d8 = detallar(O3)
r = A.post("/api/orders?confirm_shortage=true", json=tana([dict(profil("K220 yangi", 7, False, ID["P25"]), id=_d8[0]["id"])]))
_o8 = js(r).get("id")
check("A8 yangi buyurtma yaratishda raqam e'tiborsiz — yangi detal yangi raqam bilan, boshqa buyurtma o'zgarmadi",
      r.status_code == 200 and detallar(O3) == _d8 and _o8 and detallar(_o8)[0]["id"] != _d8[0]["id"], (r.status_code, xabar(r)))
_k9 = [put(O1, [dict(x, id=v) for x in body_from(O1)[:1]] + body_from(O1)[1:]).status_code for v in (0, 2_147_483_648)]
check("A9 noto'g'ri raqam (0, 2 147 483 648) — 422 (asl: e'tiborsiz)", _k9 == [422, 422], _k9)
O10 = yarat([profil("Karniz Q", 40, True, ID["P35"]), profil("Karniz Q", 25, False, ID["P25"])])
topshir(O10)
Q0 = detallar(O10)
_b10 = body_from(O10)
_q10 = [i for i, x in enumerate(_b10) if x["name"] == "Karniz Q"]
_b10[_q10[1]]["id"] = _b10[_q10[0]]["id"]          # ikkala nomdoshda bir raqam (buzilgan tana): birinchisi to'g'ri, ikkinchisi takror
r = put(O10, _b10)
check("A10 bir raqam ikki detalda (buzilgan tana) — birinchisi raqam bo'yicha, takror raqamli ikkinchisi — xususiyatlar bo'yicha: 200, o'zgarishsiz",
      r.status_code == 200 and detallar(O10) == Q0, (r.status_code, xabar(r), detallar(O10)))
_tk = A.post("/api/takliflar", json={"mijoz": "K220 Taklif", "telefon": None, "buyurtma": {"order_type": "product", "items": [
    dict(profil("K220 taklif detal", 10, False, ID["P25"]), id=Q0[0]["id"])]}})
from models import Taklif as _Tk                   # noqa: E402
_s11 = SessionLocal()
_tt = [json.loads(x.tana or "{}") for x in _s11.query(_Tk).all()]
_s11.close()
check("A11 taklif tanasida detal raqami SAQLANMAYDI (review220 №6), taklif saqlanadi",
      _tk.status_code == 200 and _tt and all("id" not in it for t in _tt for it in (t.get("items") or [])), (_tk.status_code, _tt[:1]))

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
    OU = yarat([profil("Karniz U", 60, True, ID["P35"]), profil("Ustun UU", 20, False, ID["P35"], w=15), profil("Karniz U", 30, False, ID["P25"],
                                                                                                                  narx_m=35_000)])
    topshir(OU)
    DU0 = detallar(OU)
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
        QATOR = """() => [...document.querySelectorAll('#items .detal')].map(r => ({nom: r.querySelector('.i-name').value,
            l: r.querySelector('.i-l').value, id: r.dataset.itemId || '', del: r.dataset.delivered || '',
            belgi: (r.querySelector('.detal-badge') || {}).textContent || ''}))"""
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
            ctx.set_default_timeout(20000)
            ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda r: r.fulfill(status=204, body=""))
            ctx.add_init_script("try { localStorage.removeItem('penodecor_new_order_draft_v1'); } catch (e) {}")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
            TUT = []
            pg.on("request", lambda q: TUT.append(q.post_data) if q.method == "PUT" and re.search(r"/api/orders/\d+", q.url) else None)
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", "k220_a")
            xav(pg.fill, "input[name=password]", PAROL)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.goto, BU + "/orders")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.evaluate, """() => { window.__msg = []; window.showMsg = (t, ty) => { window.__msg.push([String(t), ty]); };
                window.showConfirmModal = async () => true; window.customConfirm = async () => true; window.confirm = () => true;
                window.alert = (t) => window.__msg.push([String(t), 'alert']); }""")
            xav(pg.evaluate, f"() => {{ selectedOrderId = {OU}; editSelected('edit'); }}")
            xav(pg.wait_for_timeout, 2500)
            NAT["qatorlar"] = xav(pg.evaluate, QATOR, standart=[])
            NAT["collect"] = xav(pg.evaluate, "() => collectItems().map(x => [x.name, x.length, x.id === undefined ? null : x.id])", standart=[])
            xav(pg.evaluate, "() => addItem()")
            xav(pg.wait_for_timeout, 300)
            NAT["yangi_qator_id"] = xav(pg.evaluate, "() => document.querySelector('#items .detal').dataset.itemId || ''")
            xav(pg.evaluate, "() => { const r = document.querySelector('#items .detal'); r.remove(); }")
            xav(pg.evaluate, f"() => {{ updateOrder({OU}); }}")
            xav(pg.wait_for_timeout, 3000)
            xav(pg.wait_for_load_state, "networkidle")                  # review220 №8: saqlangach sahifa yangilanishi mumkin
            NAT["msg"] = xav(pg.evaluate, "() => window.__msg", standart=[])
            NAT["put"] = [[(i.get("name"), i.get("id")) for i in json.loads(t or "{}").get("items", [])] for t in TUT]
            xav(pg.evaluate, "() => { hideNewForm(); }")
            xav(pg.evaluate, f"""async () => {{ const o = await fetch('/api/orders/{OU}').then(r => r.json());
                selectedOrderId = {OU}; editSelected('duplicate', o); }}""")
            xav(pg.wait_for_timeout, 2500)
            NAT["nusxa"] = xav(pg.evaluate, "() => [...document.querySelectorAll('#items .detal')].map(r => r.dataset.itemId || '')", standart=None)
            NAT["nusxa_collect"] = xav(pg.evaluate, "() => collectItems().filter(x => x.id !== undefined).length", standart=None)
            br.close()
        server.should_exit = True
        q = NAT.get("qatorlar") or []
        _ids = {x["id"]: x for x in DU0}
        check("U1 tahrir formasi: har qatorda o'z detal raqami (nomdoshlar ham), «📦» belgisi va «kamida» cheklovi har biri O'ZINIKI (60 / 30; asl: nom "
              "bo'yicha — ikkalasida bir xil)",
              len(q) == 4 and all(x["id"] and int(x["id"]) in _ids for x in q)
              and all(float(x["del"] or 0) == _ids[int(x["id"])]["del"] for x in q if x["id"])
              and all(f"{int(_ids[int(x['id'])]['del'])} metr topshirilgan" in x["belgi"] or f"{int(_ids[int(x['id'])]['del'])} m" in x["belgi"]
                      for x in q if x["id"] and _ids[int(x["id"])]["del"] > 0), (q, DU0))
        check("U2 `collectItems` raqamlarni yuboradi; yangi qo'shilgan qatorda raqam yo'q",
              len(NAT.get("collect") or []) == 4 and all(c[2] for c in NAT["collect"]) and NAT.get("yangi_qator_id") == "",
              (NAT.get("collect"), NAT.get("yangi_qator_id")))
        check("U3 o'zgarishsiz «Saqlash» — muvaffaqiyatli («✓ Saqlandi»), PUT tanasida raqamlar, detallar o'zgarmadi (asl: «❌ O'zgarishlar saqlanmadi: "
              "Topshirilgan miqdordan kam qilib bo'lmaydi!»)",
              NAT.get("put") and all(i[1] for i in NAT["put"][0]) and any("Saqlandi" in m[0] for m in (NAT.get("msg") or []))
              and not any("saqlanmadi" in m[0] for m in (NAT.get("msg") or [])) and detallar(OU) == DU0, (NAT.get("put"), NAT.get("msg"), detallar(OU)))
        check("U4 «Nusxa olish» — qatorlarda raqam yo'q (yangi buyurtma)", NAT.get("nusxa") is not None and all(x == "" for x in NAT["nusxa"])
              and NAT.get("nusxa_collect") == 0, (NAT.get("nusxa"), NAT.get("nusxa_collect")))
        check("U5 JS xatosi yo'q", not XATO, XATO[:3])

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
