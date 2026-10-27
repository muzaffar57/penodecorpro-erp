#!/usr/bin/env python3
"""
test_loy_nomi219.py — kech159 (zip 219 «Kichik qoldiqlar: Tayyor loy nomi va eslatma yangilanishi» — egasi tanlovi 27.10: «Kichik qoldiqlar
(Tavsiya)»).

NIMA UCHUN KERAK (O'LCHANGAN — `work/k219/probe219.py` SQLite = PG, `work/k219/probe219b.py` Chromium; zip 218b kodi)
  (1) «Tayyor loy (…)» nomi band emas edi: oddiy «Tayyor loy (Oq marmar)» (qop) material retseptning ortgan loy zaxirasi bo'lib qolardi
      (buyurtma «3 qop» ni «3 kg loy» deb yechdi, ortgan 4 kg «4 qop» bo'lib qo'shildi, «kam qoldi» ogohlantirishi yo'qoldi); oddiy material shu
      nomga qayta nomlanardi; haqiqiy zaxira qayta nomlansa kg i oddiy materialga o'tib, retsept yangi bo'sh zaxira yaratardi; retsept nomi
      o'zgarsa eski zaxira eski nomda «yetim» qolardi; 88+ belgili retsept — PG da buyurtma 500; yashirilgan zaxiraga qo'shilgan loy
      Omborxonada ko'rinmasdi.
  (2) Buyurtma oynasi ochiq turganda boshqa xodim shu loyihaga yozgan buyurtma «ℹ️ Bu loyihada» eslatmasida chiqmasdi (ma'lumot forma
      ochilganda bir marta olinardi).
BO'LIMLAR
  S — manba (o'zgarmaslar, nom qoidasi, sahifa belgilari).
  A — server: band nom (yaratish, tiklash, qayta nomlash; harf / bo'shliq farqi); ruxsat etilgan o'xshash nomlar; retsept zaxirasi nomi /
      birligi / turi; retseptga bog'lanmagan eski qator; retsept nomi o'zgarsa zaxira ham (tarix bilan), band nom — 409 (hech narsa
      o'zgarmaydi), zaxirasiz retsept; retsept nomi 87 / 88 belgi (PG da zaxira va buyurtma); yashirin zaxiraga ortgan / qaytgan loy.
  U — HAQIQIY Chromium (SQLite / TF1): eslatma muddati o'tgach qayta so'raladi (muddat ichida — yo'q), boshqa qatorlar ham yangilanadi,
      sahifaga qaytilganda (visibilitychange / focus), forma yopiq bo'lsa so'rov yo'q, standart muddat 15 s; retsept nomi maydoni 87 belgi;
      JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (S + A).
Asl kodga (zip 218b) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_loy_nomi219.py
"""
import os
import io
import re
import sys
import glob
import json
import time
import socket
import datetime
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "loy_nomi219_test"
_T = tempfile.mkdtemp(prefix="k219_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k219.db')}"
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
REC_HTML = open(os.path.join(ROOT, "templates", "recipes.html"), encoding="utf-8").read()

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import services                                # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, InventoryMovement, Project, Recipe, RecipeIngredient, Master, Order)   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    with TestClient(main.app):
        pass

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_PRE = getattr(crud, "LOY_ZAXIRA_PREFIKS", None)
_MAX = getattr(crud, "RETSEPT_NOMI_MAX", None)
check("S1 `crud.LOY_ZAXIRA_PREFIKS` = `services.TAYYOR_LOY_PREFIKS` («Tayyor loy (»); `RETSEPT_NOMI_MAX` = 87 — «Tayyor loy (<87>)» "
      "aynan `inventory.item_name` uzunligi (100)",
      _PRE == getattr(services, "TAYYOR_LOY_PREFIKS", "?") == "Tayyor loy (" and _MAX == 87
      and len(f"{_PRE}{'x' * (_MAX or 0)})") == Inventory.__table__.c.item_name.type.length == 100, (_PRE, _MAX))
_lzn = getattr(crud, "loy_zaxira_nomimi", None)
_HA = ["Tayyor loy (Oq marmar)", "  tayyor   LOY (oq marmar)", "TAYYOR LOY (", "Tayyor loy (", "Tayyor\u00a0loy (X)", "\ufeffTayyor loy (X)",
       "Tayyor\u200b loy (X)", "Tay\u00adyor loy (X)"]
_YOQ = ["Tayyor loyiha materiali", "Tayyor loy", "Loy tayyor (Oq marmar)", "KPI Tayyor loy (nusxa)", "Tayyor loy(X)", "Тайёр лой (X)", ""]
check("S2 `crud.loy_zaxira_nomimi`: nom KALITI «tayyor loy (» bilan boshlansa — band (harf / bo'shliq / ko'rinmas belgi farqsiz — "
      "review219 №9); o'xshash, lekin boshqa nomlar — band emas",
      _lzn is not None and all(_lzn(x) for x in _HA) and not any(_lzn(x) for x in _YOQ),
      [(x, _lzn(x)) for x in _HA + _YOQ] if _lzn else None)
check("S3 «Loy retseptlari» sahifasi: yangi va tahrir nom maydoni — maxlength 87 (server qoidasi bilan bir)",
      'id="f-name" list="recipe-name-suggest" maxlength="87"' in REC_HTML and 'id="edit-name" maxlength="87"' in REC_HTML
      and 'maxlength="100"' not in REC_HTML.split('id="f-name"')[1][:80] and 'id="edit-name" maxlength="100"' not in REC_HTML)
check("S4 orders.html: eslatma muddati (`_takrorMuddat`, `window.TAKROR_MUDDAT_MS`, standart 15000), `_takrorEskirdi`, sahifaga qaytish "
      "(`visibilitychange` va `focus` — bir marta ulanadi)",
      all(x in ORD for x in ("function _takrorMuddat()", "window.TAKROR_MUDDAT_MS", ": 15000;", "function _takrorEskirdi()",
                             "function takrorQaytaKorinish()", "document.addEventListener('visibilitychange', takrorQaytaKorinish);",
                             "window.addEventListener('focus', takrorQaytaKorinish);", "if (!window.__takror219)")))

check("S5 retsept tahriri (`main.api_update_recipe`) — xomashyo navbatida: zaxira qatorini qulflaydi (review219 №1 — ikki parallel qayta "
      "nomlash eski nomda «yetim» zaxira qoldirardi)", ("main", "api_update_recipe") in getattr(main, "_XOMASHYO_MARSHRUTLARI", ()))

# ── ma'lumot
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k219_a", PAROL, UserRole.ADMIN, "K219 Admin", company_id=1)
    auth.create_user(s, "k219_b", PAROL, UserRole.ADMIN, "K219 Sherik", company_id=1)
PENO = Inventory(company_id=1, item_name="K219 Penoplast", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="K219 Kley", unit="kg", stock_quantity=100_000, price_per_unit=2_000, category="Kimyo")
PRJ = Project(company_id=1, client_name="K219 mijoz", project_name="K219 loyiha", client_phone="+998901112219", total_budget=0,
              total_paid=0)
US = Master(company_id=1, name="K219 Usta", phone="+998900002219", kpi_percent=10)
s.add_all([PENO, KLEY, PRJ, US])
s.flush()
RID = {}
for _n in ("K219 R1", "K219 R2", "K219 R3", "K219 R4", "K219 R5", "K219 R6", "K219 R7", "K219 R10"):
    _r = Recipe(company_id=1, name=_n, batch_size_kg=100.0)
    s.add(_r)
    s.flush()
    s.add(RecipeIngredient(recipe_id=_r.id, inventory_id=KLEY.id, quantity_kg=100.0))
    RID[_n] = _r.id
s.commit()
ID = {"PENO": PENO.id, "KLEY": KLEY.id, "PRJ": PRJ.id, "US": US.id}
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    return c


A = mijoz("k219_a")
B = mijoz("k219_b")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def matn(r):
    d = js(r)
    det = d.get("detail", d) if isinstance(d, dict) else d
    return str(det.get("message") if isinstance(det, dict) and det.get("message") else det)


def yarat(nom, unit="kg", qty=0, narx=0, min_stock=0, cat="Kimyo"):
    return A.post("/api/inventory", json={"item_name": nom, "unit": unit, "stock_quantity": qty, "price_per_unit": narx,
                                          "min_stock": min_stock, "is_penoplast": False, "category": cat})


def mat_soni():
    s2 = SessionLocal()
    try:
        return s2.query(Inventory).count()
    finally:
        s2.close()


def mat(i):
    s2 = SessionLocal()
    try:
        p = s2.get(Inventory, i)
        if p is None:
            return None
        hr = [(m.id, m.movement_type, round(float(m.quantity), 3)) for m in
              s2.query(InventoryMovement).filter(InventoryMovement.inventory_id == i).order_by(InventoryMovement.id)]
        return {"nom": p.item_name, "unit": p.unit, "qoldiq": round(float(p.stock_quantity or 0), 3), "peno": bool(p.is_penoplast),
                "del": bool(p.is_deleted), "cat": p.category, "min": p.min_stock, "har": hr}
    finally:
        s2.close()


def nomli(nom):
    s2 = SessionLocal()
    try:
        return [x.id for x in s2.query(Inventory).filter(Inventory.item_name == nom).order_by(Inventory.id)]
    finally:
        s2.close()


def orm_mat(**kv):
    s2 = SessionLocal()
    try:
        m = Inventory(company_id=1, **kv)
        s2.add(m)
        s2.commit()
        return m.id
    finally:
        s2.close()


def orm_yoz(i, **kv):
    s2 = SessionLocal()
    try:
        m = s2.get(Inventory, i)
        for k, v in kv.items():
            setattr(m, k, v)
        s2.commit()
    finally:
        s2.close()


def zaxira(rid):
    r = A.get(f"/api/loy-stock?recipe_id={rid}")
    d = js(r)
    ids = nomli(d.get("name")) if isinstance(d, dict) and d.get("name") else []
    return r.status_code, d, (ids[0] if ids else None)


def kirim(i, q):
    return A.post(f"/api/inventory/{i}/stock", json={"quantity_change": q, "reason": "K219 sinov"}).status_code


_SANOQ = [0]


def buyurtma(rid, loy=10.0):
    _SANOQ[0] += 1
    tana = {"project_id": ID["PRJ"], "order_type": "product", "loy_kg": loy, "recipe_id": rid, "master_id": ID["US"],
            "items": [{"name": f"K219 D{_SANOQ[0]}", "category": "profil", "width": 20, "thickness": 10, "length": 10 + _SANOQ[0],
                       "quantity": 10, "unit_price": 50_000, "is_coated": True, "penoplast_id": ID["PENO"], "recipe_id": rid}]}
    r = A.post("/api/orders", json=tana, params={"confirm_shortage": "true"})
    return r.status_code, (js(r).get("id") if r.status_code == 200 else None)


def retsept(rid):
    s2 = SessionLocal()
    try:
        r = s2.get(Recipe, rid)
        return {"nom": r.name, "batch": float(r.batch_size_kg), "tarkib": sorted((i.inventory_id, float(i.quantity_kg)) for i in r.ingredients)}
    finally:
        s2.close()


def retsept_put(rid, nom, batch=100, kg=100):
    return A.put(f"/api/recipes/{rid}", json={"name": nom, "batch_size_kg": batch,
                                             "ingredients": [{"inventory_id": ID["KLEY"], "quantity_kg": kg}]})


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A — server: «Tayyor loy (…)» nomi va retsept zaxirasi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_n0 = mat_soni()
r = yarat("Tayyor loy (K219 R1)", unit="qop", qty=3, narx=50_000, min_stock=5)
_z1 = zaxira(RID["K219 R1"])
check("A1 oddiy material «Tayyor loy (K219 R1)» (retsept zaxirasi hali yo'q) — 400 «band», hech narsa yozilmadi; retsept zaxirasi keyin "
      "o'zi kg da yaratiladi (asl: 200, «qop» material zaxira bo'lib qolardi)",
      r.status_code == 400 and "band" in matn(r) and _z1[0] == 200 and (_z1[1] or {}).get("stock_kg") == 0
      and (mat(_z1[2]) or {}).get("unit") == "kg" and mat_soni() == _n0 + 1, (r.status_code, matn(r), _z1, mat_soni(), _n0))
_rs = {x: yarat(x).status_code for x in ("  TAYYOR  loy (K219 x)", "tayyor loy (", "Tayyor loy (K219 R1)")}
check("A2 harf / bo'shliq farqi bilan ham — 400 (qatorlar qo'shilmadi)", all(v == 400 for v in _rs.values()) and mat_soni() == _n0 + 1, _rs)
_ok = {x: yarat(x).status_code for x in ("K219 Tayyor loyiha materiali", "Tayyor loy", "Loy tayyor (K219)", "KPI Tayyor loy (K219 nusxa)",
                                          "Tayyor loy(K219)")}
check("A3 o'xshash, lekin boshqa nomlar («Tayyor loy» qavssiz, «Loy tayyor (…)», o'rtasida «Tayyor loy (») — avvalgidek 200",
      all(v == 200 for v in _ok.values()), _ok)
_yid = orm_mat(item_name="Tayyor loy (K219 eski)", unit="kg", stock_quantity=0, is_deleted=True)
r = yarat("Tayyor loy (K219 eski)")
check("A4 yashirilgan (o'chirilgan) eski «Tayyor loy (…)» qatori shu nom bilan TIKLANMAYDI — 400, qator yashirinligicha",
      r.status_code == 400 and (mat(_yid) or {}).get("del") is True, (r.status_code, matn(r), mat(_yid)))
r0 = yarat("K219 Akril", qty=2, narx=1000, min_stock=5)
_ak = js(r0).get("id")
r = A.put(f"/api/inventory/{_ak}", json={"item_name": "Tayyor loy (K219 Akril)"})
r2 = A.put(f"/api/inventory/{_ak}", json={"item_name": " tayyor LOY (k219 akril) "})
s = SessionLocal()
_kam = sorted(m.item_name for m in crud.get_low_stock_items(s, company_id=1))
s.close()
check("A5 oddiy materialni «Tayyor loy (…)» ga qayta nomlash — 400 (harfi boshqa bo'lsa ham), nomi o'zgarmadi, «kam qoldi» ro'yxatida "
      "qoldi (asl: 200 va ro'yxatdan yo'qolardi)",
      r.status_code == 400 and r2.status_code == 400 and (mat(_ak) or {}).get("nom") == "K219 Akril" and "K219 Akril" in _kam,
      (r.status_code, r2.status_code, mat(_ak), _kam))
# retsept zaxirasi (R2) — 7 kg
_st, _d, Z2 = zaxira(RID["K219 R2"])
kirim(Z2, 7)
_o2 = mat(Z2)
r = A.put(f"/api/inventory/{Z2}", json={"item_name": "K219 Eski loy"})
r2 = A.put(f"/api/inventory/{Z2}", json={"item_name": "tayyor loy (K219 R2)"})
_z2b = zaxira(RID["K219 R2"])
check("A6 retsept zaxirasini qayta nomlash — 400 (faqat harfini o'zgartirish ham), nomi / qoldig'i / tarixi o'zgarmadi, retsept o'sha "
      "zaxirani ko'radi (asl: 200 — 7 kg oddiy materialga o'tib, retsept yangi bo'sh zaxira yaratardi)",
      r.status_code == 400 and "retsept" in matn(r) and r2.status_code == 400 and mat(Z2) == _o2 and _o2.get("qoldiq") == 7
      and _z2b[2] == Z2 and (_z2b[1] or {}).get("stock_kg") == 7, (r.status_code, matn(r), r2.status_code, mat(Z2), _z2b))
r = A.put(f"/api/inventory/{Z2}", json={"category": "Loy", "min_stock": 1})
check("A7 retsept zaxirasining kategoriyasi / minimal qoldig'i — avvalgidek 200", r.status_code == 200
      and (mat(Z2) or {}).get("cat") == "Loy", (r.status_code, matn(r), mat(Z2)))
_st, _d, Z3 = zaxira(RID["K219 R3"])
_o3 = mat(Z3)
ru = A.put(f"/api/inventory/{Z3}", json={"unit": "qop"})
rp = A.put(f"/api/inventory/{Z3}", json={"is_penoplast": True})
rk = A.put(f"/api/inventory/{Z3}", json={"unit": " kg "})
check("A8 retsept zaxirasi (tarixi YO'Q bo'lsa ham) — birligi «qop» ga va penoplastga o'tmaydi (400), hech narsa yozilmadi; « kg » "
      "(bo'shliq farqi) — o'zgarish emas (200)",
      ru.status_code == 400 and rp.status_code == 400 and "loy zaxirasi" in matn(ru) and rk.status_code == 200
      and (mat(Z3) or {}).get("unit") == "kg" and not (mat(Z3) or {}).get("peno") and mat(Z3)["har"] == _o3["har"],
      (ru.status_code, matn(ru), rp.status_code, rk.status_code, mat(Z3)))
_bog = orm_mat(item_name="Tayyor loy (K219 retseptsiz)", unit="qop", stock_quantity=2, category="Kimyo")
r = A.put(f"/api/inventory/{_bog}", json={"item_name": "Tayyor loy (K219 boshqa)"})
r2 = A.put(f"/api/inventory/{_bog}", json={"item_name": "K219 Kley aralashma"})
check("A9 retseptga bog'lanmagan eski «Tayyor loy (…)» qator: boshqa «Tayyor loy (…)» nomga — 400; prefiksiz nomga — 200 (tuzatib olish mumkin)",
      r.status_code == 400 and r2.status_code == 200 and (mat(_bog) or {}).get("nom") == "K219 Kley aralashma",
      (r.status_code, r2.status_code, matn(r2), mat(_bog)))
_yetim = orm_mat(item_name="Tayyor loy (K219 o'chgan retsept)", unit="kg", stock_quantity=0, category="Kimyo")
r = A.put(f"/api/inventory/{_yetim}", json={"item_name": "K219 Eski loy qoldig'i"})
check("A9c retsepti yo'q (o'chirilgan retseptdan qolgan) kg li «Tayyor loy (…)» qator — prefiksiz nomga 200 (u zaxira emas — faqat mavjud "
      "retsept zaxirasi himoyada)", r.status_code == 200 and (mat(_yetim) or {}).get("nom") == "K219 Eski loy qoldig'i", (r.status_code, matn(r)))
_qop = orm_mat(item_name="Tayyor loy (K219 R10)", unit="qop", stock_quantity=0, category="Kimyo")
r = A.put(f"/api/inventory/{_qop}", json={"item_name": "K219 Qop loy"})
check("A9b retsept nomidagi, lekin zaxira SHAKLIDA bo'lmagan («qop») eski qator — prefiksiz nomga qayta nomlab tuzatsa bo'ladi (200; review219 "
      "№4 — ilgari 400 «birligi «qop» o'zgarmaydi»)", r.status_code == 200 and (mat(_qop) or {}).get("nom") == "K219 Qop loy",
      (r.status_code, matn(r), mat(_qop)))
# retsept nomi o'zgarsa — zaxira ham (R4, 9 kg)
_st, _d, Z4 = zaxira(RID["K219 R4"])
kirim(Z4, 9)
_o4 = mat(Z4)
r = retsept_put(RID["K219 R4"], "K219 R4 yangi")
_z4 = zaxira(RID["K219 R4"])
_sb, _ob = buyurtma(RID["K219 R4"], loy=4.0)
check("A10 retsept nomi o'zgartirildi — uning zaxirasi o'sha qator (id, 9 kg, harakatlar) «Tayyor loy (K219 R4 yangi)» bo'ldi, eski nomda "
      "qator yo'q, retsept shu zaxirani ko'radi, keyingi buyurtma undan oladi (asl: 9 kg eski nomda qolib, retsept yangi bo'sh zaxira "
      "yaratardi)",
      r.status_code == 200 and _z4[2] == Z4 and (mat(Z4) or {}).get("nom") == "Tayyor loy (K219 R4 yangi)"
      and mat(Z4)["har"][:len(_o4["har"])] == _o4["har"] and not nomli("Tayyor loy (K219 R4)") and (_z4[1] or {}).get("stock_kg") == 9
      and _sb == 200 and (mat(Z4) or {}).get("qoldiq") == 5, (r.status_code, matn(r), _z4, mat(Z4), _sb))
_st, _d, Z5 = zaxira(RID["K219 R5"])
r = retsept_put(RID["K219 R5"], "k219 r5")
check("A11 retsept nomining faqat harfi o'zgardi («K219 R5» → «k219 r5») — zaxira ham AYNAN shu yozilishga o'tdi",
      r.status_code == 200 and (mat(Z5) or {}).get("nom") == "Tayyor loy (k219 r5)" and zaxira(RID["K219 R5"])[2] == Z5,
      (r.status_code, matn(r), mat(Z5)))
_st, _d, Z6 = zaxira(RID["K219 R6"])
kirim(Z6, 3)
_band = orm_mat(item_name="Tayyor loy (K219 band)", unit="kg", stock_quantity=1, is_deleted=True)
_o6, _r6 = mat(Z6), retsept(RID["K219 R6"])
r = retsept_put(RID["K219 R6"], "K219 band", batch=150, kg=90)
check("A12 yangi nomdagi zaxira omborda allaqachon bor (yashirin bo'lsa ham) — 409 sababi bilan, retsept (nomi, hajmi, tarkibi) va ikkala "
      "material o'zgarmadi",
      r.status_code == 409 and "Tayyor loy (K219 band)" in matn(r) and "o'chirilgan (yashirilgan)" in matn(r)
      and retsept(RID["K219 R6"]) == _r6 and mat(Z6) == _o6
      and (mat(_band) or {}).get("nom") == "Tayyor loy (K219 band)", (r.status_code, matn(r), retsept(RID["K219 R6"]), mat(Z6)))
_n7 = mat_soni()
r = retsept_put(RID["K219 R7"], "K219 R7 yangi")
check("A13 zaxirasi yo'q retsept nomi o'zgartirildi — 200, ombor qatori yaratilmadi", r.status_code == 200 and mat_soni() == _n7,
      (r.status_code, mat_soni(), _n7))
_88, _87 = "K" + "x" * 87, "K" + "y" * 86
r88 = A.post("/api/recipes", json={"name": _88, "batch_size_kg": 100, "ingredients": [{"inventory_id": ID["KLEY"], "quantity_kg": 100}]})
r87 = A.post("/api/recipes", json={"name": _87, "batch_size_kg": 100, "ingredients": [{"inventory_id": ID["KLEY"], "quantity_kg": 100}]})
_rid87 = js(r87).get("id")
_z87 = zaxira(_rid87) if _rid87 else (0, {}, None)
_s87, _ = buyurtma(_rid87, loy=5.0) if _rid87 else (0, None)
rp88 = retsept_put(_rid87, _88) if _rid87 else None
check("A14 retsept nomi 88 belgi — 400 «ko'pi bilan 87»; 87 belgi — 200, uning zaxirasi (100 belgili nom) va qoplamali buyurtma — 200 "
      "(PG da ham; asl: 88+ belgili retseptli buyurtma PG da 500); tahrirda 88 belgi — 400, nomi o'zgarmadi",
      r88.status_code == 400 and "87" in matn(r88) and r87.status_code == 200 and _z87[0] == 200
      and len(str((_z87[1] or {}).get("name") or "")) == 100 and _s87 == 200 and rp88 is not None and rp88.status_code == 400
      and retsept(_rid87)["nom"] == _87,
      (r88.status_code, matn(r88), r87.status_code, _z87[0], _s87, getattr(rp88, "status_code", None)))
# yashirin zaxira — ortgan loy
s = SessionLocal()
_r8 = Recipe(company_id=1, name="K219 R8", batch_size_kg=100.0)
s.add(_r8)
s.flush()
s.add(RecipeIngredient(recipe_id=_r8.id, inventory_id=ID["KLEY"], quantity_kg=100.0))
s.commit()
RID["K219 R8"] = _r8.id
s.close()
_st, _d, Z8 = zaxira(RID["K219 R8"])
orm_yoz(Z8, is_deleted=True)
_s8, _o8 = buyurtma(RID["K219 R8"], loy=10.0)
r = A.post(f"/api/orders/{_o8}/ready", params={"loy_kg": "6"}) if _o8 else None
_roy = [m.get("id") for m in (js(A.get("/api/inventory")) or []) if isinstance(m, dict)]
check("A15 retsept zaxirasi yashirilgan (o'chirilgan) — «Tayyor» da ortgan 4 kg o'sha qatorga qo'shiladi va u QAYTA ko'rinadi (Omborxona "
      "ro'yxatida; asl: yashirin qatorga qo'shilib ko'rinmasdi)",
      r is not None and r.status_code == 200 and (mat(Z8) or {}).get("qoldiq") == 4 and (mat(Z8) or {}).get("del") is False and Z8 in _roy,
      (getattr(r, "status_code", None), mat(Z8), Z8 in _roy))
# yashirin zaxira — buyurtma o'chirilganda zaxiradan olingan loy qaytadi
s = SessionLocal()
_r9 = Recipe(company_id=1, name="K219 R9", batch_size_kg=100.0)
s.add(_r9)
s.flush()
s.add(RecipeIngredient(recipe_id=_r9.id, inventory_id=ID["KLEY"], quantity_kg=100.0))
s.commit()
RID["K219 R9"] = _r9.id
s.close()
_st, _d, Z9 = zaxira(RID["K219 R9"])
kirim(Z9, 5)
_s9, _o9 = buyurtma(RID["K219 R9"], loy=10.0)
_q9 = (mat(Z9) or {}).get("qoldiq")
orm_yoz(Z9, is_deleted=True)
r = A.delete(f"/api/orders/{_o9}") if _o9 else None
check("A16 buyurtma zaxiradan 5 kg olgan, so'ng zaxira yashirilgan — buyurtma o'chirilganda 5 kg zaxiraga qaytadi va u QAYTA ko'rinadi",
      _s9 == 200 and _q9 == 0 and r is not None and r.status_code == 200 and (mat(Z9) or {}).get("qoldiq") == 5
      and (mat(Z9) or {}).get("del") is False, (_s9, _q9, getattr(r, "status_code", None), mat(Z9)))
_f = getattr(crud, "retsept_zaxira_nomi_xatosi", None)
s = SessionLocal()
_rr = s.get(Recipe, RID["K219 R6"])
check("A17 `crud.retsept_zaxira_nomi_xatosi`: band nom — matn; o'z nomi / bo'sh joy — None",
      _f is not None and _f(s, _rr, "K219 band") and _f(s, _rr, _rr.name) is None and _f(s, _rr, "K219 R6 boshqa") is None)
s.close()

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
    XATO = []
    SOROV = []
    NAT = {}
    s = SessionLocal()
    P2 = Project(company_id=1, client_name="K219 U mijoz", project_name="K219 U loyiha", client_phone="+998901112220", total_budget=0,
                 total_paid=0)
    s.add(P2)
    s.commit()
    PID2 = P2.id
    s.close()

    def sherik(nom, L):
        tana = {"project_id": PID2, "order_type": "product", "recipe_id": None, "master_id": ID["US"],
                "deadline": (datetime.date.today() + datetime.timedelta(days=3)).isoformat(), "is_draft": False, "base_price": 600000,
                "loy_kg": None, "items": [{"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": L, "quantity": 1,
                                           "unit_price": 10000, "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None,
                                           "finished_product_id": None}]}
        r = B.post("/api/orders?confirm_shortage=true", json=tana)
        return js(r).get("order_number") if r.status_code == 200 else None

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
        ESL = """(nom) => { const r = [...document.querySelectorAll('#items .detal')].find(x => (x.querySelector('.i-name') || {}).value === nom);
          if (!r) return null; const e = r.querySelector('.i-takror');
          return {matn: e ? e.textContent : null, bor: !!e && e.style.display === 'block', belgi: r.dataset.takror || ''}; }"""
        YOZ = """([i, m]) => { const n = document.querySelectorAll('#items .detal .i-name')[i]; n.value = '';
          n.dispatchEvent(new Event('input')); n.value = m; n.dispatchEvent(new Event('input')); }"""
        QAYT = """() => { Object.defineProperty(document, 'visibilityState', {value: 'hidden', configurable: true});
          document.dispatchEvent(new Event('visibilitychange'));
          Object.defineProperty(document, 'visibilityState', {value: 'visible', configurable: true});
          document.dispatchEvent(new Event('visibilitychange')); }"""
        with sync_playwright() as pw:
            _exe = None
            for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                    "chrome-linux", "chrome"))):
                _exe = _y
            br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()
            ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
            ctx.set_default_timeout(20000)
            ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda r: r.fulfill(status=204, body=""))
            ctx.add_init_script("try { localStorage.removeItem('penodecor_new_order_draft_v1'); } catch (e) {}")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
            pg.on("request", lambda q: SOROV.append(q.url.replace(BU, "")) if "berilgan-detallar" in q.url else None)
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", "k219_a")
            xav(pg.fill, "input[name=password]", PAROL)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.goto, BU + "/orders")
            xav(pg.wait_for_load_state, "networkidle")
            NAT["muddat_std"] = xav(pg.evaluate, "() => (typeof _takrorMuddat === 'function') ? _takrorMuddat() : null")
            xav(pg.evaluate, "() => { window.showMsg = () => {}; window.TAKROR_MUDDAT_MS = 1500; showNewForm(); "
                             "document.getElementById('items').innerHTML = ''; if (typeof itemCount !== 'undefined') itemCount = 0; addItem(); }")
            xav(pg.evaluate, f"() => {{ const p = document.getElementById('project_id'); p.value = '{PID2}'; p.dispatchEvent(new Event('change')); }}")
            xav(pg.wait_for_timeout, 400)
            SOROV.clear()
            xav(pg.evaluate, YOZ, [0, "K219 Karniz"])
            xav(pg.wait_for_timeout, 600)
            NAT["u1_a"] = [xav(pg.evaluate, ESL, "K219 Karniz"), len(SOROV)]
            NAT["or1"] = sherik("K219 Karniz", 40)
            xav(pg.evaluate, YOZ, [0, "K219 Karniz"])
            xav(pg.wait_for_timeout, 500)
            NAT["u1_b"] = [xav(pg.evaluate, ESL, "K219 Karniz"), len(SOROV)]
            xav(pg.wait_for_timeout, 1300)
            xav(pg.evaluate, YOZ, [0, "K219 Karniz"])
            xav(pg.wait_for_timeout, 900)
            NAT["u1_c"] = [xav(pg.evaluate, ESL, "K219 Karniz"), len(SOROV)]
            # U2 — boshqa qator yangilanadi: 1-qator «K219 Ustun», 2-qatorga «K219 Boshqa» yoziladi (muddat o'tgach)
            xav(pg.evaluate, YOZ, [0, "K219 Ustun"])
            xav(pg.wait_for_timeout, 500)
            xav(pg.evaluate, "() => { addItem(); document.querySelectorAll('#items .detal').forEach(r => r.classList.remove('collapsed')); }")
            xav(pg.wait_for_timeout, 300)
            NAT["u2_a"] = xav(pg.evaluate, ESL, "K219 Ustun")
            NAT["or2"] = sherik("K219 Ustun", 25)
            xav(pg.wait_for_timeout, 1700)
            _n2 = len(SOROV)
            _yangi_i = xav(pg.evaluate, "() => [...document.querySelectorAll('#items .detal .i-name')].findIndex(n => !n.value)", standart=-1)
            xav(pg.evaluate, YOZ, [_yangi_i, "K219 Boshqa"])
            xav(pg.wait_for_timeout, 1000)
            NAT["u2_b"] = [xav(pg.evaluate, ESL, "K219 Ustun"), len(SOROV) - _n2]
            # U3 — sahifaga qaytish (visibilitychange), keyin focus
            NAT["or3"] = sherik("K219 Ustun", 26)
            xav(pg.wait_for_timeout, 1700)
            _n3 = len(SOROV)
            xav(pg.evaluate, QAYT)
            xav(pg.wait_for_timeout, 1000)
            NAT["u3_a"] = [xav(pg.evaluate, ESL, "K219 Ustun"), len(SOROV) - _n3]
            NAT["or4"] = sherik("K219 Boshqa", 30)
            xav(pg.wait_for_timeout, 1700)
            _n4 = len(SOROV)
            xav(pg.evaluate, "() => window.dispatchEvent(new Event('focus'))")
            xav(pg.wait_for_timeout, 1000)
            NAT["u3_b"] = [xav(pg.evaluate, ESL, "K219 Boshqa"), len(SOROV) - _n4]
            _n5 = len(SOROV)
            xav(pg.evaluate, QAYT)
            xav(pg.wait_for_timeout, 600)
            NAT["u3_c"] = len(SOROV) - _n5
            # U8 — yangilash so'rovi yiqilsa (500 / tarmoq) — eski eslatma joyida qoladi, keyin yana so'raladi (review219 №3)
            _yiq = {"n": 0, "tur": "500"}

            def _yh(rt):
                _yiq["n"] += 1
                if _yiq["tur"] == "tarmoq":
                    return rt.abort()
                return rt.fulfill(status=500, content_type="text/html", body="<h1>500</h1>")
            _URL = re.compile(r".*/berilgan-detallar.*")
            xav(pg.route, _URL, _yh)
            for _tur in ("500", "tarmoq"):
                _yiq["tur"] = _tur
                xav(pg.wait_for_timeout, 1700)
                _n8 = len(SOROV)
                xav(pg.evaluate, QAYT)
                xav(pg.wait_for_timeout, 900)
                NAT[f"u8_{_tur}"] = [xav(pg.evaluate, ESL, "K219 Ustun"), len(SOROV) - _n8, xav(pg.evaluate, "() => TAKROR.vaqt")]
            xav(pg.unroute, _URL, _yh)
            _n9 = len(SOROV)
            xav(pg.evaluate, QAYT)
            xav(pg.wait_for_timeout, 900)
            NAT["u8_keyin"] = [xav(pg.evaluate, ESL, "K219 Ustun"), len(SOROV) - _n9]
            # U4 — forma yopiq: so'rov yo'q
            xav(pg.wait_for_timeout, 1700)
            xav(pg.evaluate, "() => hideNewForm()")
            _n6 = len(SOROV)
            xav(pg.evaluate, QAYT)
            xav(pg.evaluate, "() => window.dispatchEvent(new Event('focus'))")
            xav(pg.wait_for_timeout, 800)
            NAT["u4"] = len(SOROV) - _n6
            # U6 — retsept nomi maydoni
            xav(pg.goto, BU + "/recipes")
            xav(pg.wait_for_load_state, "networkidle")
            NAT["u6"] = xav(pg.evaluate, """() => { const a = document.getElementById('f-name'), b = document.getElementById('edit-name');
                return {a: a ? a.maxLength : null, b: b ? b.maxLength : null}; }""")
            br.close()
        server.should_exit = True
        check("U1 standart eslatma muddati — 15 000 ms", NAT.get("muddat_std") == 15000, NAT.get("muddat_std"))
        a, b_, c = NAT.get("u1_a") or [{}, 0], NAT.get("u1_b") or [{}, 0], NAT.get("u1_c") or [{}, 0]
        check("U2 forma ochiq: sherik shu loyihaga «K219 Karniz» yozdi — muddat ichida nom qayta yozilsa yangi so'rov YO'Q (1); muddat "
              "o'tgach — qayta so'raladi (2) va eslatma chiqadi (asl: so'rov 1 ta, eslatma hech qachon chiqmasdi)",
              NAT.get("or1") and not (a[0] or {}).get("bor") and a[1] == 1 and not (b_[0] or {}).get("bor") and b_[1] == 1
              and (c[0] or {}).get("bor") and f"{NAT['or1']} — 40 m (hali berilmagan)" in ((c[0] or {}).get("matn") or "")
              and c[1] == 2, (a, b_, c, NAT.get("or1")))
        u2a, u2b = NAT.get("u2_a") or {}, NAT.get("u2_b") or [{}, 0]
        check("U3 muddat o'tgach BOSHQA qatorga nom yozildi — qayta so'raldi (1) va avval yozilgan «K219 Ustun» qatori (qayta yozilmasdan) "
              "sherikning yangi buyurtmasini ko'rsatadi",
              NAT.get("or2") and not u2a.get("bor") and u2b[1] == 1 and (u2b[0] or {}).get("bor")
              and NAT["or2"] in ((u2b[0] or {}).get("matn") or "") and (u2b[0] or {}).get("belgi") == "1", (u2a, u2b, NAT.get("or2")))
        u3a, u3b = NAT.get("u3_a") or [{}, 0], NAT.get("u3_b") or [{}, 0]
        check("U4 sahifaga qaytildi (`visibilitychange`) va keyin `focus` — muddat o'tgan bo'lsa yozmasdan yangilanadi (har biri 1 so'rov); "
              "muddat ichida qayta qaytish — so'rov yo'q",
              NAT.get("or3") and u3a[1] == 1 and NAT["or3"] in ((u3a[0] or {}).get("matn") or "") and NAT.get("or4") and u3b[1] == 1
              and NAT["or4"] in ((u3b[0] or {}).get("matn") or "") and NAT.get("u3_c") == 0, (u3a, u3b, NAT.get("u3_c")))
        check("U5 forma yopiq — sahifaga qaytilganda ham so'rov yo'q", NAT.get("u4") == 0, NAT.get("u4"))
        _u8 = [NAT.get("u8_500") or [{}, 0, None], NAT.get("u8_tarmoq") or [{}, 0, None]]
        _u8k = NAT.get("u8_keyin") or [{}, 0]
        check("U8 yangilash so'rovi yiqildi (500 va tarmoq) — «K219 Ustun» eslatmasi o'chmadi (oldingi ma'lumot), eskirgan deb qoldi (keyingi "
              "qaytishda yana so'raldi); server tiklangach — yangi so'rov, eslatma joyida (review219 №3: ilgari hamma eslatma o'chib, qaytishda "
              "so'rov ham ketmasdi)",
              all((x[0] or {}).get("bor") and str(NAT.get("or3")) in ((x[0] or {}).get("matn") or "") and x[1] == 1 and x[2] == 1 for x in _u8)
              and (_u8k[0] or {}).get("bor") and _u8k[1] == 1, (_u8, _u8k))
        check("U6 «Loy retseptlari»: yangi va tahrir nom maydoni ko'pi bilan 87 belgi", NAT.get("u6") == {"a": 87, "b": 87}, NAT.get("u6"))
        check("U7 JS xatosi yo'q", not XATO, XATO[:3])

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
