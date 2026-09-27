#!/usr/bin/env python3
"""
test_qarz_ochirilgan.py — kech100 darvozasi (2026-09-27, 134-band, FOYDALANUVCHI QARORI "A"; K100-4).

QAROR "A": o'chirilgan, lekin hisobotda qolgan buyurtmaning to'lanmagan qarzi "Qarzdorlar" da ko'rinsin ("o'chirilgan"
belgisi bilan) — pul undirilishi kerak.

O'LCHANGAN (`work/probe134.py`, asl kod): Qarzdorlar (ro'yxat, jami), debt-summary (Moliya, PDF), `get_debt_stats`
(bosh sahifa ro'yxati), 30 kunlik ogohlantirish — o'chirilgan buyurtmalarni umuman olmasdi; bosh sahifa "Jami qarz"
esa o'chirilgan READY / DELIVERED byudjetini olib, HAMMA to'lovlarni ayirardi (asl 900 000 ↔ haqiqiy 1 000 000):
hisobga kirmagan buyurtmalar to'lovlari va ortiqcha to'lovlar boshqa mijozlar qarzini "yopardi" (K100-4).

YECHIM: YAGONA shart `crud.qarz_hisobidagi_buyurtma_sharti()` — o'chirilmagan YOKI o'chirilgan READY / DELIVERED;
eski o'chirilgan IN_PROGRESS (summa topshirilganga tushirilmagan) kirmaydi. Hamma qarz ko'rsatkichlari shu bilan;
"Jami qarz" = qarzlar yig'indisi.

Bo'limlar: A — a'zolik; B — hamma ko'rsatkich bir xil (jami / soni); C — UI belgilari; D — o'chirilgan qarzdor to'lovi;
E — tiklash; F — miqyos (so'rovlar soni); X — 5xx; S — statik.

Ishlatish:
    python3 tools/test_qarz_ochirilgan.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_qarz_ochirilgan.py
"""
import os
import re
import sys
import inspect
import tempfile
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qarz_ochirilgan_test"
_T = tempfile.mkdtemp(prefix="qarz_ochirilgan_")
_DB = os.path.join(_T, "qarz_ochirilgan_test.db")

if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
               isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402
    import crud                                    # noqa: E402

from database import SessionLocal, engine          # noqa: E402
from models import UserRole, Project, Inventory, OrderItem, Order   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from sqlalchemy import event                       # noqa: E402

crud.PUL_TAKROR_SONIYA = 0

YORLIQ = "[PG] " if PG_URL else ""
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
        print(f"  ✗ {label}   {str(detail)[:600]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"

    def json(self):
        return {}


XATOLAR_5XX = []


def req(c, metod, url, **k):
    try:
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    if r.status_code >= 500:
        XATOLAR_5XX.append((metod, url, r.status_code, str(getattr(r, "text", ""))[:200]))
    return r


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def taxminan(a, b, eps=0.01):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


def tartibda(src, *qismlar):
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "QO_admin", "Parol123!", UserRole.ADMIN, "QO Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="QO Penoplast", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
_db.add(PENO)
_db.flush()
PRJ = {}
for k in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
    p = Project(company_id=1, client_name=f"QO {k} Mijoz", project_name=f"QO {k}", total_budget=0, total_paid=0)
    _db.add(p)
    _db.flush()
    PRJ[k] = p.id
_db.commit()
PENO_ID = PENO.id
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
if req(C, "post", "/login", data={"username": "QO_admin", "password": "Parol123!"}, follow_redirects=False).status_code != 302:
    print("LOGIN BO'LMADI")
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)
_n = [0]


def yarat(k, draft=False):
    _n[0] += 1
    r = req(C, "post", "/api/orders", params={"confirm_shortage": "true"}, json={
        "project_id": PRJ[k], "order_type": "product", "loy_kg": 0, "is_draft": draft,
        "items": [{"name": f"QO_{k}_{_n[0]}", "category": "profil", "width": 20, "thickness": 10, "length": 10,
                   "quantity": 10, "unit_price": 50_000, "is_coated": False, "penoplast_id": PENO_ID}]})
    oid = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
    s = SessionLocal()
    try:
        iid = s.query(OrderItem.id).filter(OrderItem.order_id == oid).first()
    finally:
        s.close()
    return oid, (iid[0] if iid else None)


