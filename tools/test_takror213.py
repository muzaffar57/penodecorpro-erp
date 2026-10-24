#!/usr/bin/env python3
"""
test_takror213.py — kech156 (zip 213 «Bu takror emasmi?» — egasi tanlovlari 24.10: «Bu takror emasmi? (Tavsiya)», ko'rinish — «Qatorda
eslatma (Tavsiya)», so'ng — «Ochiq buyurtma ham (Tavsiya)»).

NIMA UCHUN KERAK
  ORD-068 (production, 23.10): «hammasi topshirildi» deyilgan karniz aslida berilmagan; 5 kundan keyin sherigi YANGI buyurtmada uni yana
  yozgan — bitta detal ikki marta. Haqiqiy ma'lumotda qayta buyurtma ko'p (51 loyihadan 9 tasida keyingi buyurtmada xuddi shu nomli detal) —
  shuning uchun bloklamaydi, faqat ko'rsatadi: buyurtma oynasida detal nomi yozilganda qator ostida «ℹ️ Bu loyihada: ORD-064-4 — 72 m
  (hali berilmagan) · ORD-064-3 — 72 m berilgan (19.10)» (yuk xati bilan berilgan va ochiq buyurtmada hali berilmagan). Asl kodda
  (zip 212) bunday ma'lumot ham, marshrut ham yo'q.
BO'LIMLAR
  S — manba: marshrut ruxsati, eslatma joyi (`.i-takror`, matn `textContent` bilan), ulanish joylari (nom yozilganda, loyiha tanlanganda,
      tahrir / qoralama yuklanganda, tayyor mahsulot tanlanganda, forma ochilganda — eski ma'lumot tozalanadi), yig'ilgan qator belgisi.
  K — nom kaliti (`crud.detal_nomi_kaliti`) va brauzerdagi `takrorKalit` — AYNAN bir natija (node).
  A — `GET /api/projects/{id}/berilgan-detallar`: yuk xati bilan berilgan detallar va OCHIQ buyurtmadagi hali berilmagan qism (qolgan,
      `ochiq`); o'chirilgan / bekor / qoralama buyurtma, boshqa loyiha, boshqa korxona — yo'q; bir detalning bir necha yuki — jami va oxirgi
      sana (Toshkent); ochiqlari birinchi, keyin eng yangisi; `istisno` — tahrirlanayotgan buyurtma; «Tayyor» buyurtma — bor (ochiq emas);
      birlik, son ko'rinishi, o'tgan yil sanasi; bir buyurtmadagi bir xil nomli detallar — bitta yozuv; narx yo'q; ruxsat (buyurtma
      ko'rish) va korxona chegarasi (404), juda katta id — 422, kirmagan foydalanuvchi.
  U — HAQIQIY Chromium (Playwright) + lokal server: nom yozilganda eslatma (bitta so'rov; «berilgan», «hali berilmagan», qisman),
      mos kelmasa yo'q, Kirillda yozilsa ham, bazada Kirill nom, XSS nomli detal (bajarilmaydi), 3 tadan ko'p — «… yana N ta», loyiha
      almashtirilsa / olib tashlansa, tayyor mahsulot / MRP mahsuloti tanlansa, kechikkan javob (boshqa loyiha tanlangach) yozilmaydi,
      yig'ilgan qatorda belgi (telefonda ham ko'rinadi), saqlash BLOKLANMAYDI, tahrirda o'zi sanalmaydi (`istisno`), qoralama tiklanganda,
      forma qayta ochilganda saqlangan qatorlar yangi ma'lumot bilan (yangi yuk / o'chirilgan yuk), server xatosi keshda qolmaydi, Kirill
      rejimi, tungi rejim kontrasti, telefon (360 / 390 px), JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (U bo'limi faqat SQLite / TF1 da).
Asl kodga (zip 212) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_takror213.py
"""
import os
import io
import re
import sys
import json
import glob
import time
import socket
import tempfile
import datetime
import threading
import subprocess
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "takror213_test"
_T = tempfile.mkdtemp(prefix="k213_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k213.db')}"
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
        if callable(detail):
            try:
                detail = detail()
            except Exception as e:         # noqa: BLE001
                detail = f"{type(e).__name__}: {e}"
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def xav(f, *a, standart=None, **k):
    try:
        return f(*a, **k)
    except Exception as e:                 # noqa: BLE001
        print(f"    (bajarilmadi: {getattr(f, '__name__', f)} — {type(e).__name__}: {str(e)[:200]})")
        return standart


def rgb(s):
    m = re.findall(r"[\d.]+", s or "")
    return tuple(float(x) for x in m[:3]) if len(m) >= 3 else None


def _lum(c):
    def k(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * k(c[0]) + 0.7152 * k(c[1]) + 0.0722 * k(c[2])


def kontrast(a, b):
    if not a or not b:
        return 0
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ORD = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
MAIN_SRC = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
CRUD_SRC = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()


def _fn(src, bosh, keyingi="\nfunction "):
    i = src.find(bosh)
    if i < 0:
        return ""
    j = src.find(keyingi, i + len(bosh))
    return src[i:j if j > 0 else len(src)]


_mr = MAIN_SRC[MAIN_SRC.find('@app.get("/api/projects/{project_id}/berilgan-detallar")'):]
_mr = _mr[:_mr.find("\n@app.", 10)]
check("S1 marshrut `GET /api/projects/{id}/berilgan-detallar`: buyurtma KO'RISH ruxsati, loyiha faqat joriy korxonadan (404), "
      "`crud.loyiha_berilgan_detallar` (istisno bilan)",
      bool(_mr) and 'auth.ruxsat("buyurtma", "korish")' in _mr and "auth.project_of_company(db, project_id, _cid)" in _mr
      and "status_code=404" in _mr and "crud.loyiha_berilgan_detallar(db, project_id, _cid, istisno_order_id=istisno)" in _mr, _mr[:300])
_tq = _fn(ORD, "async function takrorQatori(row)")
check("S2 eslatma joyi — nom maydoni ostida `.i-takror` (role=status, rang — CSS o'zgaruvchisi); matn `textContent` / `createTextNode` "
      "bilan (`innerHTML` yo'q)",
      '<div class="i-takror" role="status" style="display:none;' in ORD and "color:var(--gold-dark)" in ORD
      and bool(_tq) and "innerHTML" not in _tq and "el.textContent = ''" in _tq and "document.createTextNode(" in _tq, len(_tq))
_lt = _fn(ORD, "async function loyihaTanlovi(sel)")
_sn = _fn(ORD, "function showNewForm()")
_ed = _fn(ORD, "async function editSelected(")
_rd = _fn(ORD, "async function restoreDraftLS(draft)")
_pf = ORD[ORD.find("row.querySelector('.i-name').value = fp.name;"):][:200]
check("S3 ulanish joylari: nom yozilganda (`oninput`), loyiha tanlanganda, tahrir / nusxa yuklangach, qoralama tiklangach, tayyor "
      "mahsulot / MRP mahsuloti tanlanganda; forma ochilganda eski ma'lumot tozalanadi va saqlangan qatorlar yangilanadi",
      "updateDetalSummary(this.closest('.detal'));takrorQatori(this.closest('.detal'))" in ORD
      and "takrorHammasi();" in _lt[:200] and "takrorTozala()" in _sn[:400]
      and "editInitialLoadDone = true;\n    // kech156 (zip 213)" in _ed and "takrorHammasi();" in _ed
      and "takrorHammasi();" in _rd and "takrorQatori(row);" in _pf
      and "takrorHammasi();\n  // kech152 (zip 194)" in _sn and "takrorQatori(row);" in _fn(ORD, "function selectMrpProduct(row, pt)"),
      (len(_lt), len(_sn), len(_ed), len(_rd)))
_uds = _fn(ORD, "function updateDetalSummary(row)")
check("S4 yig'ilgan qator xulosasida «ℹ️ loyihada bor» belgisi (`data-takror`) — BIRINCHI, tor ekranda faqat ikonka; matn doimiy "
      "(foydalanuvchi ma'lumoti emas)",
      "row.dataset.takror === '1'" in _uds and "parts.unshift('<span class=\"takror-belgi\"" in _uds
      and 'ℹ️<span class="tb-matn"> loyihada bor</span></span>' in _uds and "function _takrorBelgi(row, bor)" in ORD
      and "@media (max-width:900px){.detal-summary .takror-belgi .tb-matn{display:none}}" in ORD)
_cf = CRUD_SRC[CRUD_SRC.find("def loyiha_berilgan_detallar("):]
_cf = _cf[:_cf.find("\ndef ", 10)]
check("S5 `crud.loyiha_berilgan_detallar`: korxona, o'chirilmagan, qoralama / bekor emas, istisno; narx / summa maydoni YO'Q",
      "Order.company_id == company_id" in _cf and "Order.is_deleted.isnot(True)" in _cf
      and "Order.status.notin_([OrderStatus.DRAFT, OrderStatus.CANCELLED])" in _cf and "Order.id != istisno_order_id" in _cf
      and "price" not in _cf.split('"""')[-1] and "summa\"" not in _cf, len(_cf))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal, tashkent_vaqt   # noqa: E402
from models import UserRole, Inventory, Project, Master, Order, OrderStatus, Delivery, User, Rol, ReturnItem, ReturnReason   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K — nom kaliti (server = brauzer)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_KAL = ["Karniz M-06", "  karniz   M-06 ", "G‘isht o’ram", "Bo`yoq ʻoqʼ", "TO´G'RI", "\tPanel\u00a010x5\n", "", "Ustun 3 m"]
_kk = getattr(crud, "detal_nomi_kaliti", None)
check("K1 `crud.detal_nomi_kaliti`: kichik harf, apostrof turlari bitta, bo'shliqlar bitta, chetlar kesilgan",
      _kk is not None and _kk("  Karniz   M-06 ") == "karniz m-06" and _kk("G‘isht o’ram") == "g'isht o'ram"
      and _kk("Bo`yoq ʻoqʼ") == "bo'yoq 'oq'" and _kk("TO´G'RI") == "to'g'ri" and _kk("\tPanel\u00a010x5\n") == "panel 10x5"
      and _kk(None) == "" and _kk("Karniz M-06") == _kk("karniz m-06"),
      [_kk(x) for x in _KAL] if _kk else None)
_jsf = _fn(ORD, "function takrorKalit(s)")
_node = None
if _jsf:
    _kod = _jsf + "\nconsole.log(JSON.stringify(" + json.dumps(_KAL) + ".map(takrorKalit)));"
    _p = subprocess.run(["node", "-e", _kod], capture_output=True, text=True, timeout=60)
    try:
        _node = json.loads(_p.stdout.strip().splitlines()[-1])
    except Exception:                      # noqa: BLE001
        _node = _p.stderr[-300:]
check("K2 brauzerdagi `takrorKalit` (node) — server bilan AYNAN (8 ta nom)",
      _kk is not None and isinstance(_node, list) and _node == [_kk(x) for x in _KAL], (_node, [_kk(x) for x in _KAL] if _kk else None))

# ── ma'lumot
PAROL = "Parol123!"
s = SessionLocal()
_c2 = Company(name="K213 B korxona")
s.add(_c2)
s.commit()
CID2 = _c2.id
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k213_a", PAROL, UserRole.ADMIN, "K213 Admin", company_id=1)
    auth.create_user(s, "k213_b", PAROL, UserRole.ADMIN, "K213 B Admin", company_id=CID2)
    auth.create_user(s, "k213_yoq", PAROL, UserRole.MANAGER, "K213 Ruxsatsiz", company_id=1)
    auth.create_user(s, "k213_kor", PAROL, UserRole.MANAGER, "K213 Ko'ruvchi", company_id=1)
PENO = Inventory(company_id=1, item_name="K213 Penoplast", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
PENO2 = Inventory(company_id=CID2, item_name="K213 B Penoplast", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                  volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
P1 = Project(company_id=1, client_name="K213 mijoz", project_name="K213 loyiha", client_phone="+998901112213", total_budget=0, total_paid=0)
P2 = Project(company_id=1, client_name="K213 ikkinchi", project_name="K213 boshqa loyiha", client_phone="+998901112214", total_budget=0,
             total_paid=0)
P4 = Project(company_id=1, client_name="K213 bo'sh", project_name="K213 bo'sh loyiha", client_phone="+998901112215", total_budget=0,
             total_paid=0)
P3 = Project(company_id=CID2, client_name="K213 B mijoz", project_name="K213 B loyiha", client_phone="+998901112216", total_budget=0,
             total_paid=0)
US = Master(company_id=1, name="K213 Usta", phone="+998900002213", kpi_percent=10)
s.add_all([PENO, PENO2, P1, P2, P3, P4, US])
s.commit()
ID = {"PENO": PENO.id, "PENO2": PENO2.id, "P1": P1.id, "P2": P2.id, "P3": P3.id, "P4": P4.id, "US": US.id}
for _lg_, _rx in (("k213_yoq", {"loyiha": ["korish"], "tolov": ["korish"]}), ("k213_kor", {"buyurtma": ["korish"]})):
    _u = s.query(User).filter(User.username == _lg_).first()
    _r = Rol(company_id=1, nom="K213 " + _lg_, kod=None, ruxsatlar=json.dumps(_rx), tavsif="")
    s.add(_r)
    s.flush()
    _u.rol_id = _r.id
s.commit()
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    return c


A = mijoz("k213_a")
B = mijoz("k213_b")
NOW = datetime.datetime.utcnow()
BUGUN_T = tashkent_vaqt(NOW).date()


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


PROFIL = lambda n, L, p=10000: {"name": n, "category": "profil", "width": 20, "thickness": 10, "length": L, "quantity": 1,   # noqa: E731
                                "unit_price": p}
DONA = lambda n, q, p=5000: {"name": n, "category": "dona", "width": 0, "thickness": 0, "length": 0, "quantity": q,          # noqa: E731
                             "unit_price": p}
_SANOQ = [0]


def buyurtma(items, pid=None, c=None, peno=None, usta=True):
    _SANOQ[0] += 1
    items = list(items) + [DONA(f"K213 to'ldiruvchi {_SANOQ[0]}", _SANOQ[0])]      # 8 soniyalik takror-himoya bir xil deb olmasin
    tana = {"project_id": pid or ID["P1"], "order_type": "product", "recipe_id": None, "master_id": ID["US"] if usta else None,
            "deadline": (BUGUN_T + datetime.timedelta(days=3)).isoformat(), "is_draft": False, "base_price": 600000, "loy_kg": None,
            "items": [dict({"category": None, "width": None, "thickness": None, "length": 0, "quantity": 1, "unit_price": 0,
                            "is_coated": False, "penoplast_id": peno or ID["PENO"], "price_per_m3": None, "finished_product_id": None}, **it)
                      for it in items]}
    c = c or A
    r = c.post("/api/orders", json=tana)
    if r.status_code == 409:
        r = c.post("/api/orders?confirm_shortage=true", json=tana)
    return js(r).get("id") if r.status_code == 200 else None


def topshir(oid, miqdorlar, c=None, vaqt=None):
    """miqdorlar: {detal nomi: miqdor | None (qolganining hammasi)}; vaqt — shu yuk xatining `delivered_at` (UTC)."""
    c = c or A
    if not oid:
        return 0
    h = js(c.get(f"/api/orders/{oid}/delivery-status")).get("items") or []
    items = []
    for x in h:
        if x.get("name") not in miqdorlar:
            continue
        q = miqdorlar[x["name"]]
        q = x.get("remaining", 0) if q is None else q
        if q > 0.0001:
            items.append({"order_item_id": x["id"], "quantity": q})
    r = c.post("/api/deliveries", json={"order_id": oid, "items": items, "received_by": "K213", "notes": "", "transport_carrier": "",
                                        "transport_cost": 0, "transport_payer": "client"})
    if r.status_code == 200 and vaqt is not None:
        s2 = SessionLocal()
        d = s2.query(Delivery).filter(Delivery.order_id == oid).order_by(Delivery.id.desc()).first()
        d.delivered_at = vaqt
        s2.commit()
        s2.close()
    return r.status_code


def kun(n, soat=7, daqiqa=0):
    d = (NOW - datetime.timedelta(days=n)).date()
    return datetime.datetime(d.year, d.month, d.day, soat, daqiqa)


def db(fn):
    s2 = SessionLocal()
    try:
        r = fn(s2)
        s2.commit()
        return r
    finally:
        s2.close()


O = {}
AM = []
KAR = "Karniz M-06"
O["o1"] = buyurtma([PROFIL(KAR, 72)])
AM.append(topshir(O["o1"], {KAR: None}, vaqt=kun(5)))
AM.append(A.post(f"/api/orders/{O['o1']}/ready").status_code)
O["o2"] = buyurtma([PROFIL("karniz  m-06 ", 40), DONA("K213 ustun", 4)])
_n2 = (js(A.get(f"/api/orders/{O['o2']}/delivery-status")).get("items") or [{}])[0].get("name") if O["o2"] else None
AM.append(topshir(O["o2"], {_n2: 10, "K213 ustun": None}, vaqt=kun(3, 5)))
AM.append(topshir(O["o2"], {_n2: 20}, vaqt=kun(2, 19, 30)))            # Toshkent — ertasi kun 00:30
for _k, _L in (("o3", 15), ("o4", 16), ("o5", 17)):
    O[_k] = buyurtma([PROFIL(KAR, _L)])
    AM.append(topshir(O[_k], {KAR: None}, vaqt=kun(1)))
O["o6"] = buyurtma([PROFIL(KAR, 18)])                                    # umuman berilmagan
O["o7"] = buyurtma([PROFIL("K213 kirill nom", 12.5)])
AM.append(topshir(O["o7"], {"K213 kirill nom": None}, vaqt=kun(400)))   # o'tgan yil (yoki undan oldin)
XSS = '<img src=x onerror="window.__xss=1">'
O["o8"] = buyurtma([PROFIL("K213 xss nom", 1234.5)])
AM.append(topshir(O["o8"], {"K213 xss nom": None}, vaqt=kun(6)))
PLI = "Plintus P-1"
for _i in range(5):
    O[f"pl{_i}"] = buyurtma([PROFIL(PLI, _i + 1)])
    AM.append(topshir(O[f"pl{_i}"], {PLI: None}, vaqt=kun(20 - _i)))
O["p2"] = buyurtma([PROFIL(KAR, 50)], pid=ID["P2"])
AM.append(topshir(O["p2"], {KAR: None}, vaqt=kun(4)))
O["p3"] = buyurtma([PROFIL(KAR, 60)], pid=ID["P3"], c=B, peno=ID["PENO2"], usta=False)
AM.append(topshir(O["p3"], {KAR: None}, c=B, vaqt=kun(4)))


def _holatlar(s2):
    s2.get(Order, O["o3"]).is_deleted = True
    s2.get(Order, O["o4"]).status = OrderStatus.CANCELLED
    s2.get(Order, O["o5"]).status = OrderStatus.DRAFT
    # tartib: ochiq buyurtmalar ESKI (o6 — 10 kun oldin, o2 — 4 kun oldin) — «ochiq birinchi» qoidasisiz o1 (yopiq, yuk 5 kun oldin)
    # o6 dan oldin chiqardi; o6 karnizidan 5 m omborga ORTIQCHA qo'yilgan (qolgan = 18 − 5)
    s2.get(Order, O["o6"]).created_at = kun(10)
    s2.get(Order, O["o2"]).created_at = kun(4)
    _k6 = [it for it in s2.get(Order, O["o6"]).items if it.name == KAR][0]
    s2.add(ReturnItem(company_id=1, order_id=O["o6"], order_item_id=_k6.id, item_name=KAR, quantity=5, unit="metr", reason=ReturnReason.EXCESS,
                      ortiqcha_miqdor=5))
    for it in s2.get(Order, O["o7"]).items:
        if it.name == "K213 kirill nom":
            it.name = "Карниз Х"          # «Карниз Х» — eski (Kirill) yozuv
    for it in s2.get(Order, O["o8"]).items:
        if it.name == "K213 xss nom":
            it.name = XSS
    return True


_hl = db(_holatlar) if all(O.values()) else False
NUM = db(lambda s2: {k: s2.get(Order, v).order_number for k, v in O.items() if v})
check(f"T0 fikstura: kirish, {len(O)} buyurtma (3 loyiha, 2 korxona), yuk xatlari / «Tayyor» — hammasi 200",
      all(O.values()) and AM and all(x == 200 for x in AM) and _hl is True and len(NUM) == len(O), (O, AM))


def royxat(pid, istisno=None, c=None):
    c = c or A
    r = c.get(f"/api/projects/{pid}/berilgan-detallar" + (f"?istisno={istisno}" if istisno else ""))
    return r.status_code, js(r)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A — marshrut")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
st, j = royxat(ID["P1"])
D = (j or {}).get("detallar") if isinstance(j, dict) else None
D = D if isinstance(D, list) else []
KALITLAR = {"kalit", "nomi", "order_id", "buyurtma", "berilgan", "berilgan_matn", "birlik", "sana", "sana_matn", "qolgan", "qolgan_matn",
            "ochiq"}
check("A1 200; har yozuv — AYNAN 12 maydon (narx / summa / mijoz YO'Q)",
      st == 200 and D and all(set(d) == KALITLAR for d in D), (st, D[:2]))
_kar = [d for d in D if d.get("kalit") == "karniz m-06"]
_byo = {d.get("order_id"): d for d in _kar}


def tash_sana(v):
    t = tashkent_vaqt(v)
    return t.date().isoformat(), (t.strftime("%d.%m") if t.year == BUGUN_T.year else t.strftime("%d.%m.%Y"))


_d1, _d6 = _byo.get(O["o1"], {}), _byo.get(O["o6"], {})
check("A2 «Karniz M-06» — yuk xati bilan berilgan o1 (72 m, «Tayyor» — ochiq EMAS), o2 (nomi boshqacha yozilgan: kichik harf, ortiqcha "
      "bo'shliq) va OCHIQ buyurtmada hali berilmagan o6 (18 m − 5 m omborga ortiqcha = 13 m, sanasiz); o'chirilgan, bekor, qoralama, boshqa loyiha / korxona — YO'Q",
      set(_byo) == {O["o1"], O["o2"], O["o6"]} and _d1.get("berilgan") == 72 and _d1.get("berilgan_matn") == "72"
      and _d1.get("birlik") == "m" and _d1.get("buyurtma") == NUM["o1"] and _d1.get("qolgan") == 0 and _d1.get("ochiq") is False
      and _d6.get("berilgan") == 0 and _d6.get("qolgan") == 13 and _d6.get("qolgan_matn") == "13" and _d6.get("ochiq") is True
      and _d6.get("sana") is None and _d6.get("sana_matn") == "",
      ([(d["buyurtma"], d["berilgan"], d["qolgan"], d["ochiq"]) for d in _kar], NUM))
_d2 = _byo.get(O["o2"], {})
_e2 = tash_sana(kun(2, 19, 30))
check("A3 bir detalning 2 yuki — jami 30 m, oxirgi yuk sanasi TOSHKENT bo'yicha (UTC 19:30 → ertasi kun); ochiq buyurtma — qolgan 10 m",
      _d2.get("berilgan") == 30 and _d2.get("berilgan_matn") == "30" and _d2.get("sana") == _e2[0] and _d2.get("sana_matn") == _e2[1]
      and _d2.get("qolgan") == 10 and _d2.get("ochiq") is True, (_d2, _e2))
_ust = [d for d in D if d.get("kalit") == "k213 ustun"]
check("A4 donali detal — birligi «dona», miqdori 4, sanasi Toshkent bo'yicha",
      len(_ust) == 1 and _ust[0]["berilgan"] == 4 and _ust[0]["birlik"] == "dona" and _ust[0]["sana"] == tash_sana(kun(3, 5))[0], _ust)
_och = [bool(d.get("ochiq")) for d in D]
_sanalar = [d.get("sana") or "" for d in D if not d.get("ochiq")]
check("A5 tartib — ochiqlari birinchi (oxirgi yuk / yaratilgan bo'yicha yangisi birinchi), keyin oxirgi yuk sanasi bo'yicha: karniz — "
      "o2 (ochiq, yuk 2 kun oldin), o6 (ochiq, 10 kun oldin yaratilgan), o1 (yopiq, yuk 5 kun oldin)",
      _och == sorted(_och, reverse=True) and _sanalar == sorted(_sanalar, reverse=True)
      and [d.get("order_id") for d in _kar] == [O["o2"], O["o6"], O["o1"]], (_och, _sanalar, [d.get("buyurtma") for d in _kar]))
_kir = [d for d in D if d.get("order_id") == O["o7"] and d.get("berilgan") == 12.5]
_e7 = tash_sana(kun(400))
check("A6 kasrli miqdor «12,5», o'tgan yil sanasi «dd.mm.yyyy»; bazadagi Kirill nom — o'z holicha (kalit ham)",
      len(_kir) == 1 and _kir[0]["berilgan_matn"] == "12,5" and _kir[0]["sana_matn"] == _e7[1] and len(_e7[1]) == 10
      and _kir[0]["nomi"] == "Карниз Х", (_kir, _e7))
_xs = [d for d in D if d.get("order_id") == O["o8"] and d.get("berilgan") == 1234.5]
check("A7 ming ajratgich — «1 234,5» (NBSP); XSS nom — o'zgarishsiz (ekranga `textContent` bilan chiqadi)",
      len(_xs) == 1 and _xs[0]["berilgan_matn"] == "1\u00a0234,5" and _xs[0]["nomi"] == XSS, _xs)
_pl = [d for d in D if d.get("kalit") == "plintus p-1"]
check("A8 bir nomli detal 5 buyurtmada — 5 yozuv, eng yangisi birinchi", len(_pl) == 5 and [d["berilgan"] for d in _pl] == [5, 4, 3, 2, 1],
      [(d["buyurtma"], d["berilgan"], d["sana"]) for d in _pl])
st, j = royxat(ID["P1"], istisno=O["o2"])
_ki = [d for d in (j or {}).get("detallar", []) if d.get("kalit") == "karniz m-06"]
check("A9 `istisno` (tahrirlanayotgan buyurtma) — o'zi sanalmaydi, boshqasi qoladi",
      st == 200 and [d["order_id"] for d in _ki] == [O["o6"], O["o1"]] and not any(d.get("order_id") == O["o2"] for d in j.get("detallar", [])),
      _ki)
st2, j2 = royxat(ID["P2"])
check("A10 boshqa loyiha — faqat o'zining yuki (o1 / o2 yo'q)",
      st2 == 200 and [d["order_id"] for d in j2.get("detallar", []) if d["kalit"] == "karniz m-06"] == [O["p2"]], j2)
st4, j4 = royxat(ID["P4"])
check("A11 yuki yo'q loyiha — bo'sh ro'yxat", st4 == 200 and j4 == {"detallar": []}, (st4, j4))
_x1 = royxat(ID["P3"])
_x2 = royxat(ID["P1"], c=B)
_x3 = royxat(ID["P3"], c=B)
_x4 = royxat(987654)
check("A12 korxona chegarasi: 1-korxona 2-korxona loyihasini — 404, 2-korxona 1-korxonanikini — 404 (ma'lumotsiz); o'z loyihasi — 200; "
      "yo'q loyiha — 404",
      _x1[0] == 404 and "detallar" not in _x1[1] and _x2[0] == 404 and "detallar" not in _x2[1] and _x3[0] == 200
      and {d["order_id"] for d in _x3[1].get("detallar", [])} == {O["p3"]} and _x4[0] == 404, (_x1, _x2, _x3[0], _x4))
_yoq = royxat(ID["P1"], c=mijoz("k213_yoq"))
_kor = royxat(ID["P1"], c=mijoz("k213_kor"))
_bez = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False).get(
    f"/api/projects/{ID['P1']}/berilgan-detallar", follow_redirects=False)
check("A13 ruxsat: «Buyurtmalar: Ko'rish» yo'q rol — 403; faqat shu ruxsatli rol — 200 (o'sha ro'yxat); kirmagan — ma'lumot yo'q",
      _yoq[0] == 403 and "detallar" not in _yoq[1] and _kor[0] == 200 and len(_kor[1].get("detallar", [])) == len(D)
      and _bez.status_code in (401, 403, 302, 303, 307) and "detallar" not in _bez.text, (_yoq[0], _kor[0], _bez.status_code))
_sql = []
from sqlalchemy import event as _ev                # noqa: E402
from database import engine as _eng                # noqa: E402


def _say(*a, **k):
    _sql.append(1)


_ev.listen(_eng, "before_cursor_execute", _say)
royxat(ID["P1"])
_ev.remove(_eng, "before_cursor_execute", _say)
check("A14 so'rovlar soni detal soniga bog'liq emas (N+1 yo'q): 12 yozuvli ro'yxat ≤ 25 SQL", 0 < len(_sql) <= 25, len(_sql))
O["juft"] = buyurtma([PROFIL("K213 juft", 10), PROFIL("k213  JUFT", 7)])
_tj = topshir(O["juft"], {"K213 juft": None, "k213  JUFT": None}, vaqt=kun(8))
NUM["juft"] = db(lambda s2: s2.get(Order, O["juft"]).order_number) if O["juft"] else None
_jf = [d for d in royxat(ID["P1"])[1].get("detallar", []) if d.get("kalit") == "k213 juft"]
check("A15 bitta buyurtmada bir xil nomli 2 detal (10 + 7 m) — BITTA yozuv, jami 17 m (review213 №6)",
      _tj == 200 and len(_jf) == 1 and _jf[0]["berilgan"] == 17 and _jf[0]["buyurtma"] == NUM["juft"], (_tj, _jf))
_k1 = A.get(f"/api/projects/{ID['P1']}/berilgan-detallar?istisno=99999999999").status_code
_k2 = A.get("/api/projects/99999999999/berilgan-detallar").status_code
_k3 = A.get(f"/api/projects/{ID['P1']}/berilgan-detallar?istisno=0").status_code
check("A16 juda katta id (int4 dan katta) — 422 (PostgreSQL da 500 emas); istisno=0 — 422 (review213 №7)",
      _k1 == 422 and _k2 == 422 and _k3 == 422, (_k1, _k2, _k3))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U — HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PW_BOR = not PG_URL
try:
    from playwright.sync_api import sync_playwright
except Exception:                          # noqa: BLE001
    PW_BOR = False
if PG_URL:
    print("  (PG: brauzer bo'limi — SQLite / TF1 rejimida)")
else:
    check("U0 Python `playwright` bor", PW_BOR)

XATO = []
SOROV = []
if PW_BOR and all(O.values()):
    import uvicorn                                 # noqa: E402
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
    DRAFT_KEY = "penodecor_new_order_draft_v1"
    ILGAK = """() => { window.__msg = []; window.__ha = true;
      window.showMsg = (t, ty) => { window.__msg.push([String(t), ty]); };
      window.showConfirmModal = async () => window.__ha; window.customConfirm = async () => window.__ha; }"""
    ESLATMA = """(i) => { const r = document.querySelectorAll('#items .detal')[i || 0]; if (!r) return null;
      const e = r.querySelector('.i-takror'); const sm = r.querySelector('.detal-summary');
      return {ko: !!e && e.style.display === 'block' && e.offsetParent !== null, matn: e ? e.textContent : null,
              html: e ? e.innerHTML : null, img: e ? e.querySelectorAll('img').length : -1, belgi: r.dataset.takror || '',
              xulosa: sm ? sm.textContent : '', xulosa_ko: !!sm && getComputedStyle(sm).display !== 'none',
              yigilgan: r.classList.contains('collapsed'), nom: (r.querySelector('.i-name') || {}).value}; }"""

    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def sahifa(w=1440, h=900, tel=False, tungi=False, kirill=False, qoralama=None):
            ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ", is_mobile=tel, has_touch=tel)
            ctx.set_default_timeout(20000)
            ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda r: r.fulfill(status=204, body=""))
            _init = "try { localStorage.removeItem('%s');" % DRAFT_KEY
            if qoralama is not None:
                _init = "try { if (!sessionStorage.getItem('k213q')) { sessionStorage.setItem('k213q', '1'); localStorage.setItem('%s', %s); }" % (
                    DRAFT_KEY, json.dumps(json.dumps(qoralama)))
            if tungi:
                _init += " localStorage.setItem('theme', 'dark');"
            if kirill:
                _init += " localStorage.setItem('erp_script', 'kirill');"
            ctx.add_init_script(_init + " } catch (e) {}")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
            pg.on("request", lambda q: SOROV.append(q.url.replace(BU, "")) if "berilgan-detallar" in q.url else None)
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", "k213_a")
            xav(pg.fill, "input[name=password]", PAROL)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            return ctx, pg

        def buyurtmalar(pg, yol="/orders"):
            xav(pg.goto, BU + yol)
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.evaluate, ILGAK)

        def yangi_forma(pg, pid, toza=True):
            xav(pg.evaluate, "() => showNewForm()")
            if toza:                       # avvalgi ssenariy qatorlari (masalan tayyor mahsulotdan — nomi qulflangan) qolmasin
                xav(pg.evaluate, """() => { document.getElementById('items').innerHTML = '';
                    if (typeof itemCount !== 'undefined') itemCount = 0; addItem(); }""")
            xav(pg.evaluate, f"""() => {{ const p = document.getElementById('project_id'); p.value = '{pid}';
                p.dispatchEvent(new Event('change')); }}""")
            xav(pg.wait_for_timeout, 300)

        def yoz(pg, matn, i=0, harfma=False):
            loc = pg.locator("#items .detal .i-name").nth(i)
            if harfma:
                xav(loc.fill, "")
                xav(loc.press_sequentially, matn, delay=15)
            else:
                xav(loc.fill, matn)

        def kut(pg, i=0, korinsin=True, ms=6000):
            xav(pg.wait_for_function, """([i, k]) => { const r = document.querySelectorAll('#items .detal')[i]; if (!r) return false;
                const e = r.querySelector('.i-takror'); return !!e && ((e.style.display === 'block') === k); }""", arg=[i, korinsin],
                timeout=ms)
            xav(pg.wait_for_timeout, 250)
            return xav(pg.evaluate, ESLATMA, i, standart={}) or {}

        # ── U1–U9 — yangi buyurtma
        ctx, pg = sahifa()
        try:
            buyurtmalar(pg)
            yangi_forma(pg, ID["P1"])
            SOROV.clear()
            yoz(pg, "karniz m-06", harfma=True)
            e1 = kut(pg)
            _m = e1.get("matn") or ""
            check("U1 nom yozilganda qator ostida «ℹ️ Bu loyihada: …»: o2 — 30 m berilgan (Toshkent sanasi), "
                  "10 m hali berilmagan, o6 — 13 m (hali berilmagan; ortiqcha ayirilgan), o1 — 72 m berilgan (son, birlik, sana — bo'linmas bo'shliq bilan); ochiq birinchi; o'chirilgan / "
                  "bekor / qoralama / boshqa loyiha buyurtmasi YO'Q",
                  e1.get("ko") and _m.startswith("ℹ️ Bu loyihada: ")
                  and f"{NUM['o6']} —\u00a013\u00a0m\u00a0(hali\u00a0berilmagan)" in _m
                  and f"{NUM['o2']} —\u00a030\u00a0m\u00a0berilgan\u00a0({_e2[1]}), 10\u00a0m\u00a0hali\u00a0berilmagan" in _m
                  and f"{NUM['o1']} —\u00a072\u00a0m\u00a0berilgan\u00a0(" in _m
                  and _m.find(NUM["o2"] + " ") < _m.find(NUM["o6"] + " ") < _m.find(NUM["o1"] + " ")
                  and not any(NUM[k] + " " in _m for k in ("o3", "o4", "o5", "p2")), (e1, NUM))
            check("U2 11 harf yozildi — server so'rovi BITTA (loyiha bo'yicha bir marta)",
                  len(SOROV) == 1 and SOROV[0] == f"/api/projects/{ID['P1']}/berilgan-detallar", SOROV)
            yoz(pg, "Karniz M-07")
            e2 = kut(pg, korinsin=False)
            check("U3 mos kelmaydigan nom — eslatma yo'q (matn tozalangan)", not e2.get("ko") and e2.get("matn") == "" and not e2.get("belgi"), e2)
            yoz(pg, "Карниз М-06")           # «Карниз М-06»
            e3 = kut(pg)
            check("U4 Kirillda yozilgan nom («Карниз М-06») — o'sha eslatma", e3.get("ko") and NUM["o2"] in (e3.get("matn") or ""), e3)
            yoz(pg, "Karniz X")
            e4 = kut(pg)
            check("U5 bazadagi eski Kirill nom («Карниз Х») Lotinda yozilganda ham topiladi; «12,5 m», o'tgan yil sanasi bilan",
                  e4.get("ko") and f"{NUM['o7']} —\u00a012,5\u00a0m\u00a0berilgan\u00a0({_e7[1]})" in (e4.get("matn") or ""), e4)
            yoz(pg, XSS)
            e5 = kut(pg)
            xav(pg.wait_for_timeout, 400)
            _xss = xav(pg.evaluate, "() => typeof window.__xss", standart="?")
            check("U6 XSS nomli detal: eslatma bor, lekin HTML bajarilmaydi (rasm yo'q, `window.__xss` yo'q)",
                  e5.get("ko") and e5.get("img") == 0 and _xss == "undefined" and f"{NUM['o8']} —\u00a01\u00a0234,5\u00a0m\u00a0berilgan" in (e5.get("matn") or ""),
                  (e5, _xss))
            yoz(pg, PLI)
            e6 = kut(pg)
            _m6 = e6.get("matn") or ""
            check("U7 5 ta buyurtmada — eng yangi 3 tasi va «… yana 2 ta»",
                  e6.get("ko") and _m6.endswith(" · … yana 2 ta") and all(NUM[f"pl{i}"] in _m6 for i in (4, 3, 2))
                  and not any(NUM[f"pl{i}"] + " " in _m6 for i in (0, 1)), e6)
            yoz(pg, KAR)
            kut(pg)
            xav(pg.evaluate, f"""() => {{ const p = document.getElementById('project_id'); p.value = '{ID["P2"]}';
                p.dispatchEvent(new Event('change')); }}""")
            xav(pg.wait_for_function, f"() => (document.querySelector('#items .detal .i-takror').textContent || '').includes('{NUM['p2']}')",
                timeout=6000)
            e7 = xav(pg.evaluate, ESLATMA, 0, standart={}) or {}
            check("U8 loyiha almashtirildi — yozilgan detal eslatmasi YANGI loyiha bo'yicha (faqat uning buyurtmasi)",
                  e7.get("ko") and NUM["p2"] in (e7.get("matn") or "") and NUM["o1"] not in (e7.get("matn") or ""), e7)
            xav(pg.evaluate, """() => { const p = document.getElementById('project_id'); p.value = '';
                p.dispatchEvent(new Event('change')); }""")
            e8 = kut(pg, korinsin=False)
            check("U9 loyiha olib tashlandi — eslatma yo'q", not e8.get("ko") and e8.get("matn") == "", e8)
            yangi_forma(pg, ID["P1"])
            _fp = {"id": 999999, "quantity": 5, "unit": "metr", "unit_price": 1000, "name": KAR, "category": "profil", "width": 20,
                   "thickness": 10, "is_coated": False, "notes": ""}
            xav(pg.evaluate, """(fp) => { const r = document.querySelector('#items .detal'); const el = document.createElement('div');
                el.dataset.fp = JSON.stringify(fp); r.appendChild(el); try { pickFinished(el, fp.id); } finally { el.remove(); } }""", _fp)
            e8b = kut(pg)
            check("U9b tayyor mahsulotdan tanlanganda (nom dasturdan yoziladi, `input` hodisasisiz) — eslatma chiqadi",
                  e8b.get("ko") and e8b.get("nom") == KAR and NUM["o2"] in (e8b.get("matn") or ""), e8b)
            yangi_forma(pg, ID["P1"])
            _pt = {"id": 999998, "name": KAR, "unit": "dona", "input_template": "", "supports_coating": False, "coating_price_multiplier": ""}
            xav(pg.evaluate, "(pt) => { selectMrpProduct(document.querySelector('#items .detal'), pt); }", _pt)
            e8c = kut(pg)
            check("U9c MRP mahsuloti tanlanganda (nom dasturdan yoziladi) — eslatma chiqadi (review213 №2)",
                  e8c.get("ko") and e8c.get("nom") == KAR and NUM["o2"] in (e8c.get("matn") or ""), e8c)
            # U10 — kechikkan javob: P1 so'rovi sekin, shu orada P2 tanlanadi → P1 javobi yozilmaydi
            xav(pg.evaluate, f"""() => {{ const asl = window.fetch; window.__aslFetch = asl;
                window.fetch = function(u, o) {{ const p = asl.apply(this, arguments);
                  return String(u).includes('/api/projects/{ID["P1"]}/berilgan-detallar') ? p.then(r => new Promise(res => setTimeout(() => res(r), 1500))) : p; }};
                hideNewForm(); showNewForm(); const p = document.getElementById('project_id'); p.value = '{ID["P1"]}';
                p.dispatchEvent(new Event('change')); const n = document.querySelector('#items .detal .i-name'); n.value = '{KAR}';
                n.dispatchEvent(new Event('input')); p.value = '{ID["P2"]}'; p.dispatchEvent(new Event('change')); }}""")
            xav(pg.wait_for_timeout, 2600)
            e9 = xav(pg.evaluate, ESLATMA, 0, standart={}) or {}
            xav(pg.evaluate, "() => { if (window.__aslFetch) window.fetch = window.__aslFetch; }")
            check("U10 kechikkan javob (oldingi loyiha) keyin kelsa ham yozilmaydi — eslatma joriy loyihaniki",
                  e9.get("ko") and NUM["p2"] in (e9.get("matn") or "") and NUM["o1"] not in (e9.get("matn") or ""), e9)
            # U11 — yig'ilgan qator belgisi
            yangi_forma(pg, ID["P1"])
            yoz(pg, KAR)
            kut(pg)
            xav(pg.evaluate, "() => addItem()")
            xav(pg.wait_for_timeout, 400)
            e10 = xav(pg.evaluate, ESLATMA, 1, standart={}) or {}
            e10b = xav(pg.evaluate, ESLATMA, 0, standart={}) or {}
            check("U11 «+ Detal» bosildi — oldingi qator yig'ildi, xulosasida «ℹ️ loyihada bor» belgisi (birinchi); yangi qatorda eslatma yo'q",
                  e10.get("yigilgan") and e10.get("xulosa_ko") and (e10.get("xulosa") or "").startswith("ℹ️ loyihada bor")
                  and e10.get("nom") == KAR and not e10b.get("ko") and not e10b.get("belgi"), (e10, e10b))
            # U12 — saqlash bloklanmaydi
            TUT = []

            def _ush(r):
                if r.request.method == "POST":
                    TUT.append(r.request.post_data)
                    return r.fulfill(status=400, content_type="application/json", body='{"detail":"Sinov: saqlanmaydi"}')
                return r.continue_()
            pg.route(re.compile(r".*/api/orders(\?.*)?$"), _ush)
            yangi_forma(pg, ID["P1"])
            xav(pg.evaluate, f"""() => {{ const d = document.getElementById('deadline_input'); if (d) d.value = '{(BUGUN_T + datetime.timedelta(days=5)).isoformat()}';
                const r = document.querySelector('#items .detal'); const t = r.querySelector('.type-opt[data-value="dona"]'); if (t) t.click();
                const n = r.querySelector('.i-name'); n.value = '{KAR}'; n.dispatchEvent(new Event('input')); r.querySelector('.i-q').value = '2';
                const up = r.querySelector('.i-unitprice'); if (up) {{ up.value = '1 000'; up.dispatchEvent(new Event('input')); }} }}""")
            e11 = kut(pg)
            xav(pg.evaluate, "() => saveOrder(false)")
            xav(pg.wait_for_timeout, 1500)
            _tb = {}
            try:
                _tb = json.loads(TUT[0]) if TUT and TUT[0] else {}
            except Exception:                  # noqa: BLE001
                _tb = {}
            check("U12 eslatma ko'rinib turganda «💾 Saqlash» — so'rov YUBORILADI (bloklamaydi), detal nomi o'sha",
                  e11.get("ko") and _tb and any(it.get("name") == KAR for it in _tb.get("items", [])), (e11, TUT[:1]))
            pg.unroute(re.compile(r".*/api/orders(\?.*)?$"), _ush)
            # U13 — forma qayta ochilganda yangi yuk ko'rinadi
            yangi_forma(pg, ID["P1"])
            yoz(pg, "K213 yangi detal")
            e12 = kut(pg, korinsin=False, ms=2500)
            _oy = buyurtma([PROFIL("K213 yangi detal", 9)])
            _ty = topshir(_oy, {"K213 yangi detal": None})
            NUM["oy"] = db(lambda s2: s2.get(Order, _oy).order_number) if _oy else None
            xav(pg.evaluate, "() => { hideNewForm(); showNewForm(); }")       # qator saqlanadi — nom QAYTA yozilmaydi
            e13 = kut(pg)
            check("U13 forma qayta ochilganda — saqlangan qatorda (nomi qayta yozilmasdan) oraliqda yozilgan yuk xati ko'rinadi "
                  "(eski ma'lumot ishlatilmaydi; review213 №3)",
                  not e12.get("ko") and _ty == 200 and e13.get("ko") and e13.get("nom") == "K213 yangi detal"
                  and f"{NUM.get('oy') or '?'} —\u00a09\u00a0m\u00a0berilgan" in (e13.get("matn") or ""), (e12, e13))
            _dl = db(lambda s2: [d.id for d in s2.query(Delivery).filter(Delivery.order_id == _oy).all()]) if _oy else []
            _dd = [A.delete(f"/api/deliveries/{_i}").status_code for _i in _dl]
            xav(pg.evaluate, "() => { hideNewForm(); showNewForm(); }")
            xav(pg.wait_for_function, "() => (document.querySelector('#items .detal .i-takror').textContent || '').includes('hali')",
                timeout=6000)
            e13b = xav(pg.evaluate, ESLATMA, 0, standart={}) or {}
            check("U13b yuk xati o'chirildi — forma qayta ochilganda eskirgan «berilgan» o'rniga «hali berilmagan» (ochiq buyurtma; nom qayta "
                  "yozilmasdan)",
                  _dl and all(x == 200 for x in _dd) and e13b.get("ko") and e13b.get("nom") == "K213 yangi detal"
                  and f"{NUM.get('oy') or '?'} —\u00a09\u00a0m\u00a0(hali\u00a0berilmagan)" in (e13b.get("matn") or "")
                  and "berilgan" + "\u00a0" not in (e13b.get("matn") or ""), (_dd, e13b))
            # U20 — server xatosi keshda qolmaydi
            yangi_forma(pg, ID["P1"])
            xav(pg.wait_for_timeout, 600)
            _ur = {"n": 0}

            def _xato(r):
                _ur["n"] += 1
                if _ur["n"] == 1:
                    return r.fulfill(status=500, content_type="application/json", body='{"detail":"sinov"}')
                return r.continue_()
            pg.route(re.compile(r".*/berilgan-detallar.*"), _xato)
            xav(pg.evaluate, "() => takrorTozala()")
            yoz(pg, KAR)
            e14 = kut(pg, korinsin=False, ms=2500)
            yoz(pg, KAR + " ")
            e15 = kut(pg)
            pg.unroute(re.compile(r".*/berilgan-detallar.*"), _xato)
            check("U20 server xatosi (500) keshda qolmaydi — keyingi harfda qayta so'raladi, eslatma chiqadi (review213 №4)",
                  not e14.get("ko") and e15.get("ko") and NUM["o2"] in (e15.get("matn") or "") and _ur["n"] == 2, (_ur, e14, e15))
        except Exception as _e:                # noqa: BLE001
            check("U1! ssenariy", False, f"{type(_e).__name__}: {_e}")
        finally:
            ctx.close()

        # ── U14 — tahrir: o'zi sanalmaydi
        ctx, pg = sahifa()
        try:
            SOROV.clear()
            buyurtmalar(pg, f"/orders?order={O['o2']}")
            xav(pg.wait_for_timeout, 600)
            xav(pg.evaluate, ILGAK)
            xav(pg.evaluate, "() => editSelected()")
            xav(pg.wait_for_function, "() => typeof editInitialLoadDone !== 'undefined' && editInitialLoadDone === true && editMode === true",
                timeout=15000)
            xav(pg.wait_for_timeout, 1200)
            _qq = xav(pg.evaluate, "() => [...document.querySelectorAll('#items .detal')].map((r, i) => i)", standart=[]) or []
            _ee = [xav(pg.evaluate, ESLATMA, i, standart={}) or {} for i in _qq]
            _k = [e for e in _ee if (e.get("nom") or "").strip().lower().startswith("karniz")]
            _u = [e for e in _ee if (e.get("nom") or "") == "K213 ustun"]
            _km = (_k[0].get("matn") if _k else "") or ""
            _kb = (_k[0].get("belgi") if _k else "") == "1"
            check("U14 tahrirda (o2): karniz qatorida faqat BOSHQA buyurtma (o1) — o'zi (o2) sanalmaydi; faqat o'zida bor «K213 ustun» — "
                  "eslatma / belgi yo'q; so'rov `istisno` bilan",
                  _k and _kb and (NUM["o1"] in _km or "ℹ️ loyihada bor" in (_k[0].get("xulosa") or "")) and NUM["o2"] not in _km
                  and _u and not _u[0].get("belgi") and not _u[0].get("ko")
                  and any(x == f"/api/projects/{ID['P1']}/berilgan-detallar?istisno={O['o2']}" for x in SOROV), (_ee, SOROV))
            if _k and _k[0].get("yigilgan"):
                check("U14b (yig'ilgan karniz qatori xulosasida belgi)", "ℹ️ loyihada bor" in (_k[0].get("xulosa") or ""), _k)
            elif _k:
                check("U14b (ochiq karniz qatorida o1 eslatmasi)", NUM["o1"] in _km and _k[0].get("ko"), _k)
        except Exception as _e:                # noqa: BLE001
            check("U14! ssenariy", False, f"{type(_e).__name__}: {_e}")
        finally:
            ctx.close()

        # ── U15 — qoralama tiklanganda
        _qd = {"ts": int(time.time() * 1000), "project_id": str(ID["P1"]), "master_id": "", "deadline_input": "", "recipe_id": "",
               "base_price": "", "blok_base_price": "", "loy_kg": "",
               "rows": [{"i-type": "profil", "i-name": "K213 boshqa narsa"}, {"i-type": "profil", "i-name": KAR}]}
        ctx, pg = sahifa(qoralama=_qd)
        try:
            buyurtmalar(pg)
            xav(pg.wait_for_function, "() => document.querySelectorAll('#items .detal').length >= 2", timeout=10000)
            xav(pg.wait_for_function, "() => [...document.querySelectorAll('#items .detal')].some(r => r.dataset.takror === '1')", timeout=8000)
            _ee = [xav(pg.evaluate, ESLATMA, i, standart={}) or {} for i in range(2)]
            _k = [e for e in _ee if e.get("nom") == KAR]
            _b = [e for e in _ee if e.get("nom") == "K213 boshqa narsa"]
            check("U15 qoralama tiklanganda — karniz qatorida eslatma / belgi, boshqasida yo'q",
                  _k and _k[0].get("belgi") == "1" and NUM["o2"] in (_k[0].get("matn") or "") and _b and not _b[0].get("belgi"), _ee)
        except Exception as _e:                # noqa: BLE001
            check("U15! ssenariy", False, f"{type(_e).__name__}: {_e}")
        finally:
            ctx.close()

        # ── U16 — Kirill rejimi
        ctx, pg = sahifa(kirill=True)
        try:
            buyurtmalar(pg)
            yangi_forma(pg, ID["P1"])
            yoz(pg, KAR)
            e = kut(pg)
            xav(pg.wait_for_timeout, 300)
            e = xav(pg.evaluate, ESLATMA, 0, standart={}) or {}
            check("U16 Kirill yozuvi rejimida — yozuv Kirillda («Бу лойиҳада …»), buyurtma raqami o'zgarmagan",
                  e.get("ko") and "Бу лойиҳада" in (e.get("matn") or "")
                  and NUM["o2"] in (e.get("matn") or ""), e)
        except Exception as _e:                # noqa: BLE001
            check("U16! ssenariy", False, f"{type(_e).__name__}: {_e}")
        finally:
            ctx.close()

        # ── U17 — kontrast (kunduzgi / tungi), U18 — telefon
        RANG = """() => { const e = document.querySelector('#items .detal .i-takror'); let p = e.parentElement, f = 'rgba(0, 0, 0, 0)';
          while (p) { const b = getComputedStyle(p).backgroundColor; if (b && b !== 'rgba(0, 0, 0, 0)' && b !== 'transparent') { f = b; break; }
            p = p.parentElement; }
          const r = e.getBoundingClientRect();
          return {rang: getComputedStyle(e).color, fon: f, ong: Math.round(r.right), en: document.documentElement.clientWidth,
                  tosh: document.documentElement.scrollWidth - document.documentElement.clientWidth, bal: Math.round(r.height)}; }"""
        _kt = {}
        for _nom, _kw in (("kunduzgi", {}), ("tungi", {"tungi": True}), ("telefon", {"w": 390, "h": 844, "tel": True})):
            ctx, pg = sahifa(**_kw)
            try:
                buyurtmalar(pg)
                yangi_forma(pg, ID["P1"])
                yoz(pg, PLI)
                e = kut(pg)
                _kt[_nom] = dict(xav(pg.evaluate, RANG, standart={}) or {}, ko=e.get("ko"))
            except Exception as _e:            # noqa: BLE001
                _kt[_nom] = {"xato": str(_e)[:200]}
            finally:
                ctx.close()
        _kc = {k: round(kontrast(rgb(v.get("rang")), rgb(v.get("fon"))), 2) for k, v in _kt.items()}
        check("U17 eslatma o'qiladi: kunduzgi va tungi rejimda kontrast ≥ 4,5",
              _kt.get("kunduzgi", {}).get("ko") and _kt.get("tungi", {}).get("ko") and _kc.get("kunduzgi", 0) >= 4.5
              and _kc.get("tungi", 0) >= 4.5, (_kc, _kt))
        _tl = _kt.get("telefon", {})
        check("U18 telefon (390 px): eslatma ko'rinadi, ekrandan chiqmaydi, sahifa yon tomonga surilmaydi (uzun yozuv qatorlarga bo'linadi)",
              _tl.get("ko") and _tl.get("tosh", 99) <= 0 and _tl.get("ong", 9999) <= _tl.get("en", 0) and _tl.get("bal", 0) > 20, _tl)

        BELGI = """() => { const r = document.querySelectorAll('#items .detal')[1]; if (!r) return null;
          const s = r.querySelector('.detal-summary').getBoundingClientRect(); const b = r.querySelector('.detal-summary .takror-belgi');
          const br = b ? b.getBoundingClientRect() : null;
          return {s: [Math.round(s.left), Math.round(s.right)], b: br ? [Math.round(br.left), Math.round(br.right), Math.round(br.width)] : null,
                  yig: r.classList.contains('collapsed')}; }"""
        _bel = {}
        for _w in (360, 390):
            ctx, pg = sahifa(w=_w, h=800, tel=True)
            try:
                buyurtmalar(pg)
                yangi_forma(pg, ID["P1"])
                yoz(pg, KAR + " uzunroq nomli detal")
                yoz(pg, KAR)
                kut(pg)
                xav(pg.evaluate, "() => addItem()")
                xav(pg.wait_for_timeout, 400)
                _bel[_w] = xav(pg.evaluate, BELGI, standart=None)
            except Exception as _e:            # noqa: BLE001
                _bel[_w] = {"xato": str(_e)[:200]}
            finally:
                ctx.close()

        def _ichida(v):
            return bool(v) and v.get("yig") and v.get("b") and v["b"][2] >= 10 and v["b"][0] >= v["s"][0] - 1 and v["b"][1] <= v["s"][1] + 1
        check("U18b telefon (360 / 390 px): yig'ilgan qator belgisi xulosa maydoni ICHIDA to'liq ko'rinadi (review213 №1)",
              _ichida(_bel.get(360)) and _ichida(_bel.get(390)), _bel)

    check("U19 JS xatosi yo'q (barcha sahifalar)", not XATO, XATO[:5])

if PG_URL:                                          # o'z bazasini o'chiradi (review213 №8)
    try:
        from database import engine as _eng2
        _eng2.dispose()
        _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
        with _adm.connect() as _c:
            _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm.dispose()
    except Exception as _e:                         # noqa: BLE001
        print(f"  (PG bazasi o'chirilmadi: {type(_e).__name__}: {_e})")
print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
