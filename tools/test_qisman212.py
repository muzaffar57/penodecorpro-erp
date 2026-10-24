#!/usr/bin/env python3
"""
test_qisman212.py — kech156 (zip 212 «Qisman buyurtma foydasi» — egasi tanlovi 24.10 17:1x, tugmali savol).

NIMA UCHUN KERAK
  Buyurtma QISMAN topshirilib «Tayyor» qilinsa (yoki o'chirilsa — o'sha yakunlash qoidasi) detal topshirilgan qismga qisqaradi, berilmagan
  qism xomashyosi omborga qaytadi — demak u ishlab chiqarilmagan. O'LCHANGAN (`work/k212/probe212.py`, zip 211 kodi; SQLite = PG AYNAN):
  berilmagan qism baribir hisoblanib qolardi —
    F1 Panel / o'lchamsiz Donali umuman berilmagan (miqdor 0): `quantity or 1` — tannarx, kesilgan blok, qoplamachi bonusi 1 dona bilan;
    F2 o'lchamli Donali: `length` (jami metr ekvivalenti) qisqarmasdi — tannarx, kesilgan blok; qolgan qism qaytishida ham to'liq — ombor
       sarfi kam (10 dan 4 berilsa 6 emas 10 donalik xomashyo qaytardi); keyingi qaytarish / brak hajmi va tannarxi ham shishgan;
    F3 karniz ichidagi qo'shimcha detal qisqarmasdi — tannarx, qoplamachi bonusi, «metr» hodim oyligi, kesilgan blok, keyingi qaytarish /
       brak (xomashyosi esa omborga ulushda qaytgan);
    F4 «Tekshiruv»: umuman berilmagan karniz — yolg'on «narxi 0 — unutilgan» ogohlantirishi.
  To'g'ri natija: QISMAN buyurtma = NAZORAT buyurtma (faqat AYNAN topshirilgan qism bilan to'liq topshirilib «Tayyor» qilingan).
BO'LIMLAR
  A — qisman = nazorat: foyda (/api/orders/{id}/profit), oylik hisobot (kesilgan blok, metr, m², dona, qoplamachi bonusi, sof foyda,
      tannarx, usta KPI, hodim «birlik bo'yicha» — metr / dona / blok), ombor sarfi; Panel, Donali (o'lchamsiz / o'lchamli, qoplamali),
      karniz (ichki profil / panel bo'lak), o'chirish; «Tayyor» dan keyin qaytarish va brak (hajm, tannarx, ombor).
  B — detal holati: o'lchamli Donali `length`, ichki detal (uzunlik / miqdor / hajm / narx), yuk ulushi (qolgan detalga nisbatan);
      to'liq topshirilgan detal o'zgarmaydi; `_detal_miqdori` (NULL — 1, 0 — 0); miqdori NULL eski detal — 1 (avvalgidek).
  C — oylar: yuk noyabrda, qisman «Tayyor» dekabrda — noyabr O'ZGARMAYDI, dekabrga qo'shimcha 0 (nazorat bilan AYNAN).
  D — o'chirish → tiklash (surat v3): detal / ichki detal / ulush / holat AYNAN qaytadi, ombor AYNAN o'chirishdan oldingi.
  E — zip 212 dan OLDIN o'chirilgan (surat v2) buyurtma tiklanadi — eski qaytish qoidasi bilan (ombor siljimaydi); surat versiyasi.
  F — «Tekshiruv»: umuman berilmagan karniz — «narxi 0» yo'q; haqiqiy narxsiz detal (ochiq va to'liq «Tayyor») — bor.
  G — buyurtmani ko'rish (o'chirish rejasi — oldindan hisob) detal / ichki detal / ulushni o'zgartirmaydi.
  S — statik: yordamchi, eski oylar (2026-10 gacha) tsikli o'zgarmagan.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL.
Asl kodga (zip 211) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_qisman212.py
"""
import os
import io
import sys
import json
import inspect
import tempfile
import datetime
import contextlib
from types import SimpleNamespace

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qisman212_test"
_T = tempfile.mkdtemp(prefix="k212_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k212.db')}"
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


def yaqin(a, b, eps=1e-6):
    try:
        return abs(float(a) - float(b)) <= eps
    except (TypeError, ValueError):
        return False


with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, Master, Order, Employee, Delivery, FinishedProduct  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k212_a", PAROL, UserRole.ADMIN, "K212 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="K212 Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
P = Project(company_id=1, client_name="K212 mijoz", project_name="K212 loyiha", client_phone="+998901112212", total_budget=0, total_paid=0)
US = Master(company_id=1, name="K212 Usta", phone="+998900002212", kpi_percent=10)
s.add_all([PENO, P, US])
s.commit()
ID = {"PENO": PENO.id, "P": P.id, "US": US.id}
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lg = A.post("/login", data={"username": "k212_a", "password": PAROL}, follow_redirects=False)
BUGUN = services._tashkent_date() if hasattr(services, "_tashkent_date") else datetime.date.today()
Y, M = BUGUN.year, BUGUN.month

HODIM = {}
for _t in ("metr", "dona", "blok"):
    _r = A.post("/api/employees", json={"name": f"K212 {_t}chi", "pay_type": "per_unit", "per_unit_rate": 1000, "per_unit_type": _t})
    if _r.status_code in (200, 201):
        HODIM[_t] = _r.json().get("id")
s = SessionLocal()
for _eid in HODIM.values():
    _e = s.get(Employee, _eid)
    if _e is not None:
        _e.hire_date = datetime.datetime(2026, 1, 1)
s.commit()
s.close()


def js(r):
    try:
        return r.json()
    except Exception:                   # noqa: BLE001
        return {}


def buyurtma(items):
    tana = {"project_id": ID["P"], "order_type": "product", "recipe_id": None, "master_id": ID["US"],
            "deadline": (BUGUN + datetime.timedelta(days=3)).isoformat(), "is_draft": False, "base_price": 600000, "loy_kg": None,
            "items": [dict({"category": None, "width": None, "thickness": None, "length": 0, "quantity": 1, "unit_price": 0,
                            "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None}, **it)
                      for it in items]}
    r = A.post("/api/orders", json=tana)
    if r.status_code == 409:
        r = A.post("/api/orders?confirm_shortage=true", json=tana)
    return js(r).get("id") if r.status_code == 200 else None


def topshir(oid, miqdorlar):
    """miqdorlar: {detal nomi: miqdor | None (qolganining hammasi)}; ro'yxatda yo'q detal — topshirilmaydi."""
    if not oid:
        return 0
    h = js(A.get(f"/api/orders/{oid}/delivery-status")).get("items") or []
    items = []
    for x in h:
        if x.get("name") not in miqdorlar:
            continue
        q = miqdorlar[x["name"]]
        q = x.get("remaining", 0) if q is None else q
        if q > 0.0001:
            items.append({"order_item_id": x["id"], "quantity": q})
    r = A.post("/api/deliveries", json={"order_id": oid, "items": items, "received_by": "K212", "notes": "", "transport_carrier": "",
                                        "transport_cost": 0, "transport_payer": "client"})
    return r.status_code


def stok():
    s2 = SessionLocal()
    try:
        return float(s2.get(Inventory, ID["PENO"]).stock_quantity)
    finally:
        s2.close()


def holat(oid):
    s2 = SessionLocal()
    try:
        o = s2.get(Order, oid) if oid else None
        if o is None:
            return {"items": [], "status": None}
        return {"status": o.status.value, "total": float(o.total_amount or 0),
                "agreed": None if o.agreed_amount is None else float(o.agreed_amount), "num": o.order_number,
                "json": o.ochirish_yopish_json,
                "items": [{"id": it.id, "name": it.name, "qty": None if it.quantity is None else float(it.quantity),
                           "len": None if it.length is None else float(it.length), "price": float(it.unit_price or 0),
                           "total": float(it.total_price or 0),
                           "sub": [(sd.id, None if sd.length is None else float(sd.length), None if sd.quantity is None else float(sd.quantity),
                                    round(float(sd.volume_m3 or 0), 9), float(sd.total_price or 0)) for sd in (it.sub_details or [])],
                           "ulush": sorted((di.id, None if di.ulush is None else round(float(di.ulush), 9)) for di in (it.deliveries or []))}
                          for it in sorted(o.items, key=lambda x: x.id)]}
    finally:
        s2.close()


def detal(h, nom):
    for it in h.get("items") or []:
        if it["name"] == nom:
            return it
    return {}


def salomatlik(num):
    r = A.get("/api/system/health-check")
    if r.status_code != 200:
        return None
    iss = (js(r).get("financial") or {}).get("issues", [])
    return [x.get("type") for x in iss if f"{num}" in str(x.get("label", ""))]


def foyda(oid):
    r = A.get(f"/api/orders/{oid}/profit") if oid else None
    if r is None or r.status_code != 200:
        return {"xato": getattr(r, "status_code", None)}
    j = js(r)
    return {"tan_narxi": round(float(j.get("tan_narxi", 0) or 0), 4), "foyda": round(float(j.get("foyda", 0) or 0), 4)}


KEYS = ("jami_blok", "jami_metr", "jami_m2", "jami_dona", "qoplamachi_bonus_avtomatik", "sof_foyda", "tannarx_jami",
        "ishlab_chiqarish_xarajat", "buyurtmalar_foydasi", "usta_kpi_xarajat", "daromad")


def hisobot():
    r = A.get(f"/api/finance/report?year={Y}&month={M}")
    j = js(r) if r.status_code == 200 else {}
    d = {k: j.get(k) for k in KEYS}
    for b in j.get("hodimlar_breakdown") or []:
        for _t, _eid in HODIM.items():
            if b.get("employee_id") == _eid or b.get("id") == _eid or b.get("name") == f"K212 {_t}chi":
                d[f"hodim_{_t}"] = b.get("amount")
    return d


def farq(a, b):
    out = {}
    for k in set(a) | set(b):
        x, y = a.get(k), b.get(k)
        if isinstance(x, (int, float, type(None))) and isinstance(y, (int, float, type(None))):
            out[k] = round(float(y or 0) - float(x or 0), 6)
    return out


def bir_yurish(items, miqdorlar, ochir=False):
    h0, s0 = hisobot(), stok()
    q = buyurtma(items)
    d = topshir(q, miqdorlar)
    rr = A.delete(f"/api/orders/{q}") if ochir else A.post(f"/api/orders/{q}/ready")
    s2 = stok()
    h1 = hisobot()
    return {"id": q, "deliver": d, "ready": rr.status_code, "profit": foyda(q), "stok": round(s0 - s2, 9), "oy": farq(h0, h1)}


SAHNA = {}
_OY_EPS = {"jami_blok": 0.0101, "usta_kpi_xarajat": 1.01, "sof_foyda": 1.01, "buyurtmalar_foydasi": 1.01}


def sahna(nom, a, b, b_topshir, b_nazorat, ochir=False):
    """a, b — detal lug'atlari; b_topshir — B dan topshiriladigan miqdor (0 — umuman); b_nazorat — B' (None — faqat A)."""
    _nom = lambda d, t: dict(d, name=f"{d['name']} {nom}-{t}")
    a_q, b_q = _nom(a, "q"), _nom(b, "q")
    m = {a_q["name"]: None}
    if b_topshir:
        m[b_q["name"]] = b_topshir
    qisman = bir_yurish([a_q, b_q], m, ochir=ochir)
    nitems = [_nom(a, "n")] + ([_nom(b_nazorat, "n")] if b_nazorat else [])
    nazorat = bir_yurish(nitems, {x["name"]: None for x in nitems})
    SAHNA[nom] = {"qisman": qisman, "nazorat": nazorat, "b_nomi": b_q["name"], "a_nomi": a_q["name"]}
    _ok = (qisman["deliver"] == 200 and nazorat["deliver"] == 200 and qisman["ready"] == 200 and nazorat["ready"] == 200)
    fq, fn = qisman["profit"], nazorat["profit"]
    check(f"A-{nom}/foyda qisman = nazorat (tannarx / foyda)",
          _ok and yaqin(fq.get("tan_narxi"), fn.get("tan_narxi"), 0.01) and yaqin(fq.get("foyda"), fn.get("foyda"), 0.01),
          (qisman["deliver"], qisman["ready"], nazorat["deliver"], nazorat["ready"], fq, fn))
    # butun so'mga yaxlitlanadigan yig'indilar (hodim oyligi, usta KPI, sof foyda) — 1 so'm; `jami_blok` hisobotda 2 xonaga yaxlitlangan — yaxlitlangan JAMI ning farqi asos (oydagi boshqa buyurtmalar) ga qarab 0,01 ga siljishi
    # mumkin (0,03 ↔ 0,04); aniq blok miqdori — «blok» hodimi oyligida (yaxlitlanmagan miqdor × 1 000) tekshiriladi
    _oyf = {k: (qisman["oy"].get(k), nazorat["oy"].get(k)) for k in sorted(set(qisman["oy"]) | set(nazorat["oy"]))
            if not yaqin(qisman["oy"].get(k) or 0, nazorat["oy"].get(k) or 0, _OY_EPS.get(k, 1.01 if k.startswith("hodim_") else 0.01))}
    check(f"A-{nom}/oylik hisobot qisman = nazorat (blok / metr / dona / qoplamachi / sof foyda / tannarx / usta KPI / hodimlar)",
          _ok and not _oyf, _oyf)
    check(f"A-{nom}/ombor sarfi qisman = nazorat", _ok and yaqin(qisman["stok"], nazorat["stok"], 1e-9),
          (qisman["stok"], nazorat["stok"]))


PANEL = lambda n, q, p, **k: dict({"name": n, "category": "panel", "width": 60, "thickness": 5, "length": 0, "quantity": q, "unit_price": p}, **k)
DONA = lambda n, q, p, **k: dict({"name": n, "category": "dona", "width": 0, "thickness": 0, "length": 0, "quantity": q, "unit_price": p}, **k)
ODONA = lambda n, q, p, L, **k: dict({"name": n, "category": "dona", "width": 40, "thickness": 20, "length": L, "quantity": q, "unit_price": p}, **k)
PROFIL = lambda n, L, p, **k: dict({"name": n, "category": "profil", "width": 20, "thickness": 10, "length": L, "quantity": 1, "unit_price": p}, **k)
SUB = lambda L, c=True: {"name": "ichki", "category": "profil", "width": 10, "thickness": 5, "length": L, "quantity": 1, "is_coated": c}
PSUB = lambda q, c=True: {"name": "ichki panel", "category": "panel", "width": 30, "thickness": 5, "length": 0, "quantity": q, "is_coated": c}
BLOK = lambda n, kerak, chiqishi=40, **k: dict({"name": n, "category": "blok", "length": kerak / chiqishi, "quantity": kerak,
                                                 "unit_price": 600_000 / chiqishi, "blok_birlik": "metr", "blok_chiqishi": chiqishi,
                                                 "blok_koef": 2, "notes": f"blok_narxi=600000,blok_yield={chiqishi}"}, **k)

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Qisman «Tayyor» / o'chirish = faqat topshirilgan qism bilan to'liq buyurtma (nazorat)")
sahna("panel_B0", PANEL("A panel", 4, 5000), PANEL("B panel", 6, 20000), 0, None)
sahna("panel_B2", PANEL("A panel", 4, 5000), PANEL("B panel", 6, 20000), 2, PANEL("B panel", 2, 20000))
sahna("panel_qoplamali_B0", PANEL("A panel", 4, 5000, is_coated=True), PANEL("B panel", 6, 20000, is_coated=True), 0, None)
sahna("dona_B0", DONA("A dona", 4, 6000), DONA("B dona", 10, 12000), 0, None)
sahna("dona_B4", DONA("A dona", 4, 6000), DONA("B dona", 10, 12000), 4, DONA("B dona", 4, 12000))
sahna("dona_qoplamali_B0", DONA("A dona", 4, 6000, is_coated=True), DONA("B dona", 10, 12000, is_coated=True), 0, None)
sahna("odona_B0", ODONA("A od", 4, 6000, 2), ODONA("B od", 10, 12000, 5), 0, None)
sahna("odona_B4", ODONA("A od", 4, 6000, 2), ODONA("B od", 10, 12000, 5), 4, ODONA("B od", 4, 12000, 2))
sahna("odona_qoplamali_B4", ODONA("A od", 4, 6000, 2, is_coated=True), ODONA("B od", 10, 12000, 5, is_coated=True), 4,
      ODONA("B od", 4, 12000, 2, is_coated=True))
sahna("profil_ichki_B0", PROFIL("A pr", 10, 10000), PROFIL("B pr", 10, 10000, sub_details=[SUB(10)]), 0, None)
sahna("profil_ichki_B4", PROFIL("A pr", 10, 10000), PROFIL("B pr", 10, 10000, sub_details=[SUB(10)]), 4,
      PROFIL("B pr", 4, 4000, sub_details=[SUB(4)]))
sahna("profil_qoplamali_ichki_B4", PROFIL("A pr", 10, 10000, is_coated=True),
      PROFIL("B pr", 10, 10000, is_coated=True, sub_details=[SUB(10)]), 4, PROFIL("B pr", 4, 4000, is_coated=True, sub_details=[SUB(4)]))
sahna("profil_panel_ichki_B4", PROFIL("A pr", 10, 10000), PROFIL("B pr", 10, 10000, sub_details=[PSUB(10)]), 4,
      PROFIL("B pr", 4, 4000, sub_details=[PSUB(4)]))
sahna("profil_panel_ichki_B0", PROFIL("A pr", 10, 10000), PROFIL("B pr", 10, 10000, sub_details=[PSUB(10)]), 0, None)
sahna("profil_B4", PROFIL("A pr", 10, 10000), PROFIL("B pr", 10, 10000), 4, PROFIL("B pr", 4, 4000))
sahna("blok_B40", BLOK("A blok", 40), BLOK("B blok", 100), 40, BLOK("B blok", 40))
sahna("ochir_dona_B0", DONA("A dona", 4, 6000), DONA("B dona", 10, 12000), 0, None, ochir=True)
sahna("ochir_odona_B4", ODONA("A od", 4, 6000, 2), ODONA("B od", 10, 12000, 5), 4, ODONA("B od", 4, 12000, 2), ochir=True)
sahna("ochir_profil_ichki_B4", PROFIL("A pr", 10, 10000), PROFIL("B pr", 10, 10000, sub_details=[SUB(10)]), 4,
      PROFIL("B pr", 4, 4000, sub_details=[SUB(4)]), ochir=True)
sahna("ochir_profil_panel_ichki_B0", PROFIL("A pr", 10, 10000), PROFIL("B pr", 10, 10000, sub_details=[PSUB(10)]), 0, None, ochir=True)


def _qaytar(oid, nom, miqdor, sabab):
    s2 = SessionLocal()
    try:
        _o = s2.get(Order, oid) if oid else None
        _it = [i for i in (_o.items if _o else []) if i.name == nom]
        iid, birlik = (_it[0].id, _it[0].delivery_unit) if _it else (None, "dona")
    finally:
        s2.close()
    tana = {"order_id": oid, "item_name": nom, "quantity": float(miqdor), "unit": birlik, "reason": sabab, "refund_amount": 0.0,
            "to_stock": sabab != "Brak", "order_item_id": iid}
    if sabab == "Brak":
        tana["brak_sabab"] = "ishchi"
        tana["brak_bosqich"] = "saqlash_tashish"
    st0 = stok()
    r = A.post("/api/returns", json=tana)
    st1 = stok()
    s2 = SessionLocal()
    try:
        fp = s2.query(FinishedProduct).filter(FinishedProduct.name == nom).order_by(FinishedProduct.id.desc()).first()
        fpd = (round(float(fp.volume_m3 or 0), 9), round(float(fp.cost_price or 0), 2)) if fp else (None, None)
    finally:
        s2.close()
    return {"status": r.status_code, "fp": fpd, "stok": round(st0 - st1, 9), "profit": foyda(oid)}


def qaytarish_sahna(nom, a, b, b_topshir, b_nazorat, miqdor, sabab):
    _nom = lambda d, t: dict(d, name=f"{d['name']} {nom}-{t}")
    a_q, b_q, a_n, b_n = _nom(a, "q"), _nom(b, "q"), _nom(a, "n"), _nom(b_nazorat, "n")
    q = buyurtma([a_q, b_q])
    topshir(q, {a_q["name"]: None, b_q["name"]: b_topshir})
    A.post(f"/api/orders/{q}/ready")
    rq = _qaytar(q, b_q["name"], miqdor, sabab)
    n = buyurtma([a_n, b_n])
    topshir(n, {a_n["name"]: None, b_n["name"]: None})
    A.post(f"/api/orders/{n}/ready")
    rn = _qaytar(n, b_n["name"], miqdor, sabab)
    _ok = rq["status"] == 200 and rn["status"] == 200
    if sabab != "Brak":
        check(f"A-{nom}/hajm qaytgan mahsulot hajmi va tannarxi: qisman = nazorat",
              _ok and rq["fp"][0] is not None and yaqin(rq["fp"][0], rn["fp"][0], 1e-9) and yaqin(rq["fp"][1], rn["fp"][1], 0.01),
              (rq["status"], rn["status"], rq["fp"], rn["fp"]))
    check(f"A-{nom}/keyin ombor va buyurtma tannarxi: qisman = nazorat",
          _ok and yaqin(rq["stok"], rn["stok"], 1e-9) and yaqin(rq["profit"].get("tan_narxi"), rn["profit"].get("tan_narxi"), 0.01),
          (rq["status"], rn["status"], rq["stok"], rn["stok"], rq["profit"], rn["profit"]))


qaytarish_sahna("qayt_odona_B4", ODONA("A od", 4, 6000, 2), ODONA("B od", 10, 12000, 5), 4, ODONA("B od", 4, 12000, 2), 1, "Mijoz iltimosi")
qaytarish_sahna("qayt_profil_ichki_B4", PROFIL("A pr", 10, 10000), PROFIL("B pr", 10, 10000, sub_details=[SUB(10)]), 4,
                PROFIL("B pr", 4, 4000, sub_details=[SUB(4)]), 1, "Mijoz iltimosi")
qaytarish_sahna("brak_odona_B4", ODONA("A od", 4, 6000, 2), ODONA("B od", 10, 12000, 5), 4, ODONA("B od", 4, 12000, 2), 1, "Brak")
qaytarish_sahna("brak_profil_ichki_B4", PROFIL("A pr", 10, 10000), PROFIL("B pr", 10, 10000, sub_details=[SUB(10)]), 4,
                PROFIL("B pr", 4, 4000, sub_details=[SUB(4)]), 1, "Brak")
qaytarish_sahna("qayt_panel_B2", PANEL("A panel", 4, 5000), PANEL("B panel", 6, 20000), 2, PANEL("B panel", 2, 20000), 1, "Mijoz iltimosi")

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Detal holati qisman yakunlashdan keyin")
_h = holat(SAHNA["odona_B4"]["qisman"]["id"])
_b = detal(_h, SAHNA["odona_B4"]["b_nomi"])
check("B1 o'lchamli Donali (10 dona, 5 m ekv.) — 4 tasi topshirilgan: miqdor 4, `length` 5 × 0,4 = 2", yaqin(_b.get("qty"), 4)
      and yaqin(_b.get("len"), 2.0, 1e-9), _b)
_h = holat(SAHNA["profil_ichki_B4"]["qisman"]["id"])
_b = detal(_h, SAHNA["profil_ichki_B4"]["b_nomi"])
_sub = (_b.get("sub") or [(None, None, None, None, None)])[0]
_v0 = 0.10 * 0.05 / 2 * 10
check("B2 karniz 10 m dan 4 m: ichki profil bo'lak uzunligi 10 → 4, miqdor 1, hajm va narx 0,4 ulushda",
      yaqin(_b.get("len"), 4) and yaqin(_sub[1], 4, 1e-9) and yaqin(_sub[2], 1) and yaqin(_sub[3], _v0 * 0.4, 1e-9), (_b, _v0))
check("B3 karniz yuk ulushi qolgan detalga nisbatan: 0,4 → 1,0 (topshirilgan hammasi)",
      len(_b.get("ulush") or []) == 1 and yaqin((_b.get("ulush") or [(0, 0)])[0][1], 1.0, 1e-9), _b.get("ulush"))
_h = holat(SAHNA["profil_panel_ichki_B4"]["qisman"]["id"])
_b = detal(_h, SAHNA["profil_panel_ichki_B4"]["b_nomi"])
_sub = (_b.get("sub") or [(None, None, None, None, None)])[0]
check("B4 ichki PANEL bo'lak (10 dona) — miqdor 10 → 4, uzunlik o'zgarmaydi", yaqin(_sub[2], 4, 1e-9) and yaqin(_sub[1] or 0, 0), _b)
_h = holat(SAHNA["profil_ichki_B0"]["qisman"]["id"])
_b = detal(_h, SAHNA["profil_ichki_B0"]["b_nomi"])
_sub = (_b.get("sub") or [(None, None, None, None, None)])[0]
check("B5 umuman berilmagan karniz: uzunlik 0, ichki bo'lak 0, yuk yo'q", yaqin(_b.get("len"), 0) and yaqin(_sub[1], 0, 1e-9)
      and not _b.get("ulush"), _b)
_h = holat(SAHNA["profil_ichki_B4"]["nazorat"]["id"])
_b = [x for x in _h.get("items") or [] if x.get("sub")]
_b = _b[0] if _b else {}
check("B6 to'liq topshirilgan karniz (nazorat): ichki bo'lak 4 m va ulush 1,0 — o'zgarmagan",
      yaqin(((_b.get("sub") or [(0, 0)])[0])[1], 4, 1e-9) and yaqin(((_b.get("ulush") or [(0, 0)])[0])[1], 1.0, 1e-9), _b)
_dm = getattr(services, "_detal_miqdori", None)
check("B7 `services._detal_miqdori`: NULL — 1, 0 — 0, 2,5 — 2,5",
      _dm is not None and _dm(SimpleNamespace(quantity=None)) == 1.0 and _dm(SimpleNamespace(quantity=0)) == 0.0
      and _dm(SimpleNamespace(quantity=2.5)) == 2.5, _dm)
_o1 = buyurtma([PANEL("K212 null panel 1", 1, 20000)])
topshir(_o1, {"K212 null panel 1": None})
A.post(f"/api/orders/{_o1}/ready")
_f1 = foyda(_o1)
s = SessionLocal()
for _it in s.get(Order, _o1).items:
    _it.quantity = None
s.commit()
s.close()
_f2 = foyda(_o1)
check("B8 miqdori NULL eski detal — 1 dona deb (avvalgidek): tannarx o'zgarmaydi", "xato" not in _f1 and _f1 == _f2, (_f1, _f2))

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C. Oylar: yuk noyabrda, qisman «Tayyor» dekabrda — noyabr O'ZGARMAYDI, dekabrga qo'shimcha 0")


def oy_hisob(y, m):
    try:
        services.hisobot_xotirasini_tozala()
    except Exception:                      # noqa: BLE001
        pass
    s2 = SessionLocal()
    try:
        r = services.get_monthly_report(s2, y, m, company_id=1)
        return {"qop": float(r.get("qoplamachi_bonus_avtomatik") or 0), "metr": float(r.get("jami_metr") or 0),
                "m2": float(r.get("jami_m2") or 0), "blok": float(r.get("jami_blok") or 0), "dona": float(r.get("jami_dona") or 0)}
    finally:
        s2.close()


def oylar():
    return {(2026, 11): oy_hisob(2026, 11), (2026, 12): oy_hisob(2026, 12)}


def sana_yuk(oid, dt):
    s2 = SessionLocal()
    try:
        s2.query(Delivery).filter(Delivery.order_id == oid).update({Delivery.delivered_at: dt}, synchronize_session=False)
        s2.commit()
    finally:
        s2.close()


def sana_yopish(oid, dt):
    s2 = SessionLocal()
    try:
        s2.query(Order).filter(Order.id == oid).update({Order.completed_at: dt}, synchronize_session=False)
        s2.commit()
    finally:
        s2.close()


def oy_sahna(nom, items, miqdorlar):
    O0 = oylar()
    q = buyurtma(items)
    topshir(q, miqdorlar)
    sana_yuk(q, datetime.datetime(2026, 11, 10, 7, 0))
    O1 = oylar()
    rr = A.post(f"/api/orders/{q}/ready")
    sana_yopish(q, datetime.datetime(2026, 12, 15, 7, 0))
    O2 = oylar()
    d1 = {ym: {k: round(O1[ym][k] - O0[ym][k], 6) for k in O0[ym]} for ym in O0}
    d2 = {ym: {k: round(O2[ym][k] - O0[ym][k], 6) for k in O0[ym]} for ym in O0}
    return rr.status_code, d1, d2


_st, _q1, _q2 = oy_sahna("cq", [PROFIL("C karniz q", 10, 10000, is_coated=True, sub_details=[SUB(10)])], {"C karniz q": 4})
_stn, _n1, _n2 = oy_sahna("cn", [PROFIL("C karniz n", 4, 4000, is_coated=True, sub_details=[SUB(4)])], {"C karniz n": None})
check("C1 yuk paytida (noyabr): asosiy 4 m + ichki 0,4 × 10 m = 8 m (qoplamachi 8 000) — nazorat bilan AYNAN",
      yaqin(_q1[(2026, 11)]["qop"], 8000, 0.01) and yaqin(_n1[(2026, 11)]["qop"], 8000, 0.01), (_q1, _n1))
check("C2 qisman «Tayyor» dekabrda: noyabr O'ZGARMADI (8 000; kesilgan blok ham)",
      _st == 200 and yaqin(_q2[(2026, 11)]["qop"], _q1[(2026, 11)]["qop"], 0.01)
      and yaqin(_q2[(2026, 11)]["blok"], _q1[(2026, 11)]["blok"], 1e-6), (_st, _q1, _q2))
check("C3 dekabrga qo'shimcha 0 — berilmagan 6 m ning ichki bo'lagi qoplamachiga yozilmaydi (ilgari 0,6 × 10 = 6 000)",
      _st == 200 and yaqin(_q2[(2026, 12)]["qop"], 0, 0.01) and yaqin(_q2[(2026, 12)]["metr"], 0, 1e-6)
      and yaqin(_q2[(2026, 12)]["blok"], 0, 1e-6), _q2)
check("C4 noyabr + dekabr: qisman = nazorat (qoplamachi, metr, kesilgan blok)",
      _stn == 200 and all(yaqin(_q2[ym][k], _n2[ym][k], 0.01) for ym in _q2 for k in ("qop", "metr", "m2", "blok")), (_q2, _n2))

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. O'chirish → tiklash (surat v3): hammasi AYNAN qaytadi")
_dq = buyurtma([ODONA("D od A", 4, 6000, 2), ODONA("D od B", 10, 12000, 5),
                PROFIL("D karniz", 10, 10000, is_coated=True, sub_details=[SUB(10), PSUB(10)])])
topshir(_dq, {"D od A": None, "D od B": 4, "D karniz": 4})
_hd0, _sd0 = holat(_dq), stok()
_rd = A.delete(f"/api/orders/{_dq}")
_hd1, _sd1 = holat(_dq), stok()
_snap = json.loads(_hd1.get("json") or "{}") if _hd1.get("json") else {}
check("D1 qisman topshirilgan buyurtma o'chirildi: yakunlandi, surat v3 (ichki detal va ulushlar bilan)",
      _rd.status_code == 200 and _snap.get("v") == 3 and all("sub" in x and "ulush" in x for x in _snap.get("items") or [{}]),
      (_rd.status_code, _snap.get("v"), [list(x) for x in (_snap.get("items") or [])][:3]))
_bod = detal(_hd1, "D od B")
_bkr = detal(_hd1, "D karniz")
check("D2 o'chirishda yakunlash: o'lchamli Donali `length` 5 → 2, karniz ichki bo'laklari 0,4 ulushda, ulush 1,0",
      yaqin(_bod.get("len"), 2, 1e-9) and yaqin(_bkr["sub"][0][1], 4, 1e-9) and yaqin(_bkr["sub"][1][2], 4, 1e-9)
      and yaqin(_bkr["ulush"][0][1], 1.0, 1e-9) if _bkr.get("sub") and _bkr.get("ulush") else False, (_bod, _bkr))
_vq = 0.40 * 0.20 / 2 * 5 * 0.6 + (0.10 * 0.05 / 2 * 10 + 0.30 * 0.05 * 10) * 0.6 + 0.20 * 0.10 / 2 * 10 * 0.6
check("D3 o'chirishda omborga FAQAT berilmagan qism qaytdi (Donali 6/10, karniz 6/10 ichki bo'laklari bilan)",
      yaqin(_sd1 - _sd0, _vq, 1e-9), (_sd1 - _sd0, _vq))
_rt = A.post(f"/api/orders/{_dq}/restore")
_hd2, _sd2 = holat(_dq), stok()
_bez = lambda h: [{k: v for k, v in it.items() if k != "id"} for it in h.get("items") or []]
check("D4 tiklash: detallar (miqdor / uzunlik / narx / jami), ichki bo'laklar (uzunlik / miqdor / hajm / narx), yuk ulushlari, holat — "
      "o'chirishdan OLDINGI holat AYNAN", _rt.status_code == 200 and _bez(_hd2) == _bez(_hd0) and _hd2["status"] == _hd0["status"]
      and _hd2["total"] == _hd0["total"], (_rt.status_code, _bez(_hd0), _bez(_hd2)))
check("D5 tiklash: ombor qoldig'i o'chirishdan OLDINGI holat AYNAN", yaqin(_sd2, _sd0, 1e-9), (_sd0, _sd1, _sd2))
_rr = A.post(f"/api/orders/{_dq}/ready")
_hd3 = holat(_dq)
check("D6 tiklangandan keyin «Tayyor» — yana to'g'ri yakunlanadi (Donali 2, ichki 4 / 4, ulush 1,0)",
      _rr.status_code == 200 and yaqin(detal(_hd3, "D od B").get("len"), 2, 1e-9)
      and yaqin(detal(_hd3, "D karniz")["sub"][0][1], 4, 1e-9) and yaqin(detal(_hd3, "D karniz")["ulush"][0][1], 1.0, 1e-9)
      if detal(_hd3, "D karniz").get("sub") and detal(_hd3, "D karniz").get("ulush") else False, (_rr.status_code, _hd3))

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. Zip 212 dan OLDIN o'chirilgan (surat v2) buyurtma tiklanadi — eski qaytish qoidasi, ombor siljimaydi")
_eq = buyurtma([ODONA("E od A", 4, 6000, 2), ODONA("E od B", 10, 12000, 5)])
topshir(_eq, {"E od A": None, "E od B": 4})
_se0 = stok()
_re = A.delete(f"/api/orders/{_eq}")
_se1 = stok()
_eski_qaytgan = 0.40 * 0.20 / 2 * 5          # zip 212 dan oldin: qolgan 6 dona uchun B ning HAMMA (5 m ekv.) hajmi qaytardi
s = SessionLocal()
_oe = s.get(Order, _eq)
_sn = json.loads(_oe.ochirish_yopish_json or "{}")
_sn["v"] = 2
for _x in _sn.get("items") or []:
    _x.pop("sub", None)
    _x.pop("ulush", None)
_oe.ochirish_yopish_json = json.dumps(_sn, ensure_ascii=False)
_pe = s.get(Inventory, ID["PENO"])
_pe.stock_quantity = float(_pe.stock_quantity) + (_eski_qaytgan - (_se1 - _se0))       # eski kod qaytargan miqdorga keltiriladi
s.commit()
s.close()
_se1b = stok()
_rte = A.post(f"/api/orders/{_eq}/restore")
_se2 = stok()
check("E1 v2 surat (zip 212 dan oldin o'chirilgan) bilan tiklash: ombor o'chirishdan OLDINGI holat AYNAN (eski qoida bilan qayta yechildi)",
      _re.status_code == 200 and _rte.status_code == 200 and yaqin(_se1b - _se0, _eski_qaytgan, 1e-9) and yaqin(_se2, _se0, 1e-9),
      (_re.status_code, _rte.status_code, _se0, _se1, _se1b, _se2))
_ev = getattr(crud, "_ochirish_surati_eskimi212", None)
check("E2 surat versiyasi: v1 / v2 — eski, v3 / surat yo'q / buzuq — eski emas",
      _ev is not None and _ev(SimpleNamespace(ochirish_yopish_json='{"v": 2}')) is True
      and _ev(SimpleNamespace(ochirish_yopish_json='{"items": []}')) is True
      and _ev(SimpleNamespace(ochirish_yopish_json='{"v": 3}')) is False and _ev(SimpleNamespace(ochirish_yopish_json=None)) is False
      and _ev(SimpleNamespace(ochirish_yopish_json="{buzuq")) is False, _ev)
_pr = getattr(services, "_ProratedItem", None)
_it_e = SimpleNamespace(category="dona", width=40, thickness=20, length=5.0, quantity=10.0, penoplast_id=None, is_coated=False,
                        price_per_m3=None, finished_product_id=None, recipe_id=None, unit_price=12000, unit_price_for_volume=None,
                        order=None, company_id=1, sub_details=[])
try:
    _pn = _pr(_it_e, 0.6)
    _po = _pr(_it_e, 0.6, eski212=True)
    _pv = (_pn.length, _po.length, _pn.quantity, _po.quantity)
except Exception as _e:                  # noqa: BLE001
    _pv = repr(_e)
check("E3 `_ProratedItem`: o'lchamli Donali qolgan 0,6 — `length` 3 (yangi), eski212 — 5; miqdor 6", isinstance(_pv, tuple)
      and yaqin(_pv[0], 3, 1e-9) and yaqin(_pv[1], 5, 1e-9) and yaqin(_pv[2], 6) and yaqin(_pv[3], 6), _pv)

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F. «Tekshiruv»: «narxi 0» ogohlantirishi")
_num_b0 = holat(SAHNA["profil_ichki_B0"]["qisman"]["id"]).get("num")
_t = salomatlik(_num_b0)
check("F1 umuman berilmagan karniz (qisman «Tayyor»): «narxi 0» ogohlantirishi YO'Q", _t is not None and "zero_price_item" not in _t, _t)
_fo = buyurtma([PROFIL("F narxsiz ochiq", 10, 0)])
_tf = salomatlik(holat(_fo).get("num"))
check("F2 ochiq buyurtmada narxi 0 detal — ogohlantirish BOR (o'zgarmagan)", _tf is not None and "zero_price_item" in _tf, _tf)
_fr = buyurtma([PANEL("F narxsiz tayyor", 3, 0)])
topshir(_fr, {"F narxsiz tayyor": None})
A.post(f"/api/orders/{_fr}/ready")
_tr = salomatlik(holat(_fr).get("num"))
check("F3 to'liq topshirilgan «Tayyor» buyurtmada narxi 0 detal — ogohlantirish BOR (o'zgarmagan)", _tr is not None and "zero_price_item" in _tr,
      (_tr, holat(_fr).get("status")))

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G. Buyurtmani ko'rish (o'chirish rejasi — oldindan hisob) hech narsani o'zgartirmaydi")
_gq = buyurtma([ODONA("G od", 10, 12000, 5), PROFIL("G karniz", 10, 10000, sub_details=[SUB(10), PSUB(10)])])
topshir(_gq, {"G od": 4, "G karniz": 4})
_hg0 = holat(_gq)
_gr = A.get(f"/api/orders/{_gq}")
_hg1 = holat(_gq)
_och = (js(_gr).get("ochirish") or {})
check("G1 GET /api/orders/{id} (o'chirish rejasi bilan) — detal / ichki bo'lak / ulush / summa O'ZGARMADI",
      _gr.status_code == 200 and bool(_och) and _hg0 == _hg1, (_gr.status_code, list(_och)[:6], _hg0, _hg1))

_s = SessionLocal()
try:
    _og = _s.get(Order, _gq)
    _oldin = [(it.id, it.length, it.quantity, [(sd.length, sd.quantity, sd.volume_m3) for sd in it.sub_details],
               [di.ulush for di in it.deliveries]) for it in _og.items]
    _fin = crud.ochirish_yopish_hisobi(_s, _og)
    _keyin = [(it.id, it.length, it.quantity, [(sd.length, sd.quantity, sd.volume_m3) for sd in it.sub_details],
               [di.ulush for di in it.deliveries]) for it in _og.items]
    _dirty = bool(_s.dirty)
finally:
    _s.rollback()
    _s.close()
check("G2 oldindan hisob (`ochirish_yopish_hisobi`) — sessiyadagi detal / ichki bo'lak / ulush ham o'zgarmaydi (keyingi saqlash yozib "
      "yubormasin)", _oldin == _keyin and not _dirty and bool(_fin), (_oldin, _keyin, _dirty))

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. Yopilgan oylar o'zgarmaydi: 2026-10 dan OLDIN yakunlangan buyurtmaning miqdori 0 detali — eski qoida (1 dona)")


def sana_yop(oid, dt):
    s2 = SessionLocal()
    try:
        s2.query(Order).filter(Order.id == oid).update({Order.completed_at: dt}, synchronize_session=False)
        s2.commit()
    finally:
        s2.close()


_hq = buyurtma([PANEL("H panel A", 4, 5000), PANEL("H panel B", 6, 20000)])
topshir(_hq, {"H panel A": None})
_hr = A.post(f"/api/orders/{_hq}/ready")
sana_yop(_hq, datetime.datetime(2026, 9, 15, 7, 0))
_hf_sen = foyda(_hq)
_hs = oy_hisob(2026, 9)
sana_yop(_hq, datetime.datetime(2026, 10, 5, 7, 0))
_hf_okt = foyda(_hq)
check("H1 sentabrda yakunlangan (yopilgan oy): berilmagan panel — eski qoida, tannarx 75 000 (asl kod bilan AYNAN; o'tgan oy o'zgarmaydi)",
      _hr.status_code == 200 and yaqin(_hf_sen.get("tan_narxi"), 75000, 0.01), (_hr.status_code, _hf_sen))
check("H2 sentabr hisoboti (eski tsikl): kesilgan blok 0,15 (A 0,12 + berilmagan B 1 dona 0,03) — asl kod bilan AYNAN",
      yaqin(_hs.get("blok"), 0.15, 1e-6), _hs)
check("H3 o'sha buyurtma oktabrda yakunlangan bo'lsa (ochiq oy) — to'g'ri qoida: tannarx 60 000", yaqin(_hf_okt.get("tan_narxi"), 60000, 0.01),
      _hf_okt)
_dm = getattr(services, "_detal_miqdori", None)
_sen = SimpleNamespace(quantity=0, order=SimpleNamespace(completed_at=datetime.datetime(2026, 9, 30, 18, 59)))
_okt = SimpleNamespace(quantity=0, order=SimpleNamespace(completed_at=datetime.datetime(2026, 9, 30, 19, 0)))
check("H4 chegara Toshkent vaqti bilan: 30.09 23:59 da yakunlangan — 1, 01.10 00:00 da — 0; chegara (2026, 10)",
      _dm is not None and getattr(services, "QISMAN_MIQDOR0_BOSHI", None) == (2026, 10) and _dm(_sen) == 1.0 and _dm(_okt) == 0.0,
      (getattr(services, "QISMAN_MIQDOR0_BOSHI", None), _dm(_sen) if _dm else None, _dm(_okt) if _dm else None))

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("I. Suratsiz o'chirish (yuk xatisiz, faqat «Ortiqcha» omborga) → tiklash: ombor AYNAN (yangi va zip 212 dan oldingi o'chirish)")


def ortiqcha(oid, nom, miqdor):
    s2 = SessionLocal()
    try:
        _it = [i for i in s2.get(Order, oid).items if i.name == nom]
        iid = _it[0].id if _it else None
    finally:
        s2.close()
    return A.post("/api/returns", json={"order_id": oid, "item_name": nom, "quantity": float(miqdor), "unit": "dona", "reason": "Ortiqcha",
                                       "refund_amount": 0.0, "to_stock": True, "order_item_id": iid}).status_code


def loy_manba(oid):
    s2 = SessionLocal()
    try:
        return json.loads(s2.get(Order, oid).loy_manba_json or "{}")
    finally:
        s2.close()


_iq = buyurtma([ODONA("I od A", 4, 6000, 2), ODONA("I od B", 10, 12000, 5)])
_ior = ortiqcha(_iq, "I od B", 4)
_si0 = stok()
_rid = A.delete(f"/api/orders/{_iq}")
_si1 = stok()
_hi1 = holat(_iq)
_lm = loy_manba(_iq)
_yangi_q = 0.40 * 0.20 / 2 * 2 + 0.40 * 0.20 / 2 * 5 * 0.6        # A to'liq + B ning 6 / 10 qismi (o'lchamli — `length` ulushda)
check("I1 suratsiz o'chirish: omborga A + B ning 6 / 10 qismi qaytdi (0,20 blok; ilgari 0,28), belgi `op212` bor, surat yo'q",
      _ior == 200 and _rid.status_code == 200 and yaqin(_si1 - _si0, _yangi_q, 1e-9) and _lm.get("op212") == 1 and not _hi1.get("json"),
      (_ior, _rid.status_code, _si1 - _si0, _yangi_q, _lm, bool(_hi1.get("json"))))
_rti = A.post(f"/api/orders/{_iq}/restore")
_si2 = stok()
check("I2 tiklash: ombor o'chirishdan OLDINGI holat AYNAN; belgi olib tashlandi", _rti.status_code == 200 and yaqin(_si2, _si0, 1e-9)
      and "op212" not in loy_manba(_iq), (_rti.status_code, _si0, _si1, _si2, loy_manba(_iq)))
_rid2 = A.delete(f"/api/orders/{_iq}")
_si3 = stok()
_eski_q = 0.40 * 0.20 / 2 * 2 + 0.40 * 0.20 / 2 * 5                # zip 212 dan oldin: B ning `length` i to'liq qaytardi
s = SessionLocal()
_oi = s.get(Order, _iq)
_lmd = json.loads(_oi.loy_manba_json or "{}")
_lmd.pop("op212", None)
_oi.loy_manba_json = json.dumps(_lmd, ensure_ascii=False) if _lmd else None
_pi = s.get(Inventory, ID["PENO"])
_pi.stock_quantity = float(_pi.stock_quantity) + (_eski_q - (_si3 - _si2))      # eski kod qaytargan miqdorga keltiriladi
s.commit()
s.close()
_rti2 = A.post(f"/api/orders/{_iq}/restore")
_si4 = stok()
check("I3 zip 212 dan OLDIN (belgisiz) suratsiz o'chirilgan buyurtma tiklanadi — eski qoida bilan qayta yechiladi, ombor AYNAN",
      _rid2.status_code == 200 and _rti2.status_code == 200 and yaqin(_si4, _si2, 1e-9), (_rid2.status_code, _rti2.status_code, _si2, _si3, _si4))
_ob = getattr(services, "ochirish_ombori212mi", None)
check("I4 `services.ochirish_ombori212mi`: belgi bor — True, yo'q / bo'sh / buyurtma yo'q — False",
      _ob is not None and _ob(SimpleNamespace(loy_manba_json='{"o": {}, "op212": 1}')) is True
      and _ob(SimpleNamespace(loy_manba_json='{"o": {}}')) is False and _ob(SimpleNamespace(loy_manba_json=None)) is False and _ob(None) is False,
      _ob)

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
_src_pr = inspect.getsource(services.calculate_order_profit)
_src_v = inspect.getsource(services._item_volume_m3)
_src_q = inspect.getsource(services._qoplama_birliklari)
check("S1 foyda / hajm / qoplamachi birliklarida `quantity or 1` yo'q — `_detal_miqdori`",
      "quantity or 1)" not in _src_pr.split("# ── 1A.")[0] and "qty = _detal_miqdori(item)" in _src_pr
      and "qty = _detal_miqdori(item)" in _src_v and 'r["dona"] += _detal_miqdori(item)' in _src_q, "")
_src_m = inspect.getsource(services.get_monthly_report)
check("S2 2026-10 gacha bo'lgan oylar tsikli (eski qoida) O'ZGARMAGAN — `jami_dona += float(item.quantity or 1)`",
      "jami_dona += float(item.quantity or 1)" in _src_m and "jami_metr += uzunlik_m * float(item.quantity or 1)" in _src_m, "")
_src_f = inspect.getsource(crud.finalize_partial_order_quantities)
check("S3 yakunlash: ichki detallar faqat haqiqiy yakunlashda (oldindan hisobda — yo'q)",
      "if not faqat_hisob:\n            _qisman_ichki_detallar(item, fraction)" in _src_f, "")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