def yuk(oid, iid, m):
    return req(C, "post", "/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": iid, "quantity": m}],
                                                  "notes": f"y{_n[0]}_{oid}", "transport_cost": 0, "transport_payer": "none",
                                                  "payment_method": "naqd"}).status_code


def tolov(oid, summa):
    return req(C, "post", "/api/payments", json={"order_id": oid, "amount": summa, "notes": f"t{oid}_{summa}",
                                                "confirm_overpay": True}).status_code


ID = {}
o, i = yarat("H1"); tolov(o, 100_000); ID["H1"] = o                                           # 400 000 qarz
o, i = yarat("H2"); tolov(o, 50_000); yuk(o, i, 4); req(C, "delete", f"/api/orders/{o}"); ID["H2"] = o   # yakunlangan 150 000
o, i = yarat("H3"); tolov(o, 50_000); yuk(o, i, 4); req(C, "post", f"/api/orders/{o}/ready"); req(C, "delete", f"/api/orders/{o}"); ID["H3"] = o
o, i = yarat("H4"); tolov(o, 50_000); yuk(o, i, 10); req(C, "delete", f"/api/orders/{o}"); ID["H4"] = o  # 450 000
o, i = yarat("H5"); tolov(o, 50_000); yuk(o, i, 4)
_s = SessionLocal()
_s.execute(Order.__table__.update().where(Order.__table__.c.id == o).values(is_deleted=True, stock_returned=True))
_s.commit()
_s.close()
ID["H5"] = o                                                                                 # eski o'chirilgan IN_PROGRESS
o, i = yarat("H6"); tolov(o, 600_000); ID["H6"] = o                                           # ortiqcha 100 000
o, i = yarat("H7", draft=True); tolov(o, 70_000); ID["H7"] = o                                # qoralama zaklati
_s = SessionLocal()
_s.execute(Order.__table__.update().values(created_at=datetime.utcnow() - timedelta(days=40)))
_s.commit()
_s.close()


def qarz(oid):
    s = SessionLocal()
    try:
        return round(float(s.get(Order, oid).debt_amount or 0), 2)
    finally:
        s.close()


def debts_html():
    return str(getattr(req(C, "get", "/debts"), "text", ""))


def mijozlar_bolimi(h):
    b = h.find('<div id="tab-customers">')
    e = h.find('<div id="tab-refunds"', b) if '<div id="tab-refunds"' in h else h.find('<!-- YETKAZIB', b)
    return h[b:e] if b >= 0 and e > b else ""


def jami_html(h):
    m = re.search(r"Bizga qarzdorlar \(mijozlar\)</div>\s*<div class=\"dbt-summary-value\">([^<]+) so'm</div>", h)
    return float(m.group(1).replace(" ", "").replace(" ", "")) if m else None


def korsatkichlar():
    s = SessionLocal()
    n = datetime.utcnow()
    try:
        with contextlib.redirect_stdout(_quiet):
            st = crud.get_debt_stats(s, company_id=1)
            fd = services.get_full_debt_summary(s, n.year, n.month, company_id=1)
            ch = services.get_chart_data(s, company_id=1)
            al = services.get_business_alerts(s, company_id=1)
        return st, fd, ch, al
    finally:
        s.close()


KUTILGAN = {"H1": 400_000, "H2": 150_000, "H3": 150_000, "H4": 450_000}

# ══════════════════════════════════════════════════════════════
section("A. A'zolik — o'chirilgan, lekin hisobotda qolgan qarz ko'rinadi; eski IN_PROGRESS / ortiqcha / qoralama — yo'q")
h = debts_html()
mb = mijozlar_bolimi(h)
for k in ("H1", "H2", "H3", "H4"):
    check(f"A {k}: Qarzdorlar ro'yxatida, qarz {KUTILGAN[k]:,}", f"QO {k} Mijoz" in mb and taxminan(qarz(ID[k]), KUTILGAN[k]),
          (qarz(ID[k]),))
