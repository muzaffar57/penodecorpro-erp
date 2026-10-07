#!/usr/bin/env python3
"""
test_mijozga_qaytarish.py — kech100 darvozasi (2026-09-27, 131-band, FOYDALANUVCHI QARORI "B" — "Kerak").

QAROR: tasdiqlab ortiqcha to'langan (to'langan > kelishilgan) buyurtma uchun DOIMIY belgi va ro'yxat
"Mijozga qaytarish kerak" (summa = ortiqcha); qaytarib berilgach yopish yo'li.

O'LCHANGAN (asl kod = zip 93, `work/probe131.py`): ortiqcha to'lov — (a) "qarzdan ko'p" tasdiqlangan to'lov,
(b) oldindan to'langan qisman «Tayyor», (c) kelishilgan summa kamaytirilgan — hech qayerda ko'rinmasdi
(`/api/orders/{id}` da maydon yo'q, "Qarzdorlar" da yo'q, Buyurtmalar ro'yxatida belgi yo'q; faqat (b) izohga
`[OVERPAID:…]` surati), qaytarish yo'li yo'q edi.

YECHIM: `Order.ortiqcha_tolov` (to'langan − kelishilgan, tiyin; yarim so'mgacha 0 — `debt_amount` bilan bir bardosh);
`crud.get_ortiqcha_tolovlar` / `GET /api/ortiqcha-tolovlar`; "Qaytarildi" — `POST /api/orders/{id}/refund-overpayment`
(manfiy to'lov, 24-band "Pul qaytdi" qoidasi bilan bir xil yozuv; QULF 101; takror himoyasi); "Qarzdorlar" —
"Mijozga qaytarish" bo'limi va eslatma; Buyurtmalar — ro'yxat belgisi va to'lov panelidagi DOIMIY belgi.

Bo'limlar:
  A — ko'rsatkich: (a) / (b) / (c) / (d — o'chirishda yakunlash, 93) / tiyin chegarasi (0.50 → 0, 0.51) / qarzdor / teng.
  B — ro'yxat (API va sahifalar): a'zolik, summa, tartib, o'chirilgan buyurtma, boshqa korxona yo'q.
  C — qaytarish: to'liq (standart summa), qisman + qolgani, ortiqchadan ko'p (400), ortiqcha yo'q (409), boshqa
      korxona (404), o'chirilgan buyurtma, usul / izoh / kim, to'lov holati, kassa, loyiha to'lovlari, audit.
  D — tana QAT'IY (400, hech narsa yozilmaydi).
  E — takror yuborish (bir xil summa — bitta yozuv), qaytarish to'lovini o'chirish — ortiqcha qaytadi.
  F — 93 bilan: yakunlangan (o'chirilgan) buyurtmada qaytarish, keyin tiklash — izchil (qarz = qaytarilgan).
  G — miqyos: ro'yxat / "Qarzdorlar" so'rovlari ortiqcha buyurtmalar soniga bog'liq EMAS.
  P — poyga (FAQAT PG): ikki parallel "Qaytarildi" — jami qaytarilgan ≤ ortiqcha.
  X — 5xx yo'q.   S — statik (sahifa JS, marshrutlar).

Ishlatish:
    python3 tools/test_mijozga_qaytarish.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_mijozga_qaytarish.py
"""
import os
import sys
import inspect
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "mijozga_qaytarish_test"
_T = tempfile.mkdtemp(prefix="mijozga_qaytarish_")
_DB = os.path.join(_T, "mijozga_qaytarish_test.db")

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
from models import (                               # noqa: E402
    UserRole, Project, Inventory, OrderItem, Order, Payment, ActivityLog, PaymentType,
)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from sqlalchemy import event                       # noqa: E402

_ASL_TAKROR = getattr(crud, "PUL_TAKROR_SONIYA", 8)
crud.PUL_TAKROR_SONIYA = 0      # bir xil summali to'lovlar (turli ssenariylarda) takror deb yutilmasin — E da qaytadi

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