for k in ("H5", "H6", "H7"):
    check(f"A {k}: Qarzdorlar ro'yxatida YO'Q", f"QO {k} Mijoz" not in mb, k)

section("B. Hamma ko'rsatkich — bir xil to'plam va jami (1 150 000, 4 ta)")
st, fd, ch, al = korsatkichlar()
check("B1 Qarzdorlar jami = 1 150 000", taxminan(jami_html(h), 1_150_000, 0.5), jami_html(h))
check("B2 debt-summary (Moliya / PDF): 1 150 000, 4 ta", taxminan(fd.get("customer_debt"), 1_150_000, 0.5)
      and fd.get("customer_debt_count") == 4, {k: fd.get(k) for k in ("customer_debt", "customer_debt_count")})
check("B3 get_debt_stats (bosh sahifa ro'yxati): 1 150 000, 4 ta, o'chirilganlar belgisi",
      taxminan(st.get("total_debt"), 1_150_000) and st.get("debt_orders_count") == 4
      and sorted(d["order_id"] for d in st["debt_orders"] if d.get("is_deleted")) == sorted([ID["H2"], ID["H3"], ID["H4"]]),
      st)
check("B4 bosh sahifa \"Jami qarz\" (K100-4) = Qarzdorlar jami (ortiqcha to'lov / hisobdan tashqari to'lov qarzni YOPMAYDI)",
      taxminan(ch["finance"]["total_debt"], 1_150_000), ch["finance"])
_al = " ".join(a.get("text", "") for a in al)
check("B5 30 kunlik ogohlantirish: 4 ta qarzdor", "4 ta qarzdorning muddati 30 kundan oshgan" in _al, al)
_r = js(req(C, "get", f"/api/finance/debt-summary?year={datetime.utcnow().year}&month={datetime.utcnow().month}")) or {}
check("B6 /api/finance/debt-summary (HTTP) — o'sha jami", taxminan(_r.get("customer_debt"), 1_150_000, 0.5), _r)

section("C. UI belgilari")
def element(bolim, k):
    """Qarzdorlar ro'yxatidagi shu mijoz elementi (keyingi element boshigacha)."""
    b = bolim.find(f'data-client="QO {k} Mijoz"')
    if b < 0:
        return ""
    e = bolim.find('onclick="selectOrderDebt(this)"', b)
    return bolim[b:e if e > b else len(bolim)]


_q2 = element(mb, "H2")
check("C1 Qarzdorlar: o'chirilganlarda \"o'chirilgan\" belgisi (3 ta), o'chirilmaganda yo'q",
      mb.count('class="qarz-ochirilgan"') == 3 and "qarz-ochirilgan" in _q2 and "qarz-ochirilgan" not in element(mb, "H1"),
      (mb.count('class="qarz-ochirilgan"'), _q2[:300]))
check("C2 Qarzdorlar: data-deleted — o'chirilganlar true", mb.count('data-deleted="true"') == 3, mb.count('data-deleted="true"'))
_d = open(os.path.join(ROOT, "templates", "debts.html"), encoding="utf-8").read()
check("C3 debts.html tafsilot: o'chirilgan — /trash havolasi, aks holda /orders",
      tartibda(_d, "function selectOrderDebt(el)", "d.deleted === 'true'", 'href="/trash"', 'href="/orders"'), "")
_db_html = open(os.path.join(ROOT, "templates", "dashboard.html"), encoding="utf-8").read()
check("C4 dashboard.html qarzlar ro'yxati: d.is_deleted belgisi", tartibda(_db_html, "function buildDebtList", "d.is_deleted?"), "")

section("D. O'chirilgan qarzdor to'lovi — qarz kamayadi, to'liq to'langach ro'yxatdan chiqadi")
_rt = tolov(ID["H3"], 150_000)
h2 = debts_html()
check("D1 H3 150 000 to'landi — qarz 0, ro'yxatda yo'q, jami 1 000 000",
      _rt == 200 and qarz(ID["H3"]) == 0 and "QO H3 Mijoz" not in mijozlar_bolimi(h2) and taxminan(jami_html(h2), 1_000_000, 0.5),
      (_rt, qarz(ID["H3"]), jami_html(h2)))

section("E. Tiklash — yakunlash bekor, qarz asl summadan (belgisiz)")
_rr = req(C, "post", f"/api/orders/{ID['H2']}/restore").status_code
h3 = debts_html()
mb3 = mijozlar_bolimi(h3)
_seg = element(mb3, "H2")
check("E1 H2 tiklandi — qarz 450 000, ro'yxatda, \"o'chirilgan\" belgisisiz",
      _rr == 200 and qarz(ID["H2"]) == 450_000 and "QO H2 Mijoz" in mb3 and "qarz-ochirilgan" not in _seg,
      (_rr, qarz(ID["H2"])))

section("F. Miqyos — so'rovlar soni o'chirilgan qarzdorlar soniga bog'liq EMAS")
_SANOQ = [0]


def _hisob(conn, cursor, statement, parameters, context, executemany):
    _SANOQ[0] += 1


def sorovlar(fn):
    _SANOQ[0] = 0
    event.listen(engine, "before_cursor_execute", _hisob)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", _hisob)
    return _SANOQ[0]


def _olch():
    return (sorovlar(debts_html), sorovlar(lambda: req(C, "get", "/api/dashboard/charts")),
            sorovlar(lambda: req(C, "get", "/api/finance/debt-summary", params={"year": 2026, "month": 9})))


def _qosh(n):
    for _ in range(n):
        o, i = yarat("H4")
        tolov(o, 10_000)
        yuk(o, i, 10)
        req(C, "delete", f"/api/orders/{o}")


# Grafik oylari bo'yicha taqsimot (bo'sh oy — IN so'rovi yo'q) o'zgarmasligi uchun: avval +1, keyin +5 va yana +5
_qosh(1)
q1 = _olch()
_qosh(5)
q2 = _olch()
_qosh(5)
q3 = _olch()
check("F1 /debts, /api/dashboard/charts, debt-summary: +5 va yana +5 o'chirilgan qarzdor — so'rovlar O'ZGARMADI",
      q1 == q2 == q3, (q1, q2, q3))