def taxminan(a, b, eps=0.001):
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
if not _db.get(Company, 2):
    _db.add(Company(id=2, name="MQ Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "MQ_admin", "Parol123!", UserRole.ADMIN, "MQ Admin", company_id=1)
    auth.create_user(_db, "MQ_b", "Parol123!", UserRole.ADMIN, "MQ B", company_id=2)
    auth.create_user(_db, "MQ_usta", "Parol123!", UserRole.MASTER, "MQ Usta", company_id=1)
PENO = Inventory(company_id=1, item_name="MQ Penoplast", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
PENO_B = Inventory(company_id=2, item_name="MQ Penoplast B", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                   volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
PRJ = Project(company_id=1, client_name="MQ Mijoz", project_name="MQ loyiha", total_budget=0, total_paid=0)
PRJ_B = Project(company_id=2, client_name="MQ Mijoz B", project_name="MQ loyiha B", total_budget=0, total_paid=0)
_db.add_all([PENO, PENO_B, PRJ, PRJ_B])
_db.commit()
ID = {"PENO": PENO.id, "PENO_B": PENO_B.id, "PRJ": PRJ.id, "PRJ_B": PRJ_B.id}
_db.close()


def kirish(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c if r.status_code == 302 else None


C = kirish("MQ_admin")
CB = kirish("MQ_b")
CU = kirish("MQ_usta")
if not C or not CB:
    print("LOGIN BO'LMADI")
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def nom(p="MQ"):
    _n[0] += 1
    return f"{p}{_n[0]}"


def buyurtma(uzunlik=10, narx=50_000, agreed=None, klient=None, prj=None, peno=None):
    tana = {"project_id": prj or ID["PRJ"], "order_type": "product", "loy_kg": 0,
            "items": [{"name": nom("D"), "category": "profil", "width": 20, "thickness": 10, "length": uzunlik,
                       "quantity": 10, "unit_price": narx, "is_coated": False, "penoplast_id": peno or ID["PENO"]}]}
    if agreed is not None:
        tana["agreed_amount"] = agreed
    r = req(klient or C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    oid = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
    s = SessionLocal()
    try:
        iid = s.query(OrderItem.id).filter(OrderItem.order_id == oid).first()
    finally:
        s.close()
    return oid, (iid[0] if iid else None)


def tolov(oid, summa, tasdiq=True, klient=None):
    return req(klient or C, "post", "/api/payments", json={"order_id": oid, "amount": summa, "notes": nom("t"),
                                                         "confirm_overpay": tasdiq}).status_code


def yuk(oid, iid, miqdor):
    return req(C, "post", "/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}],
                                                  "notes": nom("y"), "transport_cost": 0, "transport_payer": "none",
                                                  "payment_method": "naqd"}).status_code


def ortiqcha(oid, klient=None):
    d = js(req(klient or C, "get", f"/api/orders/{oid}")) or {}
    return d.get("ortiqcha_tolov") if isinstance(d, dict) else None


def royxat(klient=None):
    d = js(req(klient or C, "get", "/api/ortiqcha-tolovlar")) or {}
    return d if isinstance(d, dict) else {}


def royxatda(oid, klient=None):
    for x in royxat(klient).get("buyurtmalar") or []:
        if x.get("order_id") == oid:
            return x
    return None


def qaytar(oid, klient=None, **tana):
    r = req(klient or C, "post", f"/api/orders/{oid}/refund-overpayment", json=tana)
    return r.status_code, (js(r) or {})


def tolovlar(oid):
    s = SessionLocal()
    try:
        return [(round(float(p.amount), 2), p.payment_method.value if p.payment_method else None, p.notes, p.received_by)
                for p in s.query(Payment).filter(Payment.order_id == oid).order_by(Payment.id).all()]
    finally:
        s.close()


def holat(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        return {"paid": round(float(o.paid_amount or 0), 2), "agreed": round(float(o.kelishilgan_summa), 2),
                "debt": round(float(o.debt_amount or 0), 2), "pay_status": o.payment_status.value,
                "del": bool(o.is_deleted), "status": o.status.value, "archived": bool(o.is_archived)} if o else None
    finally:
        s.close()


def kassa():
    s = SessionLocal()
    try:
        return round(float(services.get_cash_balance(s, company_id=1).get("balance") or 0), 2)
    finally:
        s.close()


def loyiha_tolangan():
    s = SessionLocal()
    try:
        return round(float(s.get(Project, ID["PRJ"]).total_paid or 0), 2)
    finally:
        s.close()


def debts_html(klient=None):
    return str(getattr(req(klient or C, "get", "/debts"), "text", ""))


def refunds_bolim(html):
    b = html.find('<div id="tab-refunds"')
    e = html.find('<!-- YETKAZIB BERUVCHI QARZLARI -->', b)
    return html[b:e] if b >= 0 and e > b else ""


def order_num(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        return o.order_number if o else None
    finally:
        s.close()


# ══════════════════════════════════════════════════════════════
# A — ko'rsatkich
# ══════════════════════════════════════════════════════════════
section("A. Ortiqcha to'lov ko'rsatkichi (DOIMIY — to'lovlar va kelishilgan summadan)")
oa, ia = buyurtma()
_r409 = tolov(oa, 600_000, tasdiq=False)
tolov(oa, 600_000, tasdiq=True)
check("A1 (a) qarzdan ko'p tasdiqlangan to'lov: 409 tasdiqsiz, keyin ortiqcha 100 000",
      _r409 == 409 and taxminan(ortiqcha(oa), 100_000), (_r409, ortiqcha(oa)))
ob, ib = buyurtma()
tolov(ob, 500_000)
yuk(ob, ib, 4)
req(C, "post", f"/api/orders/{ob}/ready")
check("A2 (b) oldindan to'langan, qisman «Tayyor» — ortiqcha 300 000", taxminan(ortiqcha(ob), 300_000), ortiqcha(ob))
oc, ic = buyurtma()
tolov(oc, 500_000)
req(C, "put", f"/api/orders/{oc}/agreed-amount", json={"agreed_amount": 450_000})
check("A3 (c) kelishilgan summa 450 000 ga kamaytirildi — ortiqcha 50 000", taxminan(ortiqcha(oc), 50_000), ortiqcha(oc))
od, idd = buyurtma()
tolov(od, 500_000)
yuk(od, idd, 4)
req(C, "delete", f"/api/orders/{od}")
check("A4 (d) o'chirishda yakunlangan (93) — ortiqcha 300 000 (o'chirilgan buyurtma)",
      taxminan(ortiqcha(od), 300_000) and holat(od)["del"], (ortiqcha(od), holat(od)))
oe, ie = buyurtma(uzunlik=10, narx=46_153.84)          # jami 461 538.40
tolov(oe, 461_538.90)
check("A5 tiyin chegarasi: 0.50 ortiqcha — 0 (bardosh, qarz qoidasi bilan bir)", taxminan(ortiqcha(oe), 0.0), ortiqcha(oe))
tolov(oe, 0.01)
check("A6 0.51 ortiqcha — 0.51", taxminan(ortiqcha(oe), 0.51), ortiqcha(oe))
og, ig = buyurtma()
tolov(og, 100_000)
check("A7 qarzdor buyurtma — 0 (qarz 400 000)", taxminan(ortiqcha(og), 0.0) and holat(og)["debt"] == 400_000,
      (ortiqcha(og), holat(og)))
oh, ih = buyurtma()
tolov(oh, 500_000)
check("A8 aniq to'langan — 0", taxminan(ortiqcha(oh), 0.0), ortiqcha(oh))
# kech100 (kmut100 Q05): 0.50 ortiqcha QOLADIGAN buyurtma (A5 niki 0.51 ga o'tdi) — SQL oldindan saralash (+0.4) uni o'tkazadi,
# yakuniy (tiyin) shart esa chiqaradi: ro'yxatda bo'lmasligi kerak.
oi, _ii = buyurtma(uzunlik=10, narx=46_153.84)          # jami 461 538.40
tolov(oi, 461_538.90)
check("A10 0.50 ortiqcha qoladigan buyurtma — 0", taxminan(ortiqcha(oi), 0.0), ortiqcha(oi))
_s = SessionLocal()
try:
    _o = _s.get(Order, ob)
    check("A9 model: Order.ortiqcha_tolov = ortiqcha_tolov_qiymati(to'langan, kelishilgan)",
          getattr(_o, "ortiqcha_tolov", None) == 300_000.0, getattr(_o, "ortiqcha_tolov", None))
finally:
    _s.close()


# ══════════════════════════════════════════════════════════════
# B — ro'yxat (API va sahifalar)
# ══════════════════════════════════════════════════════════════
section("B. \"Mijozga qaytarish kerak\" — ro'yxat, Qarzdorlar, Buyurtmalar")
R = royxat()
_ids = [x.get("order_id") for x in R.get("buyurtmalar") or []]
check("B1 API: (a) (b) (c) (d) (0.51) bor; qarzdor / aniq / 0.50 yo'q",
      set(_ids) == {oa, ob, oc, od, oe} and oi not in _ids, _ids)
check("B2 API: summa AYNAN, jami = yig'indi, soni",
      R.get("soni") == 5 and taxminan(R.get("jami"), 100_000 + 300_000 + 50_000 + 300_000 + 0.51)
      and taxminan((royxatda(ob) or {}).get("ortiqcha"), 300_000) and taxminan((royxatda(oe) or {}).get("ortiqcha"), 0.51), R)
_ort = [x.get("ortiqcha") for x in R.get("buyurtmalar") or []]
check("B3 API: tartib — ortiqcha kamayishi bo'yicha (teng — id)",
      _ort == sorted(_ort, reverse=True) and _ids[:2] == sorted([ob, od]), (_ids, _ort))
_xd = royxatda(od) or {}
check("B4 API: o'chirilgan buyurtma belgisi, mijoz / loyiha / kelishilgan / to'langan",
      _xd.get("is_deleted") is True and _xd.get("client_name") == "MQ Mijoz" and taxminan(_xd.get("agreed"), 200_000)
      and taxminan(_xd.get("paid"), 500_000), _xd)
_h = debts_html()
_rb = refunds_bolim(_h)
check("B5 Qarzdorlar: eslatma + bo'lim — 5 buyurtma, raqamlari, o'chirilgani belgilangan",
      'id="qaytarish-banner"' in _h and "Mijozga qaytarish (5)" in _h
      and all(order_num(x) in _rb for x in (oa, ob, oc, od, oe)) and order_num(og) not in _rb
      and "o'chirilgan" in _rb and 'data-ortiqcha="0.51"' in _rb, _rb[:300])
check("B6 Qarzdorlar: ortiqcha to'langan buyurtma 'Bizga qarzdorlar' da YO'Q (qarz 0)",
      order_num(ob) not in _h[:_h.find('<div id="tab-refunds"')].split('id="tab-customers"')[-1], "")
_oh = str(getattr(req(C, "get", "/orders"), "text", ""))
_belgilar = _oh.count('class="ort-qaytarish"')
check("B7 Buyurtmalar ro'yxati: belgi FAQAT o'chirilmagan ortiqcha to'langanlarda (a, b, c, 0.51) — 4",
      _belgilar == 4, _belgilar)
_rb2 = royxat(CB)
check("B8 boshqa korxona ro'yxati bo'sh (A ning buyurtmalari ko'rinmaydi)", _rb2.get("soni") == 0, _rb2)
_ru = req(CU, "get", "/api/ortiqcha-tolovlar").status_code if CU else None
check("B9 usta (MASTER) roli — ro'yxatga kirish YO'Q (403 / 401)", _ru in (401, 403), _ru)


# ══════════════════════════════════════════════════════════════
# C — qaytarish
# ══════════════════════════════════════════════════════════════
section("C. «Qaytarildi» — manfiy to'lov, ro'yxatdan chiqadi")
k0, lt0 = kassa(), loyiha_tolangan()
st, d = qaytar(ob, payment_method="plastik", notes="kartaga")
t_b = tolovlar(ob)
check("C1 to'liq qaytarish (summa berilmagan — butun ortiqcha): 200, −300 000 plastik, izoh / kim",
      st == 200 and taxminan(d.get("qaytarildi"), 300_000) and d.get("ortiqcha_qoldi") == 0
      and t_b[-1][0] == -300_000 and t_b[-1][1] == "plastik" and str(t_b[-1][2]).startswith("↩ Ortiqcha to'lov mijozga qaytarildi")
      and "kartaga" in str(t_b[-1][2]) and t_b[-1][3] == "MQ Admin", (st, d, t_b[-1:]))
check("C2 buyurtma: to'langan = kelishilgan (200 000), ortiqcha 0, holat to'langan",
      holat(ob)["paid"] == 200_000 and taxminan(ortiqcha(ob), 0) and holat(ob)["pay_status"] == "paid", holat(ob))
check("C3 kassa −300 000, loyiha to'lovlari −300 000", taxminan(kassa() - k0, -300_000) and taxminan(loyiha_tolangan() - lt0, -300_000),
      (k0, kassa(), lt0, loyiha_tolangan()))
check("C4 ro'yxatdan chiqdi", royxatda(ob) is None, royxatda(ob))
_s = SessionLocal()
try:
    _aud = _s.query(ActivityLog).filter(ActivityLog.entity_type == "order", ActivityLog.entity_id == ob,
                                        ActivityLog.action == "refunded").count()
finally:
    _s.close()
check("C5 audit yozuvi (refunded)", _aud == 1, _aud)
# qisman
st1, d1 = qaytar(od, amount=100_000)
check("C6 qisman qaytarish (o'chirilgan buyurtma) 100 000 — qolgani 200 000 ro'yxatda",
      st1 == 200 and taxminan(d1.get("ortiqcha_qoldi"), 200_000) and taxminan((royxatda(od) or {}).get("ortiqcha"), 200_000),
      (st1, d1))
st2, d2 = qaytar(od, amount=200_000.01)
check("C7 ortiqchadan ko'p (200 000.01 > 200 000) — 400, hech narsa yozilmadi",
      st2 == 400 and len(tolovlar(od)) == 2, (st2, d2, tolovlar(od)))
st3, d3 = qaytar(od, amount=200_000)
check("C8 qolganini qaytarish — 0, ro'yxatdan chiqdi", st3 == 200 and d3.get("ortiqcha_qoldi") == 0 and royxatda(od) is None,
      (st3, d3))
st4, d4 = qaytar(og)
check("C9 qarzdor buyurtma — 409 (ortiqcha yo'q), hech narsa yozilmadi", st4 == 409 and len(tolovlar(og)) == 1, (st4, d4))
st5, d5 = qaytar(oa, klient=CB)
check("C10 boshqa korxona nomidan — 404, hech narsa yozilmadi", st5 == 404 and len(tolovlar(oa)) == 1, (st5, d5))
st6, d6 = qaytar(10_000_000)
check("C11 yo'q buyurtma — 404", st6 == 404, (st6, d6))
st7, d7 = qaytar(oe, amount=0.51, payment_method="o'tkazma")
check("C12 tiyinli ortiqcha 0.51 — o'tkazma, 0 qoldi", st7 == 200 and d7.get("ortiqcha_qoldi") == 0
      and tolovlar(oe)[-1][:2] == (-0.51, "o'tkazma"), (st7, d7, tolovlar(oe)[-1:]))
if CU:
    st8, _d8 = qaytar(oa, klient=CU)
    check("C13 usta (MASTER) — ruxsat YO'Q (403 / 401), yozilmadi", st8 in (401, 403) and len(tolovlar(oa)) == 1, st8)


# ══════════════════════════════════════════════════════════════
# D — tana QAT'IY
# ══════════════════════════════════════════════════════════════
section("D. Tana qat'iy — 400, hech narsa yozilmaydi")
_nd = len(tolovlar(oa))
for nomi, tana in (("matn summa", {"amount": "100"}), ("true", {"amount": True}), ("manfiy", {"amount": -5}),
                   ("0", {"amount": 0}), ("1e20", {"amount": 1e20}), ("0.001", {"amount": 0.001}),
                   # kech100 (kmut100 Q18): 3 xonali, lekin yaxlitlangach musbat summa — crud `_pul2` jim 12.35 ga yaxlitlardi
                   ("3 xona 12.345", {"amount": 12.345}),
                   ("noma'lum maydon", {"summa": 5}), ("usul karta", {"payment_method": "karta"}),
                   ("usul son", {"payment_method": 1}), ("izoh son", {"notes": 5}), ("izoh 301", {"notes": "x" * 301})):
    r = req(C, "post", f"/api/orders/{oa}/refund-overpayment", json=tana)
    check(f"D {nomi}: 400", r.status_code == 400, (r.status_code, r.text[:150]))
r = req(C, "post", f"/api/orders/{oa}/refund-overpayment", json=[1, 2])
check("D ro'yxat tana: 400 / 422", r.status_code in (400, 422), (r.status_code, r.text[:150]))
check("D hech biri yozilmadi", len(tolovlar(oa)) == _nd and taxminan(ortiqcha(oa), 100_000), tolovlar(oa))
r = req(C, "post", f"/api/orders/{oa}/refund-overpayment")
check("D tanasiz — butun ortiqcha (100 000) qaytarildi", r.status_code == 200 and taxminan(ortiqcha(oa), 0), (r.status_code, r.text[:200]))


# ══════════════════════════════════════════════════════════════
# E — takror yuborish, qaytarish to'lovini o'chirish
# ══════════════════════════════════════════════════════════════
section("E. Takror yuborish va qaytarishni o'chirish")
crud.PUL_TAKROR_SONIYA = _ASL_TAKROR
oq, iq = buyurtma()
tolov(oq, 700_000)
e1, de1 = qaytar(oq, amount=100_000)
e2, de2 = qaytar(oq, amount=100_000)
check("E1 bir xil summa ikki marta (takror) — ikkinchisi duplicate, BITTA yozuv",
      e1 == 200 and e2 == 200 and de2.get("duplicate") is True and de1.get("payment_id") == de2.get("payment_id")
      and [t[0] for t in tolovlar(oq)] == [700_000, -100_000] and taxminan(ortiqcha(oq), 100_000), (de1, de2, tolovlar(oq)))
# kech100 (kmut100 Q24): takror izlash FAQAT "↩ Ortiqcha to'lov mijozga qaytarildi" yozuvlari orasida — boshqa manfiy to'lov
# (24-band "Pul qaytdi" — qaytgan mahsulot uchun) o'sha summada 8 s ichida bo'lsa ham qaytarish YANGI yozuv bo'ladi.
oq3, _iq3 = buyurtma()
tolov(oq3, 700_000)
_s3 = SessionLocal()
try:
    _s3.add(Payment(order_id=oq3, amount=-50_000, payment_type=PaymentType.PARTIAL, received_by="E3",
                    notes="Qaytarilgan mahsulot uchun pul qaytarildi: E3 (1 m)"))
    _s3.commit()
finally:
    _s3.close()
e3, de3 = qaytar(oq3, amount=50_000)
check("E3 boshqa manfiy to'lov (\"Pul qaytdi\") o'sha summada 8 s ichida — qaytarish takror EMAS, yangi yozuv",
      e3 == 200 and de3.get("duplicate") is False and [t[0] for t in tolovlar(oq3)] == [700_000, -50_000, -50_000]
      and taxminan(ortiqcha(oq3), 100_000), (de3, tolovlar(oq3)))
crud.PUL_TAKROR_SONIYA = 0
_pid = de1.get("payment_id")
rdel = req(C, "delete", f"/api/payments/{_pid}")
check("E2 qaytarish to'lovi o'chirildi — ortiqcha QAYTA 200 000 va ro'yxatda",
      rdel.status_code == 200 and taxminan(ortiqcha(oq), 200_000) and royxatda(oq) is not None,
      (rdel.status_code, ortiqcha(oq)))


# ══════════════════════════════════════════════════════════════
# F — 93 bilan: yakunlangan buyurtmada qaytarish, keyin tiklash
# ══════════════════════════════════════════════════════════════
section("F. O'chirishda yakunlangan buyurtma: qaytarish → tiklash — izchil")
of, if_ = buyurtma()
tolov(of, 500_000)
yuk(of, if_, 4)
req(C, "delete", f"/api/orders/{of}")
sf, dff = qaytar(of)
rr = req(C, "post", f"/api/orders/{of}/restore")
hf = holat(of)
check("F1 qaytarildi (300 000), tiklandi: kelishilgan 500 000, to'langan 200 000, qarz 300 000, ortiqcha 0",
      sf == 200 and rr.status_code == 200 and hf["agreed"] == 500_000 and hf["paid"] == 200_000 and hf["debt"] == 300_000
      and taxminan(ortiqcha(of), 0) and hf["pay_status"] == "partial" and not hf["del"], (sf, rr.status_code, hf))


# ══════════════════════════════════════════════════════════════
# G — miqyos (so'rovlar soni)
# ══════════════════════════════════════════════════════════════
section("G. Miqyos — so'rovlar soni ortiqcha buyurtmalar soniga bog'liq EMAS")
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


q_api0 = sorovlar(lambda: royxat())
q_deb0 = sorovlar(lambda: debts_html())
for _ in range(6):
    _o, _i = buyurtma()
    tolov(_o, 520_000)
q_api1 = sorovlar(lambda: royxat())
q_deb1 = sorovlar(lambda: debts_html())
check("G1 /api/ortiqcha-tolovlar: +6 ortiqcha buyurtma — so'rovlar O'ZGARMADI", q_api1 == q_api0, (q_api0, q_api1))
check("G2 /debts: +6 ortiqcha buyurtma — so'rovlar O'ZGARMADI", q_deb1 == q_deb0, (q_deb0, q_deb1))


# ══════════════════════════════════════════════════════════════
# P — poyga (FAQAT PG)
# ══════════════════════════════════════════════════════════════
section("P. Poyga (HAQIQIY PG): ikki parallel «Qaytarildi»")
if not PG_URL:
    print("  (SQLite — haqiqiy parallellik yo'q, o'tkazildi)")
else:
    for tak in range(3):
        op, ip = buyurtma()
        tolov(op, 800_000)            # ortiqcha 300 000
        nat = []
        b = threading.Barrier(2)

        def _oqim(summa):
            s = SessionLocal()
            try:
                b.wait()
                try:
                    with crud.bitta_tranzaksiya(s):
                        crud.ortiqcha_tolovni_qaytar(s, op, summa=summa, usul="naqd", kim="P", company_id=1)
                    nat.append(("ok", summa))
                except Exception as e:     # noqa: BLE001
                    nat.append((type(e).__name__, summa))
            finally:
                s.close()

        t1 = threading.Thread(target=_oqim, args=(200_000,))
        t2 = threading.Thread(target=_oqim, args=(150_000,))
        t1.start(); t2.start(); t1.join(); t2.join()
        _qaytgan = -sum(t[0] for t in tolovlar(op) if t[0] < 0)
        check(f"P{tak} 200 000 ∥ 150 000 (ortiqcha 300 000): bittasi o'tdi, jami qaytarilgan ≤ ortiqcha, qoldiq izchil",
              sum(1 for x in nat if x[0] == "ok") == 1 and _qaytgan <= 300_000 + 0.001
              and taxminan(ortiqcha(op), 300_000 - _qaytgan), (nat, _qaytgan, ortiqcha(op)))


# ══════════════════════════════════════════════════════════════
# X — 5xx
# ══════════════════════════════════════════════════════════════
section("X. Server xatosi (5xx) yo'q")
check("X1 test davomida 5xx yo'q", not XATOLAR_5XX, XATOLAR_5XX[:5])


# ══════════════════════════════════════════════════════════════
# S — statik
# ══════════════════════════════════════════════════════════════
section("S. Statik")
_q = manba(crud, "ortiqcha_tolovni_qaytar")
check("S1 qaytarish: QULF (101) → qayta o'qish → takror → ortiqcha → manfiy to'lov → holat → loyiha → audit",
      tartibda(_q, "_pul_qulfi(db, 101, order_id)", "db.expire_all()", "order = _oq.first()", "_is_duplicate_submit = True",
               "ortiqcha = order.ortiqcha_tolov", "amount=-summa", "_update_order_payment_status(db, order)",
               "_loyiha_tolangan_yangila(db, order.project)", "log_activity(db, \"refunded\""), "")
_g = manba(crud, "get_ortiqcha_tolovlar")
check("S2 ro'yxat: bitta GROUP BY (korxona — buyurtma orqali), IN yuklash, yakuniy shart ortiqcha_tolov",
      tartibda(_g, "_f131.sum(Payment.amount)", ".join(Order, Order.id == Payment.order_id)", "Order.company_id == company_id",
               ".group_by(Payment.order_id)", "_sil131(Order.payments)", "o.ortiqcha_tolov > 0"), "")
_d = open(os.path.join(ROOT, "templates", "debts.html"), encoding="utf-8").read()
check("S3 debts.html: bo'lim, tanlash, «Qaytarildi» — tasdiq, POST, server sababi; ?qaytarish=",
      tartibda(_d, 'id="tab-refunds"', "function selectRefund(el)", "escapeHtml(d.orderNumber)", "async function saveRefund()",
               "customConfirm(", "/refund-overpayment", "serverSababi(res", "get('qaytarish')")
      and "document.getElementById('tab-refunds').style.display" in _d, "")
_oh2 = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
check("S4 orders.html: to'lov paneli belgisi server maydonidan (ortiqcha_tolov), izoh surati EMAS",
      "Number(order.ortiqcha_tolov)" in _oh2 and "overpaidMatch" not in _oh2 and 'class="ort-qaytarish"' in _oh2, "")
_ag = manba(main, "api_get_order")
check("S5 GET /api/orders/{id}: ortiqcha_tolov maydoni", '"ortiqcha_tolov": order.ortiqcha_tolov' in _ag, "")

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