section("H. Biznes salomatligi — qarz ulushida o'chirilgan, hisobotda qolgan qarz ham (alohida korxona)")
# kech100 (kmut100 P09 — faqat statik ushlangan edi): salomatlik faqat RANG beradi (qarz ulushi < 15 % / < 30 %); asosiy
# ma'lumotda ikki qoida bir xil rang berardi. Alohida korxona: X — 500 000 to'liq to'langan (qarz 0), Y — 4 / 10 topshirilib
# o'chirilgan (yakunlangan 200 000, to'lanmagan). Yangi qoida: 200 000 / 700 000 = 28.6 % → "orange"; eski (faqat
# o'chirilmagan): 0 % → "green".
from production_models import Company as _Co134        # noqa: E402
_s = SessionLocal()
try:
    if not _s.get(_Co134, 2):
        _s.add(_Co134(id=2, name="QO Korxona B"))
        _s.commit()
    with contextlib.redirect_stdout(_quiet):
        auth.create_user(_s, "QO_b", "Parol123!", UserRole.ADMIN, "QO B", company_id=2)
    _pb = Inventory(company_id=2, item_name="QO Penoplast B", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                    volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
    _prb = Project(company_id=2, client_name="QO B Mijoz", project_name="QO B", total_budget=0, total_paid=0)
    _s.add_all([_pb, _prb])
    _s.commit()
    PENO_B, PRJ_B = _pb.id, _prb.id
finally:
    _s.close()
CB = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_hb_login = req(CB, "post", "/login", data={"username": "QO_b", "password": "Parol123!"}, follow_redirects=False).status_code


def yarat_b():
    _n[0] += 1
    r = req(CB, "post", "/api/orders", params={"confirm_shortage": "true"}, json={
        "project_id": PRJ_B, "order_type": "product", "loy_kg": 0,
        "items": [{"name": f"QO_B_{_n[0]}", "category": "profil", "width": 20, "thickness": 10, "length": 10,
                   "quantity": 10, "unit_price": 50_000, "is_coated": False, "penoplast_id": PENO_B}]})
    oid = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
    s = SessionLocal()
    try:
        iid = s.query(OrderItem.id).filter(OrderItem.order_id == oid).first()
    finally:
        s.close()
    return oid, (iid[0] if iid else None)


_hx, _hxi = yarat_b()
_hx_t = req(CB, "post", "/api/payments", json={"order_id": _hx, "amount": 500_000, "notes": "hb_x"}).status_code
_hy, _hyi = yarat_b()
_hy_y = req(CB, "post", "/api/deliveries", json={"order_id": _hy, "items": [{"order_item_id": _hyi, "quantity": 4}],
                                                 "notes": "hb_y", "transport_cost": 0, "transport_payer": "none",
                                                 "payment_method": "naqd"}).status_code
_hy_d = req(CB, "delete", f"/api/orders/{_hy}").status_code
_s = SessionLocal()
try:
    _bh = services.get_business_health(_s, company_id=2)
    _hy_o = _s.get(Order, _hy)
    _hy_hol = (_hy_o.status.value, bool(_hy_o.is_deleted), round(float(_hy_o.debt_amount), 2)) if _hy_o else None
finally:
    _s.close()
check("H1 tayyorgarlik: B korxonasi, X to'langan, Y 4 / 10 topshirilib o'chirilgan (READY, qarz 200 000)",
      _hb_login == 302 and _hx_t == 200 and _hy_y == 200 and _hy_d == 200 and _hy_hol == ("ready", True, 200_000.0),
      (_hb_login, _hx_t, _hy_y, _hy_d, _hy_hol))
check("H2 qarz ulushi 200 000 / 700 000 = 28.6 % → \"orange\" (o'chirilgan, hisobotda qolgan qarz ham; faqat o'chirilmaganlar — "
      "0 % \"green\")", _bh.get("qarzdorlik") == "orange", _bh)

section("X. Server xatosi (5xx) yo'q")
check("X1 test davomida 5xx yo'q", not XATOLAR_5XX, XATOLAR_5XX[:5])

section("S. Statik — yagona shart")
_sh = manba(crud, "qarz_hisobidagi_buyurtma_sharti")
check("S1 shart: o'chirilmagan YOKI READY / DELIVERED",
      "Order.is_deleted.isnot(True)" in _sh and "Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED])" in _sh, "")
_joylar = {"main.debts_page": manba(main, "debts_page"), "services.get_full_debt_summary": manba(services, "get_full_debt_summary"),
           "crud.get_debt_stats": manba(crud, "get_debt_stats"), "services.get_business_alerts": manba(services, "get_business_alerts"),
           "services.get_business_health": manba(services, "get_business_health"), "services.get_chart_data": manba(services, "get_chart_data")}
check("S2 hamma qarz ko'rsatkichlari yagona shartni ishlatadi",
      all("qarz_hisobidagi_buyurtma_sharti()" in v for v in _joylar.values()),
      [k for k, v in _joylar.items() if "qarz_hisobidagi_buyurtma_sharti()" not in v])
check("S3 get_chart_data: \"Jami qarz\" — qarzlar yig'indisi (byudjet − to'lovlar EMAS)",
      "total_debt = float(total_budget) - float(total_paid)" not in _joylar["services.get_chart_data"]
      and "o.debt_amount for o in _qz_buyurtmalar" in _joylar["services.get_chart_data"], "")

print("\n" + "=" * 66)
print(f"REJIM: {'PostgreSQL' if PG_URL else 'SQLite'}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
print("=" * 66)
if PG_URL:
    try:
        engine.dispose()
        _adm2 = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
        with _adm2.connect() as _c:
            _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm2.dispose()
    except Exception:                      # noqa: BLE001
        pass
sys.exit(1 if FAIL else 0)
