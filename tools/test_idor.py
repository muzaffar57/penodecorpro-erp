#!/usr/bin/env python3
"""
test_idor.py — IDOR (Insecure Direct Object Reference) darvozasi.

NIMA UCHUN KERAK
----------------
`tools/tenant_lint.py` STATIK tekshiruv: u `db.query(X)` yonida
`company_id` filtri bor-yo'qligini ko'radi. Uning baselinesida 156 ta
"filtrsiz o'qish" ma'lum holat sifatida turibdi. Lekin statik tekshiruv
ayta olmaydi: ulardan qaysi biri HAQIQIY xavf?

Xavf shakli aniq: **B korxona admini A korxona yozuvini ID raqami
bo'yicha o'qiy oladimi yoki o'zgartira oladimi?** HTTP so'rovida ID —
manzilning bir qismi, ya'ni foydalanuvchi uni bemalol almashtira oladi.

Bu test aynan shuni HTTP darajasida o'lchaydi: haqiqiy `TestClient`,
haqiqiy login, haqiqiy cookie. Bu MUHIM, chunki `tenant_context` dagi
avtomatik filtr faqat `auth.get_current_user` ishlaganda yoqiladi —
sessiyani to'g'ridan-to'g'ri ochadigan testlar uni umuman sinamaydi
(2026-09-21 da o'lchangan: `test_tenant_isolation` da filtr 406 marta
"kontekst yo'q" deb o'tkazib yuborilgan, 0 marta qo'llangan).

ISHLATISH
---------
    python tools/test_idor.py            # TENANT_FILTER holicha
    TENANT_FILTER=1 python tools/test_idor.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bitta sizish bor.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "idor_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

# main import qilinganda migratsiya loglari chiqadi — ularni yutamiz
_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402,F401
    import crud, auth, schemas                     # noqa: E402

from database import SessionLocal, engine          # noqa: E402
from sqlalchemy import event                       # noqa: E402
import tenant_context as _tc                       # noqa: E402


@event.listens_for(engine, "connect")
def _fk_on(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Inventory, Recipe, Project, Employee, Order, User,
)
from fastapi.testclient import TestClient          # noqa: E402

db = SessionLocal()
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}   {detail}")


def section(t):
    print(f"\n--- {t} ---")


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik: ikkita korxona, har birida bir nechta yozuv
# ══════════════════════════════════════════════════════════════
if not db.query(Company).filter(Company.id == 2).first():
    db.add(Company(id=2, name="Test Korxona B"))
    db.commit()

N_SPARE = 24         # har bir turdan nechta zaxira yozuv (mutatsiya probi uchun)


def build(cid, tag):
    """Bitta korxonaning ma'lumotlari. Mutatsiya probi har safar YANGI
    yozuvda o'tkaziladi — shuning uchun har turdan N_SPARE ta yaratamiz."""
    u = auth.create_user(db, f"{tag}_user", "Parol123!", UserRole.ADMIN,
                         tag, company_id=cid)
    invs, recs, projs, emps, ords = [], [], [], [], []
    for k in range(N_SPARE):
        i = crud.add_item(db, schemas.InventoryCreate(
            item_name=f"{tag}_Mat{k}", unit="kg", stock_quantity=100,
            price_per_unit=1000), company_id=cid)
        invs.append(i)
        recs.append(crud.create_recipe(db, schemas.RecipeCreate(
            name=f"{tag}_Rec{k}", batch_size_kg=10,
            ingredients=[schemas.RecipeIngredientCreate(
                inventory_id=i.id, quantity_kg=1)]), company_id=cid))
        p = crud.create_project(db, schemas.ProjectCreate(
            project_name=f"{tag}_L{k}", client_name=f"{tag}_Mijoz{k}"),
            company_id=cid)
        projs.append(p)
        emps.append(crud.create_employee(db, schemas.EmployeeCreate(
            name=f"{tag}_Hodim{k}", pay_type="fixed", fixed_amount=1000000),
            company_id=cid))
        ords.append(crud.create_order(db, schemas.OrderCreate(
            project_id=p.id, order_type="product",
            items=[schemas.OrderItemCreate(name=f"{tag}_Detal{k}",
                                           category="panel",
                                           quantity=1, unit_price=100000)]),
            performed_by=tag))
    return dict(user=u, inv=invs, recipe=recs, project=projs,
                employee=emps, order=ords)


with contextlib.redirect_stdout(_quiet):
    A = build(1, "AAA")
    B = build(2, "BBB")

# A ning zaxira yozuvlaridan navbat bilan olish uchun hisoblagichlar
_next = {"inv": 0, "recipe": 0, "project": 0, "employee": 0, "order": 0}


def a_id(kind):
    """A korxonaning KEYINGI ishlatilmagan yozuvi — har probga toza nishon."""
    idx = _next[kind]
    _next[kind] += 1
    assert idx < N_SPARE, f"{kind} uchun zaxira tugadi (N_SPARE oshiring)"
    return A[kind][idx].id


client = TestClient(main.app, base_url="https://testserver")
_r = client.post("/login", data={"username": "BBB_user", "password": "Parol123!"},
                 follow_redirects=False)
assert _r.status_code == 302, f"B admin login bo'lmadi: {_r.status_code}"
assert "session_token" in client.cookies, "sessiya cookie o'rnatilmadi"

print("=" * 66)
print("IDOR DARVOZASI — B korxona admini A korxona yozuviga uriladi")
print("TENANT_FILTER = " + ("1 (YOQILGAN)" if _tc.ENABLED else "0 (ochiq emas)"))
print("=" * 66)

# ══════════════════════════════════════════════════════════════
section("1. O'QISH: A ning yozuvi B ga ko'rinadimi")
# ══════════════════════════════════════════════════════════════
# Kutilgan javob: 403 yoki 404. 200 — SIZISH.
_YM = "?year=2026&month=9"
READS = [
    ("buyurtma detali",      "/api/orders/{}",                         "order"),
    ("buyurtma foydasi",     "/api/orders/{}/profit",                  "order"),
    ("yetkazish holati",     "/api/orders/{}/delivery-status",         "order"),
    ("rejalangan loy",       "/api/orders/{}/planned-loy",             "order"),
    ("buyurtma ilovalari",   "/api/orders/{}/attachments",             "order"),
    ("buyurtma PDF",         "/api/orders/{}/pdf",                     "order"),
    ("buyurtma xulosa PDF",  "/api/orders/{}/summary-pdf",             "order"),
    ("loyiha statistikasi",  "/api/projects/{}/detail-stats",          "project"),
    ("loyiha detallari",     "/api/projects/{}/items",                 "project"),
    ("hodim avanslari",      "/api/employees/{}/advances" + _YM,       "employee"),
    ("hodim tuzatmasi",      "/api/employees/{}/monthly-adjustment" + _YM, "employee"),
    ("hodim kompensatsiyasi", "/api/employees/{}/compensation-history", "employee"),
    ("hodim qarz tarixi",    "/api/obligations/employee/{}/timeline" + _YM, "employee"),
]
for label, tpl, kind in READS:
    rid = a_id(kind)
    r = client.get(tpl.format(rid))
    check(f"GET {tpl.format('A')}  \u2192 {r.status_code}",
          r.status_code in (403, 404),
          f"SIZISH: {str(r.text)[:120]}")


# ══════════════════════════════════════════════════════════════
section("2. O'ZGARTIRISH: A ning yozuvini B buza oladimi")
# ══════════════════════════════════════════════════════════════
def mutate(label, method, tpl, kind, payload=None, verify=None):
    """verify(rid) -> True agar A ning yozuvi HAQIQATAN o'zgargan bo'lsa."""
    rid = a_id(kind)
    fn = getattr(client, method)
    kw = {}
    if payload is not None:
        kw["json" if isinstance(payload, dict) else "data"] = payload
    r = fn(tpl.format(rid), **kw)
    db.expire_all()
    changed = verify(rid) if verify else None
    if changed is None:
        ok = r.status_code in (403, 404)
        detail = f"SIZISH: {r.status_code} {str(r.text)[:110]}"
    else:
        ok = not changed
        detail = f"A NING YOZUVI O'ZGARDI (status {r.status_code})"
    check(f"{method.upper()} {tpl.format('A')}  \u2192 {r.status_code}", ok, detail)


mutate("narx", "post", "/api/inventory/{}/price", "inv",
       {"price_per_unit": 999999},
       lambda i: db.get(Inventory, i).price_per_unit == 999999)

mutate("min zaxira", "post", "/api/inventory/{}/min-stock", "inv",
       {"min_stock": 777},
       lambda i: (db.get(Inventory, i).min_stock or 0) == 777)

mutate("standart penoplast", "post", "/api/inventory/{}/set-default-penoplast",
       "inv", None,
       lambda i: bool(getattr(db.get(Inventory, i),
                              "is_default_penoplast", False)))

mutate("ombor o'chirish", "delete", "/api/inventory/{}", "inv", None,
       lambda i: db.get(Inventory, i) is None)

mutate("retsept o'chirish", "delete", "/api/recipes/{}", "recipe", None,
       lambda i: db.get(Recipe, i) is None)

mutate("loyiha o'chirish", "delete", "/api/projects/{}", "project", None,
       lambda i: bool(getattr(db.get(Project, i), "is_deleted", False))
       or db.get(Project, i) is None)

mutate("hodim o'chirish", "delete", "/api/employees/{}", "employee", None,
       lambda i: bool(getattr(db.get(Employee, i), "is_deleted", False))
       or db.get(Employee, i) is None)

mutate("buyurtma o'chirish", "delete", "/api/orders/{}", "order", None,
       lambda i: bool(getattr(db.get(Order, i), "is_deleted", False))
       or db.get(Order, i) is None)

mutate("buyurtma qadash", "post", "/api/orders/{}/pin", "order", None,
       lambda i: bool(getattr(db.get(Order, i), "is_pinned", False)))

mutate("buyurtmani tayyor qilish", "post", "/api/orders/{}/ready", "order", None,
       lambda i: str(getattr(db.get(Order, i).status, "value",
                             db.get(Order, i).status)) == "ready")

mutate("kelishilgan summa", "put", "/api/orders/{}/agreed-amount", "order",
       {"agreed_amount": 1},
       lambda i: (getattr(db.get(Order, i), "agreed_amount", None) == 1))


# ══════════════════════════════════════════════════════════════
section("2b. KENG QAMROV: qolgan ID-li marshrutlar")
# ══════════════════════════════════════════════════════════════
# 2026-09-21 da 97 ta ID-li marshrut supurib chiqildi. Quyidagilar
# o'sha supurishda 403/404 bergan — ya'ni HOZIR himoyalangan. Ular shu
# yerda QULFLANADI: kelajakda qo'riqchi tushib qolsa, darvoza tutadi.
#
# MUHIM: yuk (payload) TO'G'RI bo'lishi shart. Noto'g'ri yuk 422 beradi
# va 422 himoyani ISBOTLAMAYDI — so'rov qo'riqchigacha yetib bormaydi.
# Aynan shu sabab birinchi supurishda 20 ta marshrut "tekshirilgan" deb
# ko'ringan, aslida esa tekshirilmagan edi.
_ORDER_BODY = {"project_id": None, "order_type": "product",
               "items": [{"name": "X_D", "category": "panel",
                          "quantity": 1, "unit_price": 100000}]}
_ORDER_BODY["project_id"] = B["project"][0].id

BROAD = [
    ("post",   "/api/projects/{}/payment",              "project",   {"amount": 1000}, None),
    ("post",   "/api/inventory/{}/stock",               "inv",       None, {"quantity_change": 5, "reason": "sinov"}),
    ("post",   "/api/inventory/{}/purchase",            "inv",       None, {"quantity": 1, "price_per_unit": 1000}),
    ("post",   "/api/employees/{}/advance",             "employee",  {"amount": 1000}, None),
    ("post",   "/api/employees/{}/monthly-adjustment",  "employee",  {"year": 2026, "month": 9, "reduction_amount": 100}, None),
    ("post",   "/api/obligations/employee/{}/close",    "employee",  {"year": 2026, "month": 9, "amount": 100}, None),
    ("put",    "/api/inventory/{}",                     "inv",       None, {"item_name": "Buzildi"}),
    ("put",    "/api/recipes/{}",                       "recipe",    None, {"name": "Buzildi", "batch_size_kg": 10, "ingredients": []}),
    ("put",    "/api/projects/{}",                      "project",   None, {"project_name": "Buzildi"}),
    ("put",    "/api/employees/{}",                     "employee",  None, {"name": "Buzildi"}),
    ("put",    "/api/orders/{}",                        "order",     None, _ORDER_BODY),
    ("put",    "/api/orders/{}/loy",                    "order",     {"loy_kg": 5}, None),
    ("post",   "/api/orders/{}/coating-notify",         "order",     {"loy_kg": 5}, None),
    ("post",   "/api/orders/{}/activate",               "order",     None, None),
    ("post",   "/api/orders/{}/restore",                "order",     None, None),
    ("post",   "/api/projects/{}/restore",              "project",   None, None),
    ("post",   "/api/employees/{}/restore",             "employee",  None, None),
    ("delete", "/api/orders/{}/permanent",              "order",     None, None),
    ("delete", "/api/projects/{}/permanent",            "project",   None, None),
    ("delete", "/api/employees/{}/permanent",           "employee",  None, None),
]
for meth, tpl, kind, params, body in BROAD:
    rid = a_id(kind)
    kw = {}
    if params:
        kw["params"] = params
    if body is not None:
        kw["json"] = body
    r = getattr(client, meth)(tpl.format(rid), **kw)
    check(f"{meth.upper()} {tpl.format('A')}  \u2192 {r.status_code}",
          r.status_code in (403, 404),
          ("YUK NOTO'G'RI — himoya isbotlanmadi: " if r.status_code == 422
           else "SIZISH: ") + str(r.text)[:110])


# ══════════════════════════════════════════════════════════════
section("3. ENG OG'IR: A ning ADMIN foydalanuvchisiga tegish")
# ══════════════════════════════════════════════════════════════
a_user_id = A["user"].id
r = client.post(f"/api/users/{a_user_id}/toggle")
db.expire_all()
still_active = bool(db.get(User, a_user_id).is_active)
check(f"POST /api/users/A/toggle  \u2192 {r.status_code}", still_active,
      "B admin A ning adminini O'CHIRIB QO'YDI")

r = client.post(f"/api/users/{a_user_id}/password",
                json={"new_password": "BuzilganParol1!"})
db.expire_all()
a_user = db.get(User, a_user_id)
took_over = auth.verify_password("BuzilganParol1!", a_user.password_hash) \
    if hasattr(auth, "verify_password") else (r.status_code == 200)
check(f"POST /api/users/A/password  \u2192 {r.status_code}", not took_over,
      "B admin A ning admin PAROLINI ALMASHTIRDI — to'liq egallash")


# ══════════════════════════════════════════════════════════════
section("4. ID-SIZ MARSHRUTLAR: javobda A ning belgisi chiqadimi")
# ══════════════════════════════════════════════════════════════
# 2026-09-21: bu yerda 4 ta sizish topildi (`/trash`, `top-products`,
# `loy-cost`, `loy-stock`). Ular ID qabul qilmaydi, shuning uchun
# yuqoridagi IDOR problari ularni UMUMAN ko'rmaydi — sizish javob
# MATNIDA A ning nomlari paydo bo'lishi bilan bilinadi.
#
# Usul: A ning yozuvlari "AAA" bilan boshlanadi. B sifatida kirilgan
# holda javobda "AAA" uchrasa — sizish.
#
# ⚠ SHABLONLARDA SOXTA MOSLIK BO'LISHI MUMKIN: `/orders` sahifasida
# `#B0AAA0` CSS rangi bor va u "AAA" ni o'z ichiga oladi. Shuning uchun
# bu yerda faqat JSON qaytaradigan marshrutlar va `/trash` sinaladi.
import services as _services                              # noqa: E402

with contextlib.redirect_stdout(_quiet):
    # `top-products` faqat YAKUNLANGAN buyurtmalarni ko'rsatadi.
    _services.complete_order(db, A["order"][N_SPARE - 1].id, None)

NOID = [
    ("/trash",                     "audit jurnali"),
    ("/api/reports/top-products",  "eng ko'p sotilgan mahsulotlar"),
    ("/api/loy-cost",              "loy tan narxi"),
    ("/api/loy-stock",             "loy zaxirasi"),
    ("/api/reports/top-materials", "eng ko'p ishlatilgan materiallar"),
    ("/api/reports/top-customers", "eng yirik mijozlar"),
    ("/api/reports/top-suppliers", "eng yirik ta'minotchilar"),
]
for url, label in NOID:
    r = client.get(url, params={"year": 2026, "month": 9})
    body = str(r.text)
    if r.status_code == 404:
        continue          # bunday marshrut yo'q
    pos = body.find("AAA")
    check(f"GET {url}  ({label})  \u2192 {r.status_code}", pos < 0,
          "A NING MA'LUMOTI CHIQDI: ..." + body[max(0, pos - 50):pos + 50] + "...")


# ══════════════════════════════════════════════════════════════
section("5. OPERATSION O'QISH: filtr holati to'g'ri ko'rsatiladimi")
# ══════════════════════════════════════════════════════════════
# 2026-09-21: Railway sozlamalarida o'zgaruvchining BORLIGI uning
# qiymati "1" ekanini isbotlamaydi — qiymat u yerda yashirin ko'rinadi.
# Shuning uchun `/api/system/health-check` filtr holatini qaytaradi.
# Bu qulf o'sha o'qish HAQIQATAN muhit o'zgaruvchisiga mos kelishini
# tekshiradi — aks holda u yolg'on xotirjamlik beradi.
_hc = client.get("/api/system/health-check")
check(f"GET /api/system/health-check \u2192 {_hc.status_code}",
      _hc.status_code == 200, "o'qish ishlamadi")
if _hc.status_code == 200:
    _tf = _hc.json().get("tenant_filter") or {}
    check(f"tenant_filter.enabled == {_tc.ENABLED}",
          _tf.get("enabled") is _tc.ENABLED,
          f"ko'rsatilgan: {_tf.get('enabled')}, amalda: {_tc.ENABLED}")
    check("tenant_filter.stats mavjud", isinstance(_tf.get("stats"), dict),
          f"stats yo'q: {_tf}")
    if _tc.ENABLED:
        check("filtr AMALDA ishlagan (filtered > 0)",
              (_tf.get("stats") or {}).get("filtered", 0) > 0,
              "filtr yoqilgan, lekin birorta so'rovga qo'llanmagan")


# ══════════════════════════════════════════════════════════════
section("6. BODY ICHIDAGI ID: POST /api/orders + A ning project_id si")
# ══════════════════════════════════════════════════════════════
# 2026-09-21 (11-sizish, O'LCHANGAN). Buyurtmaning korxonasi LOYIHADAN
# olinadi. Marshrut loyiha kimnikiligini tekshirmasdi: B A ning
# `project_id` sini bersa, buyurtma A korxonasida yaratilardi va A ning
# penoplasti bilan — A omboridan ayirilardi (TENANT_FILTER=0 da; filtr
# yoniq bo'lsa loyiha qidiruvi 404 berardi). Model qo'riqchisi ushlamasdi:
# buyurtma, detal, penoplast — hammasi bir korxonaniki (A) edi.
# Qo'shimcha: 8 soniyalik "dublikat" himoyasi loyiha tekshiruvidan OLDIN
# ishlardi — B ga A ning yangi buyurtmasi narxlari bilan qaytib ketardi.
from models import OrderItem as _OI6                # noqa: E402

A_PEN6 = Inventory(company_id=1, item_name="AAA_PENO6", unit="blok",
                   stock_quantity=100.0, price_per_unit=200000,
                   volume_per_unit=1.0)
B_PEN6 = Inventory(company_id=2, item_name="BBB_PENO6", unit="blok",
                   stock_quantity=1.0, price_per_unit=200000,
                   volume_per_unit=1.0)
db.add_all([A_PEN6, B_PEN6])
db.commit()
A_PROJ6 = a_id("project")
B_PROJ6 = B["project"][-1].id


def _counts6():
    db.expire_all()
    return (db.query(Order).count(), db.query(_OI6).count(),
            db.query(Order).filter(Order.project_id == A_PROJ6).count(),
            round(float(db.get(Inventory, A_PEN6.id).stock_quantity), 6))


_n6 = [0]


def _body6(project_id, **item):
    _n6[0] += 1
    it = {"name": f"BBB_D6_{_n6[0]}", "category": "panel", "width": 50,
          "thickness": 10, "quantity": 2, "unit_price": 1000,
          "is_coated": False}
    it.update(item)
    return {"project_id": project_id, "order_type": "product", "items": [it]}


for lbl, body, qs in [
    ("oddiy detal", _body6(A_PROJ6), "?confirm_shortage=true"),
    ("+ A penoplasti", _body6(A_PROJ6, penoplast_id=A_PEN6.id), "?confirm_shortage=true"),
    ("+ A penoplasti + loy_kg", _body6(A_PROJ6, penoplast_id=A_PEN6.id),
     "?confirm_shortage=true&loy_kg=20"),
]:
    c0 = _counts6()
    r = client.post("/api/orders" + qs, json=body)
    c1 = _counts6()
    check(f"POST /api/orders (A loyihasi, {lbl}) \u2192 {r.status_code}",
          r.status_code == 404, ("YUK NOTO'G'RI: " if r.status_code == 422
                                 else "SIZISH: ") + r.text[:120])
    check(f"  \u21b3 yangi buyurtma/detal YO'Q, A penoplasti O'ZGARMADI ({lbl})",
          c0 == c1, f"{c0} -> {c1}")

# 6d. Yetishmovchilik bor yuk (B da 1 blok, so'ralgani ko'p) — begona
# loyiha AYNAN 404 berishi shart, 409 "yetishmaydi" emas. Bu marshrut
# qatlamidagi tekshiruv yetishmovchilik hisobidan OLDIN turganini qulflaydi.
r = client.post("/api/orders", json=_body6(A_PROJ6, penoplast_id=B_PEN6.id,
                                          quantity=500, width=100,
                                          thickness=100))
check(f"POST /api/orders (A loyihasi, yetishmovchilik yuki) \u2192 {r.status_code} (404 shart)",
      r.status_code == 404, r.text[:140])

# 6c. "Dublikat" orqali o'qish: A hozirgina buyurtma yaratdi, B xuddi
# shu tarkibni A loyihasiga yuboradi.
_dup_items = [schemas.OrderItemCreate(name="AAA_DUP6", category="panel",
                                      quantity=3, unit_price=123457)]
with contextlib.redirect_stdout(_quiet):
    crud.create_order(db, schemas.OrderCreate(
        project_id=A_PROJ6, order_type="product", items=_dup_items),
        performed_by="AAA")
c0 = _counts6()
r = client.post("/api/orders?confirm_shortage=true", json={
    "project_id": A_PROJ6, "order_type": "product",
    "items": [{"name": "AAA_DUP6", "category": "panel", "quantity": 3,
               "unit_price": 1}]})
check(f"POST /api/orders (A ning yangi buyurtmasi dublikati) \u2192 {r.status_code}",
      r.status_code == 404 and "AAA" not in r.text and "123457" not in r.text,
      "A BUYURTMASI QAYTDI: " + r.text[:140])
check("  \u21b3 dublikat urinishi hech narsa yaratmadi", c0 == _counts6())

# 6e. Ildiz: crud.create_order korxona berilsa — begona loyihani rad etadi.
# (Eski imzoda `company_id` yo'q — TypeError ham "himoya yo'q" hisoblanadi,
# skript qulamaydi.)
c0 = _counts6()
_root = "yo'q"
try:
    with contextlib.redirect_stdout(_quiet):
        crud.create_order(db, schemas.OrderCreate(
            project_id=A_PROJ6, order_type="product",
            items=[schemas.OrderItemCreate(name="BBB_ROOT6", category="panel",
                                           quantity=1, unit_price=1)]),
            company_id=2)
    _root = "YARATILDI"
except TypeError as e:
    _root = f"imzo: {e}"
except Exception as e:                               # noqa: BLE001
    _root = f"{type(e).__name__}:{getattr(e, 'status_code', '')}"
db.rollback()
check("crud.create_order(company_id=2, A loyihasi) \u2192 HTTPException 404",
      _root == "HTTPException:404", _root)
check("  \u21b3 ildiz rad etishi hech narsa yaratmadi", c0 == _counts6(),
      f"{c0} -> {_counts6()}")

# 6e2. Ildizda tartib: A ning yangi buyurtmasi bilan bir xil tarkib —
# crud qatlami ham A buyurtmasini "dublikat" sifatida QAYTARMASLIGI shart
# (tekshiruv takroriy-yuborish himoyasidan OLDIN).
with contextlib.redirect_stdout(_quiet):
    crud.create_order(db, schemas.OrderCreate(
        project_id=A_PROJ6, order_type="product",
        items=[schemas.OrderItemCreate(name="AAA_DUP6B", category="panel",
                                       quantity=4, unit_price=1)]),
        performed_by="AAA")
_root2 = "yo'q"
try:
    with contextlib.redirect_stdout(_quiet):
        _ro = crud.create_order(db, schemas.OrderCreate(
            project_id=A_PROJ6, order_type="product",
            items=[schemas.OrderItemCreate(name="AAA_DUP6B", category="panel",
                                           quantity=4, unit_price=1)]),
            company_id=2)
    _root2 = f"QAYTDI: {getattr(_ro, 'order_number', _ro)}"
except TypeError as e:
    _root2 = f"imzo: {e}"
except Exception as e:                               # noqa: BLE001
    _root2 = f"{type(e).__name__}:{getattr(e, 'status_code', '')}"
db.rollback()
check("crud.create_order(company_id=2) A dublikatini QAYTARMAYDI \u2192 404",
      _root2 == "HTTPException:404", _root2)

# 6e3. Ulanish: marshrut ildizga korxonani UZATADI (ikkinchi qatlam
# o'lik bo'lib qolmasin — HTTP buni ko'rmaydi, marshrut qatlami yopadi).
import inspect as _insp6                            # noqa: E402
import re as _re6                                   # noqa: E402
_src6 = _insp6.getsource(main.api_create_order)
check("api_create_order: crud.create_order(..., company_id=auth.company_id_of(current_user))",
      bool(_re6.search(r"crud\.create_order\(\s*db\s*,\s*order\s*,\s*company_id\s*=\s*"
                       r"auth\.company_id_of\(current_user\)", _src6)),
      "ildizga korxona uzatilmaydi")

# 6f. Nazorat: B O'Z loyihasiga — o'tadi (404 umumiy rad etish emas).
r = client.post("/api/orders?confirm_shortage=true", json=_body6(B_PROJ6))
check(f"POST /api/orders (B O'Z loyihasi) \u2192 {r.status_code} (200 shart)",
      r.status_code == 200, r.text[:140])


# ══════════════════════════════════════════════════════════════
section("7. BODY ICHIDAGI ID (12-sizish): retsept / kirim / qaytarish / usta TG")
# ══════════════════════════════════════════════════════════════
# 2026-09-21 — O'LCHANGAN (body ID supurishi, 58 prob, DB-diff bilan):
#  S1 POST/PUT /api/recipes + A ning inventory_id → B retsepti A
#     materialiga bog'lanardi; B loy ishlab chiqarganda A ombori 100→98.
#     ILDIZ: qo'riqchida `RecipeIngredient` qoidasi O'LIK edi (company_id
#     ustuni yo'q + _TENANT_RULES da ota yo'q → _check_refs chiqib ketardi).
#     Filtr YONIQ bo'lsa ham ochiq edi.
#  S2 POST /api/inventory/receipt + A ning inventory_id → A ombori 100→101.
#  S3 POST /api/returns (B buyurtmasi + A ning order_item_id) → brak A
#     penoplastini yechardi, qaytarish summasi A tan narxidan B ga qaytardi.
#  + begona/mavjud bo'lmagan order_id → 500; begona supplier_id → 500;
#    usta PUT dublikat telegram_id → 500 (POST esa filtrga bog'liq edi).
from models import (RecipeIngredient as _RI7, InventoryPurchase as _IP7,   # noqa: E402
                    InventoryMovement as _IM7, ReturnItem as _RT7,
                    Master as _M7, OrderItem as _OI7)
import models as _models7                           # noqa: E402
import production_models as _pm7                    # noqa: E402

A_INV7 = Inventory(company_id=1, item_name="AAA_INV7", unit="kg",
                   stock_quantity=100.0, price_per_unit=1000)
A_INV7b = Inventory(company_id=1, item_name="AAA_INV7B", unit="kg",
                    stock_quantity=100.0, price_per_unit=1000)
A_PEN7 = Inventory(company_id=1, item_name="AAA_PENO7", unit="blok",
                   stock_quantity=100.0, price_per_unit=777777,
                   volume_per_unit=1.0)
B_INV7 = Inventory(company_id=2, item_name="BBB_INV7", unit="kg",
                   stock_quantity=100.0, price_per_unit=1000)
db.add_all([A_INV7, A_INV7b, A_PEN7, B_INV7])
db.commit()
with contextlib.redirect_stdout(_quiet):
    _ao7 = crud.create_order(db, schemas.OrderCreate(
        project_id=a_id("project"), order_type="product",
        items=[schemas.OrderItemCreate(name="AAA_KARNIZ7", category="profil",
                                       width=10, thickness=10, length=100,
                                       quantity=5, unit_price=100000,
                                       is_coated=False,
                                       penoplast_id=A_PEN7.id)]),
        performed_by="AAA")
A_OI7 = db.query(_OI7).filter(_OI7.order_id == _ao7.id).first().id
B_ORD7 = B["order"][-1].id
B_OI7 = db.query(_OI7).filter(_OI7.order_id == B_ORD7).first().id
B_REC7 = B["recipe"][-1].id
_A_INV_IDS7 = (A_INV7.id, A_INV7b.id, A_PEN7.id)


def _a7():
    """A holati + B da begona havola/yarim yozuv borligi."""
    db.expire_all()
    return (
        tuple(round(float(db.get(Inventory, i).stock_quantity), 6) for i in _A_INV_IDS7),
        db.query(_RI7).filter(_RI7.inventory_id.in_(_A_INV_IDS7)).count(),
        db.query(_IP7).filter(_IP7.inventory_id.in_(_A_INV_IDS7)).count(),
        db.query(_IM7).filter(_IM7.inventory_id.in_(_A_INV_IDS7)).count(),
        db.query(_RT7).count(),
        round(float(db.get(Inventory, B_INV7.id).stock_quantity), 6),
    )


def _b_rec_ings7():
    db.expire_all()
    return sorted((r.inventory_id, float(r.quantity_kg)) for r in
                  db.query(_RI7).filter(_RI7.recipe_id == B_REC7).all())


def _root7(fn):
    """Ildiz chaqiruvi: natija matni. TypeError (eski imzo) ham "himoya
    yo'q" hisoblanadi — skript QULAMAYDI."""
    try:
        with contextlib.redirect_stdout(_quiet):
            fn()
        out = "O'TDI"
    except TypeError as e:
        out = f"imzo: {e}"
    except Exception as e:                           # noqa: BLE001
        out = f"{type(e).__name__}:{getattr(e, 'status_code', '')}"
    db.rollback()
    return out


_n7 = [0]


def _nm7(p):
    _n7[0] += 1
    return f"BBB_{p}7_{_n7[0]}"


class _Resp7:
    """Server istisnosi → 500 (asl kodda istisno TestClient dan chiqib
    skriptni QULATARDI — darvoza yiqilishi kerak, qulashi emas)."""
    def __init__(self, e):
        self.status_code = 500
        self.text = f"ISTISNO: {type(e).__name__}: {e}"

    def json(self):
        return {}


def _req7(method, url, **kw):
    try:
        return getattr(client, method)(url, **kw)
    except Exception as e:                           # noqa: BLE001
        db.rollback()
        return _Resp7(e)


# --- 7a. Retsept (S1) ---
c0 = _a7()
r = _req7("post", "/api/recipes", json={"name": _nm7("R"), "batch_size_kg": 10,
                "ingredients": [{"inventory_id": A_INV7.id, "quantity_kg": 1}]})
check(f"POST /api/recipes (tarkibda A materiali) \u2192 {r.status_code} (404 shart)",
      r.status_code == 404, r.text[:140])
check("  \u21b3 A materialiga havola YO'Q, hech narsa o'zgarmadi", c0 == _a7(), f"{c0} -> {_a7()}")

r = _req7("post", "/api/recipes", json={"name": _nm7("R"), "batch_size_kg": 10,
                "ingredients": [{"inventory_id": B_INV7.id, "quantity_kg": 1},
                                {"inventory_id": A_INV7b.id, "quantity_kg": 1}]})
check(f"POST /api/recipes (B + A materiali aralash) \u2192 {r.status_code} (404 shart)",
      r.status_code == 404, r.text[:140])
check("  \u21b3 aralash: A ga havola YO'Q", c0 == _a7(), f"{c0} -> {_a7()}")

ing0 = _b_rec_ings7()
r = _req7("put", f"/api/recipes/{B_REC7}", json={"name": _nm7("RP"), "batch_size_kg": 10,
               "ingredients": [{"inventory_id": A_INV7.id, "quantity_kg": 1}]})
check(f"PUT /api/recipes/B (tarkibda A materiali) \u2192 {r.status_code} (404 shart)",
      r.status_code == 404, r.text[:140])
check("  \u21b3 B retseptining ESKI tarkibi saqlandi (o'chirishdan OLDIN rad etildi)",
      ing0 == _b_rec_ings7() and c0 == _a7(), f"{ing0} -> {_b_rec_ings7()}")

# 7a-ildiz: crud (korxona berilsa — retsept; berilmasa ham — retsept o'z korxonasi)
_o = _root7(lambda: crud.create_recipe(db, schemas.RecipeCreate(
    name=_nm7("RR"), batch_size_kg=10, ingredients=[schemas.RecipeIngredientCreate(
        inventory_id=A_INV7.id, quantity_kg=1)]), company_id=2))
check("crud.create_recipe(company_id=2, A materiali) \u2192 HTTPException 404",
      _o == "HTTPException:404", _o)
_o = _root7(lambda: crud.update_recipe(db, B_REC7, schemas.RecipeCreate(
    name=_nm7("RU"), batch_size_kg=10, ingredients=[schemas.RecipeIngredientCreate(
        inventory_id=A_INV7.id, quantity_kg=1)])))
check("crud.update_recipe(B retsepti, A materiali, company_id BERILMAGAN) \u2192 404",
      _o == "HTTPException:404", _o)
check("  \u21b3 ildiz rad etishlari hech narsa yozmadi",
      ing0 == _b_rec_ings7() and c0 == _a7(), f"{c0} -> {_a7()}")

# 7a-qo'riqchi: marshrut va crud chetlab o'tilsa ham (ORM to'g'ridan-to'g'ri)
_g = "yo'q"
try:
    db.add(_RI7(recipe_id=B_REC7, inventory_id=A_INV7.id, quantity_kg=1))
    db.commit()
    _g = "YOZILDI"
except _models7.TenantMismatchError:
    _g = "TenantMismatchError"
except Exception as e:                               # noqa: BLE001
    _g = type(e).__name__
db.rollback()
check("Qo'riqchi: RecipeIngredient(B retsepti \u2192 A materiali) \u2192 TenantMismatchError",
      _g == "TenantMismatchError", _g)

# 7a-statik: _TENANT_REFS dagi HAR qoida TIRIK bo'lsin — modelda company_id
# bo'lsin yoki _TENANT_RULES da ota bo'lsin. Aks holda _check_refs own_cid=None
# bilan chiqib ketadi (S1 aynan shunday edi).
_olik = []
for _nom in _models7._TENANT_REFS:
    _cls = getattr(_models7, _nom, None) or getattr(_pm7, _nom, None)
    _has = _cls is not None and "company_id" in {c.key for c in _cls.__table__.columns}
    if not (_has or _nom in _models7._TENANT_RULES):
        _olik.append(_nom)
check(f"_TENANT_REFS: o'lik qoida yo'q ({len(_models7._TENANT_REFS)} ta model)",
      not _olik, f"O'LIK: {_olik}")

# --- 7b. Ombor kirimi (S2) ---
c0 = _a7()
r = _req7("post", "/api/inventory/receipt", json={"items": [
    {"inventory_id": A_INV7.id, "quantity": 1, "price_per_unit": 1000}]})
check(f"POST /api/inventory/receipt (A materiali) \u2192 {r.status_code} (404 shart)",
      r.status_code == 404, r.text[:140])
check("  \u21b3 A ombori O'ZGARMADI, xarid/harakat YO'Q", c0 == _a7(), f"{c0} -> {_a7()}")
r = _req7("post", "/api/inventory/receipt", json={"items": [
    {"inventory_id": B_INV7.id, "quantity": 1, "price_per_unit": 1000},
    {"inventory_id": A_INV7.id, "quantity": 1, "price_per_unit": 1000}]})
check(f"POST /api/inventory/receipt (B + A aralash) \u2192 {r.status_code} (404 shart)",
      r.status_code == 404, r.text[:140])
check("  \u21b3 aralash: B ombori ham O'ZGARMADI (yarim kirim yo'q)", c0 == _a7(), f"{c0} -> {_a7()}")
_A_SUP7 = crud.create_supplier(db, schemas.SupplierCreate(name="AAA_SUP7"), company_id=1) \
    if "company_id" in _insp6.signature(crud.create_supplier).parameters else None
if _A_SUP7 is not None:
    r = _req7("post", "/api/inventory/receipt", json={"supplier_id": _A_SUP7.id, "items": [
        {"inventory_id": B_INV7.id, "quantity": 1, "price_per_unit": 1000}]})
    check(f"POST /api/inventory/receipt (A ta'minotchisi) \u2192 {r.status_code} (404 shart, 500 emas)",
          r.status_code == 404 and "company_id" not in r.text, r.text[:140])
    check("  \u21b3 ta'minotchi: B ombori O'ZGARMADI", c0 == _a7(), f"{c0} -> {_a7()}")
_o = _root7(lambda: crud.create_inventory_receipt(
    db, items=[{"inventory_id": A_INV7.id, "quantity": 1, "price_per_unit": 1000}],
    created_by="BBB", company_id=2))
check("crud.create_inventory_receipt(company_id=2, A materiali) \u2192 rad (ValueError)",
      _o.startswith("ValueError"), _o)
check("  \u21b3 ildiz: A ombori O'ZGARMADI", c0 == _a7(), f"{c0} -> {_a7()}")

# --- 7c. Qaytarish (S3) ---
c0 = _a7()
for _rs in ("Brak", "Ortiqcha"):
    r = _req7("post", "/api/returns", json={"order_id": B_ORD7, "order_item_id": A_OI7,
                    "item_name": "x", "quantity": 1, "reason": _rs})
    check(f"POST /api/returns (B buyurtmasi + A detali, {_rs}) \u2192 {r.status_code} (404 shart)",
          r.status_code == 404 and "777777" not in r.text, r.text[:140])
    check(f"  \u21b3 A penoplasti O'ZGARMADI, qaytarish yozuvi YO'Q ({_rs})",
          c0 == _a7(), f"{c0} -> {_a7()}")
r = _req7("post", "/api/returns", json={"order_id": _ao7.id, "item_name": "x",
                "quantity": 1, "reason": "Brak"})
check(f"POST /api/returns (A buyurtmasi) \u2192 {r.status_code} (404 shart, 500 emas)",
      r.status_code == 404, r.text[:140])
r = _req7("post", "/api/returns", json={"order_id": 99999999, "item_name": "x",
                "quantity": 1, "reason": "Brak"})
check(f"POST /api/returns (mavjud bo'lmagan buyurtma) \u2192 {r.status_code} (404 shart, 500 emas)",
      r.status_code == 404, r.text[:140])
check("  \u21b3 hech narsa yozilmadi", c0 == _a7(), f"{c0} -> {_a7()}")
for _cid7 in (2, None):
    _o = _root7(lambda: crud.create_return_item(db, schemas.ReturnItemCreate(
        order_id=B_ORD7, order_item_id=A_OI7, item_name="x", quantity=1,
        reason="Brak"), company_id=_cid7))
    check(f"crud.create_return_item(company_id={_cid7}, B buyurtmasi + A detali) \u2192 rad",
          _o.startswith("ValueError"), _o)
check("  \u21b3 ildiz: A penoplasti O'ZGARMADI", c0 == _a7(), f"{c0} -> {_a7()}")

# --- 7d. Usta Telegram ID: POST va PUT BIR XIL qoida, filtrga bog'liq emas ---
with contextlib.redirect_stdout(_quiet):
    crud.create_master(db, schemas.MasterCreate(name="AAA_Usta7", phone="+998907770001",
                                                telegram_id="7707001"), company_id=1)
r = _req7("post", "/api/masters", json={"name": "BBB_Usta7a", "phone": "+998907770002",
                                     "telegram_id": "7707001"})
check(f"POST /api/masters (boshqa korxonadagi TG ID) \u2192 {r.status_code} (200: bir usta 2 korxonada)",
      r.status_code == 200, r.text[:140])
r2 = _req7("post", "/api/masters", json={"name": "BBB_Usta7b", "phone": "+998907770003",
                                      "telegram_id": "7707001"})
check(f"POST /api/masters (O'Z korxonasida band TG ID) \u2192 {r2.status_code} (400 shart)",
      r2.status_code == 400, r2.text[:140])
r3 = _req7("post", "/api/masters", json={"name": "BBB_Usta7c", "phone": "+998907770004"})
_bm7 = r3.json().get("id") if r3.status_code == 200 else None
r = _req7("put", f"/api/masters/{_bm7}", json={"name": "BBB_Usta7c", "phone": "+998907770004",
                                            "telegram_id": "7707001"})
check(f"PUT /api/masters/B (O'Z korxonasida band TG ID) \u2192 {r.status_code} (400 shart, 500 emas)",
      r.status_code == 400, r.text[:140])
db.expire_all()
check("  \u21b3 A ustasining TG ID si o'zgarmadi, B da dublikat YO'Q",
      db.query(_M7).filter(_M7.telegram_id == "7707001", _M7.company_id == 1).count() == 1
      and db.query(_M7).filter(_M7.telegram_id == "7707001", _M7.company_id == 2).count() == 1)

# --- 7e. Nazorat: B o'z ID lari bilan — o'tadi (404 umumiy rad etish emas) ---
r = _req7("post", "/api/recipes", json={"name": _nm7("RN"), "batch_size_kg": 10,
                "ingredients": [{"inventory_id": B_INV7.id, "quantity_kg": 1}]})
check(f"nazorat: POST /api/recipes (B materiali) \u2192 {r.status_code} (200 shart)",
      r.status_code == 200, r.text[:140])
r = _req7("put", f"/api/recipes/{B_REC7}", json={"name": _nm7("RNP"), "batch_size_kg": 10,
               "ingredients": [{"inventory_id": B_INV7.id, "quantity_kg": 2}]})
check(f"nazorat: PUT /api/recipes/B (B materiali) \u2192 {r.status_code} (200 shart)",
      r.status_code == 200, r.text[:140])
r = _req7("post", "/api/inventory/receipt", json={"items": [
    {"inventory_id": B_INV7.id, "quantity": 1, "price_per_unit": 1000}]})
check(f"nazorat: POST /api/inventory/receipt (B materiali) \u2192 {r.status_code} (200 shart)",
      r.status_code == 200, r.text[:140])
r = _req7("post", "/api/returns", json={"order_id": B_ORD7, "order_item_id": B_OI7,
                "item_name": "x", "quantity": 1, "reason": "Ortiqcha"})
check(f"nazorat: POST /api/returns (B buyurtmasi + B detali) \u2192 {r.status_code} (200 shart)",
      r.status_code == 200, r.text[:140])


# ══════════════════════════════════════════════════════════════
section("8. PUT /api/order-items/{id} — tanadagi kalitlar (13-sizish)")
# ══════════════════════════════════════════════════════════════
# 2026-09-21 — O'LCHANGAN (asl kod): tana `setattr` bilan tekshiruvsiz
# yozilardi. `company_id` + `order_id` + `penoplast_id` BIRGA A niki qilib
# yuborilsa → 200: B detali A buyurtmasiga ko'chardi (filtr o'chiq: A
# penoplasti 100→99.5, A da ombor harakati; filtr yoniq: A buyurtmasiga
# begona detal). `id` o'zgarardi, `sub_details` omborsiz o'chardi,
# `order`/`delivered_qty` → 500. Endi faqat ruxsat etilgan maydonlar.
B_PEN8 = Inventory(company_id=2, item_name="BBB_PENO8", unit="blok",
                   stock_quantity=100.0, price_per_unit=1000, volume_per_unit=1.0)
B_PEN8b = Inventory(company_id=2, item_name="BBB_PENO8b", unit="blok",
                    stock_quantity=100.0, price_per_unit=2000, volume_per_unit=1.0)
db.add_all([B_PEN8, B_PEN8b])
db.commit()
B_PEN8_ID, B_PEN8b_ID = B_PEN8.id, B_PEN8b.id
A_ORD8 = _ao7.id
_n8 = [0]


def _b_item8(category="profil", penoplast=True):
    """B korxonada YANGI buyurtma (qoralama emas) va uning detali."""
    _n8[0] += 1
    kw = dict(name=f"BBB_DETAL8_{_n8[0]}", category=category, width=10, thickness=10,
              length=100, quantity=5, unit_price=1000, is_coated=False)
    if penoplast:
        kw["penoplast_id"] = B_PEN8_ID
    with contextlib.redirect_stdout(_quiet):
        o = crud.create_order(db, schemas.OrderCreate(
            project_id=B["project"][-1].id, order_type="product",
            items=[schemas.OrderItemCreate(**kw)]), performed_by="BBB")
    oid = o.id
    return oid, db.query(_OI7).filter(_OI7.order_id == oid).first().id


def _a8():
    """A holati: penoplast qoldig'i, A buyurtmasi detallari soni va summasi,
    A penoplastidagi ombor harakatlari soni."""
    db.expire_all()
    _ao = db.get(Order, A_ORD8)
    return (
        round(float(db.get(Inventory, A_PEN7.id).stock_quantity), 6),
        db.query(_OI7).filter(_OI7.order_id == A_ORD8).count(),
        round(float(_ao.total_amount or 0), 2),
        db.query(_IM7).filter(_IM7.inventory_id == A_PEN7.id).count(),
    )


def _bi8(iid):
    """B detalining bog'lanishlari va asosiy qiymatlari (yo'q bo'lsa None)."""
    db.expire_all()
    it = db.get(_OI7, iid)
    if it is None:
        return None
    return (it.company_id, it.order_id, it.penoplast_id, it.length,
            float(it.quantity or 0), float(it.unit_price or 0), bool(it.is_coated),
            it.name)


def _pen8(i):
    db.expire_all()
    return round(float(db.get(Inventory, i).stock_quantity), 6)


# --- 8a. A ga bog'lash: uchalasi birga, juft va yolg'iz ---
_HUJUM8 = [
    ("company_id + order_id + penoplast_id (A)",
     lambda: {"company_id": 1, "order_id": A_ORD8, "penoplast_id": A_PEN7.id}, 400),
    ("company_id + order_id (A)",
     lambda: {"company_id": 1, "order_id": A_ORD8}, 400),
    ("company_id=1", lambda: {"company_id": 1}, 400),
    ("order_id=A", lambda: {"order_id": A_ORD8}, 400),
    ("penoplast_id=A (yolg'iz)", lambda: {"penoplast_id": A_PEN7.id}, 404),
    ("length + penoplast_id=A", lambda: {"length": 200, "penoplast_id": A_PEN7.id}, 404),
]
for _lbl, _mk, _kut in _HUJUM8:
    _oid, _iid = _b_item8()
    c0, b0 = _a8(), _bi8(_iid)
    r = _req7("put", f"/api/order-items/{_iid}", json=_mk())
    check(f"PUT /api/order-items/B ({_lbl}) \u2192 {r.status_code} ({_kut} shart)",
          r.status_code == _kut and "777777" not in r.text, r.text[:140])
    check(f"  \u21b3 A o'zgarmadi, B detali joyida ({_lbl})",
          c0 == _a8() and b0 == _bi8(_iid), f"{c0} -> {_a8()} | {b0} -> {_bi8(_iid)}")

# --- 8b. Tuzilma maydonlari: id, bog'lanishlar, xossalar ---
for _lbl, _body in (("id = A detali", {"id": A_OI7}),
                    ("id = 99999999", {"id": 99999999}),
                    ("order (bog'lanish)", {"order": 5}),
                    ("sub_details (bog'lanish)", {"sub_details": []}),
                    ("delivered_qty (xossa)", {"delivered_qty": 5}),
                    ("finished_product_id", {"finished_product_id": 1}),
                    ("total_price", {"total_price": 1})):
    _oid, _iid = _b_item8()
    c0, b0 = _a8(), _bi8(_iid)
    r = _req7("put", f"/api/order-items/{_iid}", json=_body)
    check(f"PUT /api/order-items/B ({_lbl}) \u2192 {r.status_code} (400 shart)",
          r.status_code == 400, r.text[:140])
    check(f"  \u21b3 B detali o'z ID sida, o'zgarmagan ({_lbl})",
          b0 is not None and b0 == _bi8(_iid) and c0 == _a8(), f"{b0} -> {_bi8(_iid)}")

# --- 8c. Noto'g'ri qiymatlar → 400 (500 emas, jim yozilmaydi) ---
for _lbl, _body in (("length matn", {"length": "abc"}),
                    ("quantity 0", {"quantity": 0}),
                    ("quantity true", {"quantity": True}),
                    ("unit_price manfiy", {"unit_price": -1}),
                    ("unit_price juda katta", {"unit_price": 1e13}),
                    ("is_coated matn", {"is_coated": "ha"}),
                    ("name bo'sh", {"name": " "}),
                    ("penoplast_id matn", {"penoplast_id": "1"})):
    _oid, _iid = _b_item8()
    b0, p0 = _bi8(_iid), _pen8(B_PEN8_ID)
    r = _req7("put", f"/api/order-items/{_iid}", json=_body)
    check(f"PUT /api/order-items/B ({_lbl}) \u2192 {r.status_code} (400 shart)",
          r.status_code == 400, r.text[:140])
    check(f"  \u21b3 B detali va ombori o'zgarmadi ({_lbl})",
          b0 == _bi8(_iid) and p0 == _pen8(B_PEN8_ID), f"{b0} -> {_bi8(_iid)}")

# --- 8d. Topshirilgandan kam — aniq sabab bilan 400 (avval 404 "topilmadi") ---
_oid, _iid = _b_item8(category="panel", penoplast=False)
r = _req7("post", "/api/deliveries", json={"order_id": _oid,
                                           "items": [{"order_item_id": _iid, "quantity": 3}]})
check(f"tayyorgarlik: POST /api/deliveries (B detali, 3 dona) \u2192 {r.status_code} (200 shart)",
      r.status_code == 200, r.text[:140])
b0 = _bi8(_iid)
r = _req7("put", f"/api/order-items/{_iid}", json={"quantity": 1})
check(f"PUT /api/order-items/B (topshirilgan 3 dan kam: 1) \u2192 {r.status_code} (400 shart)",
      r.status_code == 400 and "Topshirilgan" in r.text, r.text[:140])
check("  \u21b3 B detali o'zgarmadi", b0 == _bi8(_iid), f"{b0} -> {_bi8(_iid)}")

# --- 8e. Ildiz: crud (company_id BERILMAGAN) ham rad etadi ---
_oid, _iid = _b_item8()
c0, b0 = _a8(), _bi8(_iid)
_o = _root7(lambda: crud.update_order_item(
    db, _iid, {"company_id": 1, "order_id": A_ORD8, "penoplast_id": A_PEN7.id}))
check("crud.update_order_item(uchalasi A, company_id berilmagan) \u2192 ValueError",
      _o.startswith("ValueError"), _o)
_o = _root7(lambda: crud.update_order_item(db, _iid, {"penoplast_id": A_PEN7.id}))
check("crud.update_order_item(penoplast_id=A, company_id berilmagan) \u2192 HTTPException 404",
      _o == "HTTPException:404", _o)
check("  \u21b3 ildiz rad etishlari hech narsa yozmadi",
      c0 == _a8() and b0 == _bi8(_iid), f"{c0} -> {_a8()} | {b0} -> {_bi8(_iid)}")

# --- 8f. Statik: ruxsat ro'yxatida bog'lanish/kalit ustuni YO'Q ---
# (penoplast_id bundan mustasno — u alohida QAT'IY tekshiriladi)
_ruxsat8 = getattr(crud, "_ORDER_ITEM_UPDATE_FIELDS", None)
_xavfli8 = sorted(c.key for c in _OI7.__table__.columns
                  if (c.primary_key or c.foreign_keys) and c.key != "penoplast_id"
                  and (_ruxsat8 is None or c.key in _ruxsat8))
check("crud._ORDER_ITEM_UPDATE_FIELDS: id/company_id/FK ustunlari yo'q",
      _ruxsat8 is not None and not _xavfli8, f"ro'yxat={_ruxsat8} xavfli={_xavfli8}")

# --- 8g. Nazorat: B o'z qiymatlari bilan — o'tadi VA haqiqatan yoziladi ---
_oid, _iid = _b_item8()
p0 = _pen8(B_PEN8_ID)
r = _req7("put", f"/api/order-items/{_iid}", json={"length": 150, "name": "BBB_TAHRIR8"})
_b1 = _bi8(_iid)
check(f"nazorat: PUT /api/order-items/B (length 150, nom) \u2192 {r.status_code} (200 shart)",
      r.status_code == 200 and _b1 is not None and _b1[3] == 150 and _b1[7] == "BBB_TAHRIR8",
      f"{r.text[:100]} | {_b1}")
check("  \u21b3 B penoplasti farq bo'yicha kamaydi (ombor to'g'rilandi)",
      _pen8(B_PEN8_ID) < p0, f"{p0} -> {_pen8(B_PEN8_ID)}")
p0, p0b = _pen8(B_PEN8_ID), _pen8(B_PEN8b_ID)
r = _req7("put", f"/api/order-items/{_iid}", json={"penoplast_id": B_PEN8b_ID})
check(f"nazorat: PUT /api/order-items/B (penoplast_id = B ning boshqa materiali) \u2192 {r.status_code} (200 shart)",
      r.status_code == 200 and _bi8(_iid)[2] == B_PEN8b_ID, r.text[:140])
check("  \u21b3 eski material qaytdi, yangisidan yechildi",
      _pen8(B_PEN8_ID) > p0 and _pen8(B_PEN8b_ID) < p0b,
      f"{p0}->{_pen8(B_PEN8_ID)} / {p0b}->{_pen8(B_PEN8b_ID)}")

# --- 8h. Tana qiymatlari: narx, min-stock, sovg'a darajasi (o'z korxonasida) ---
# 2026-09-21 — O'LCHANGAN (asl kod): narx kaliti bo'lmasa narx JIMGINA 0
# ga tushardi; manfiy narx saqlanardi (UI oynasi "-5000" ni o'tkazardi);
# matn → 500; min-stock `true` → 1.0, matn → 500; sovg'a summasi matn /
# nomi son → 500, `1e20` → 200 (PostgreSQL da Numeric(12,2) → 500).
B_INV8 = Inventory(company_id=2, item_name="BBB_NARX8", unit="kg",
                   stock_quantity=10.0, price_per_unit=1234, volume_per_unit=2.0,
                   min_stock=3.0)
db.add(B_INV8)
db.commit()
B_INV8_ID = B_INV8.id


def _inv8():
    db.expire_all()
    i = db.get(Inventory, B_INV8_ID)
    return (round(float(i.price_per_unit or 0), 2), float(i.volume_per_unit or 0),
            float(i.min_stock or 0))


for _lbl, _body in (("bo'sh tana — narx 0 ga tushmasin", {}),
                    ("faqat volume_per_unit", {"volume_per_unit": 3}),
                    ("narx manfiy", {"price_per_unit": -5000}),
                    ("narx matn", {"price_per_unit": "abc"}),
                    ("narx true", {"price_per_unit": True}),
                    ("narx juda katta", {"price_per_unit": 1e20}),
                    ("volume_per_unit 0", {"price_per_unit": 100, "volume_per_unit": 0}),
                    ("volume_per_unit matn", {"price_per_unit": 100, "volume_per_unit": "x"})):
    i0 = _inv8()
    r = _req7("post", f"/api/inventory/{B_INV8_ID}/price", json=_body)
    check(f"POST /api/inventory/B/price ({_lbl}) \u2192 {r.status_code} (400 shart)",
          r.status_code == 400, r.text[:140])
    check(f"  \u21b3 narx/hajm o'zgarmadi ({_lbl})", i0 == _inv8(), f"{i0} -> {_inv8()}")

for _lbl, _body in (("matn", {"min_stock": "abc"}), ("true", {"min_stock": True}),
                    ("manfiy", {"min_stock": -1}), ("yo'q", {})):
    i0 = _inv8()
    r = _req7("post", f"/api/inventory/{B_INV8_ID}/min-stock", json=_body)
    check(f"POST /api/inventory/B/min-stock ({_lbl}) \u2192 {r.status_code} (400 shart)",
          r.status_code == 400, r.text[:140])
    check(f"  \u21b3 min-stock o'zgarmadi ({_lbl})", i0 == _inv8(), f"{i0} -> {_inv8()}")

r = _req7("post", f"/api/inventory/{B_INV8_ID}/price", json={"price_per_unit": 0})
check(f"nazorat: POST /api/inventory/B/price (0 — ruxsat) \u2192 {r.status_code} (200 shart)",
      r.status_code == 200 and _inv8()[0] == 0.0, f"{r.text[:100]} | {_inv8()}")
r = _req7("post", f"/api/inventory/{B_INV8_ID}/price",
          json={"price_per_unit": 1500.5, "volume_per_unit": 2.5})
check(f"nazorat: POST /api/inventory/B/price (1500.5, hajm 2.5) \u2192 {r.status_code} (200 shart)",
      r.status_code == 200 and _inv8()[:2] == (1500.5, 2.5), f"{r.text[:100]} | {_inv8()}")
r = _req7("post", f"/api/inventory/{B_INV8_ID}/min-stock", json={"min_stock": 7.5})
check(f"nazorat: POST /api/inventory/B/min-stock (7.5) \u2192 {r.status_code} (200 shart)",
      r.status_code == 200 and _inv8()[2] == 7.5, f"{r.text[:100]} | {_inv8()}")

# Sovg'a darajasi: B ning faol davri (yo'q bo'lsa — ochiladi)
if crud.get_active_gift_period(db, 2) is None:
    r = _req7("post", "/api/gift-period/open",
              json={"tiers": [{"gift_name": "BBB_SOVGA8", "threshold_amount": 1000000}]})
    check(f"tayyorgarlik: POST /api/gift-period/open (B) \u2192 {r.status_code} (200 shart)",
          r.status_code == 200, r.text[:140])
_gp8 = crud.get_active_gift_period(db, 2)
_GT8 = _models7.GiftPeriodTier
_t8 = db.query(_GT8).filter(_GT8.period_id == _gp8.id).first() if _gp8 else None
check("tayyorgarlik: B da faol davr va bosqich bor", _t8 is not None)
_T8_ID = _t8.id if _t8 is not None else 0


def _tier8():
    db.expire_all()
    t = db.get(_GT8, _T8_ID)
    return (t.gift_name, round(float(t.threshold_amount), 2)) if t is not None else None


for _lbl, _body in (("summa matn", {"gift_name": "X8", "threshold_amount": "abc"}),
                    ("nom son", {"gift_name": 5, "threshold_amount": 100}),
                    ("summa juda katta", {"gift_name": "X8", "threshold_amount": 1e20}),
                    ("summa true", {"gift_name": "X8", "threshold_amount": True}),
                    ("summa manfiy", {"gift_name": "X8", "threshold_amount": -10})):
    t0 = _tier8()
    r = _req7("put", f"/api/gift-period/tier/{_T8_ID}", json=_body)
    check(f"PUT /api/gift-period/tier/B ({_lbl}) \u2192 {r.status_code} (400 shart)",
          r.status_code == 400, r.text[:140])
    check(f"  \u21b3 bosqich o'zgarmadi ({_lbl})", t0 == _tier8(), f"{t0} -> {_tier8()}")
r = _req7("put", f"/api/gift-period/tier/{_T8_ID}",
          json={"gift_name": "BBB_SOVGA8_YANGI", "threshold_amount": 2500000})
check(f"nazorat: PUT /api/gift-period/tier/B (to'g'ri qiymat) \u2192 {r.status_code} (200 shart)",
      r.status_code == 200 and _tier8() == ("BBB_SOVGA8_YANGI", 2500000.0),
      f"{r.text[:100]} | {_tier8()}")



# ══════════════════════════════════════════════════════════════
section("9. TAHRIR TANASI (14-band): material / tayyor mahsulot / usta / hodim / loyiha / ta'minotchi")
# ══════════════════════════════════════════════════════════════
# 2026-09-21 — O'LCHANGAN (asl kod, lokal + jonli sinov):
#   `PUT /api/inventory/{id}` manfiy narxni SAQLARDI (jonli: -5000 → 200;
#   13.3 da `/price` yopilgan, bu ikkinchi yo'l ochiq edi), `stock_quantity`
#   to'g'ridan (ombor harakatisiz), hajm 0, `is_default_penoplast`
#   ikkinchi materialga; tayyor mahsulot manfiy miqdor/narx; usta cashback
#   500 %; hodim manfiy oylik, noto'g'ri `pay_type` JIM e'tiborsiz (200);
#   loyiha `total_paid` qo'lda, noto'g'ri `status` (SQLite da qator yozilib
#   BUTUN loyihalar ro'yxati 500); ta'minotchi `null` nom → 500.
# Pydantic `true` → 1.0, "5000" → 5000 ni JIM o'girardi — shuning uchun
# tanalar XOM JSON matni sifatida ham yuboriladi (NaN / Infinity ham).
# Har prob: status + qatorning XOM SQL nusxasi (ORM emas — asl kod o'qib
# bo'lmaydigan enum yozishi mumkin) oldin/keyin. Asl kodda qator o'zgarsa,
# keyingi prob mustaqil bo'lishi uchun SQL bilan tiklanadi.
from sqlalchemy import text as _text9                    # noqa: E402
from models import (FinishedProduct as _FP9, Master as _MS9,     # noqa: E402
                    Employee as _EM9, Project as _PR9, Supplier as _SP9,
                    InventoryMovement as _IMV9,
                    EmployeeCompensationHistory as _ECH9)

with contextlib.redirect_stdout(_quiet):
    B_INV9 = crud.add_item(db, schemas.InventoryCreate(
        item_name="BBB_INV9", unit="kg", stock_quantity=50, price_per_unit=1000),
        company_id=2).id
    _bdef9 = db.query(Inventory).filter(Inventory.company_id == 2,
                                        Inventory.is_default_penoplast == True).first()  # noqa: E712
    if _bdef9 is None:
        _bdef9 = Inventory(company_id=2, item_name="BBB_PEN9", unit="dona",
                           stock_quantity=10.0, price_per_unit=1000, volume_per_unit=1.4,
                           is_penoplast=True, is_default_penoplast=True)
        db.add(_bdef9)
        db.commit()
    B_DEF9 = _bdef9.id
    _fpb = _FP9(company_id=2, name="BBB_FP9", category="profil", quantity=10,
                produced_quantity=10, unit="metr", unit_price=5000, cost_price=1000)
    _fpa = _FP9(company_id=1, name="AAA_FP9", category="profil", quantity=10,
                produced_quantity=10, unit="metr", unit_price=5000, cost_price=1000)
    db.add_all([_fpb, _fpa])
    db.commit()
    B_FP9, A_FP9 = _fpb.id, _fpa.id
    B_M9 = crud.create_master(db, schemas.MasterCreate(
        name="BBB_USTA9", phone="+998901119999"), company_id=2).id
    A_M9 = crud.create_master(db, schemas.MasterCreate(
        name="AAA_USTA9", phone="+998901118888"), company_id=1).id
    B_E9 = crud.create_employee(db, schemas.EmployeeCreate(
        name="BBB_HODIM9", pay_type="fixed", fixed_amount=1000000), company_id=2).id
    A_E9 = crud.create_employee(db, schemas.EmployeeCreate(
        name="AAA_HODIM9", pay_type="fixed", fixed_amount=1000000), company_id=1).id
    B_P9 = crud.create_project(db, schemas.ProjectCreate(
        project_name="BBB_L9", client_name="BBB_MIJOZ9"), company_id=2).id
    A_P9 = crud.create_project(db, schemas.ProjectCreate(
        project_name="AAA_L9", client_name="AAA_MIJOZ9"), company_id=1).id
    B_S9 = crud.create_supplier(db, schemas.SupplierCreate(name="BBB_TAM9"), company_id=2).id
    A_S9 = crud.create_supplier(db, schemas.SupplierCreate(name="AAA_TAM9"), company_id=1).id
    A_INV9 = crud.add_item(db, schemas.InventoryCreate(
        item_name="AAA_INV9", unit="kg", stock_quantity=50, price_per_unit=1000),
        company_id=1).id

_TAB9 = {"inv": Inventory.__tablename__, "fp": _FP9.__tablename__,
         "ms": _MS9.__tablename__, "em": _EM9.__tablename__,
         "pr": _PR9.__tablename__, "sp": _SP9.__tablename__}


def _raw9(kind, oid):
    """Qatorning XOM nusxasi (ORM emas — noto'g'ri enum ham o'qiladi)."""
    db.rollback()
    row = db.execute(_text9(f"SELECT * FROM {_TAB9[kind]} WHERE id = :i"), {"i": oid}).mappings().first()
    return dict(row) if row is not None else None


def _restore9(kind, oid, snap):
    """Asl kod qatorni o'zgartirgan bo'lsa — SQL bilan tiklash."""
    db.rollback()
    cols = [k for k in snap if k != "id"]
    db.execute(_text9(f"UPDATE {_TAB9[kind]} SET " + ", ".join(f"{c} = :{c}" for c in cols)
                      + " WHERE id = :id"), snap)
    db.commit()
    db.expire_all()


def _extra9(kind, oid):
    """Qatordan tashqari kuzatiladigan hisob yozuvlari."""
    db.rollback()
    if kind == "inv":
        return db.query(_IMV9).filter(_IMV9.inventory_id == oid).count()
    if kind == "em":
        return db.query(_ECH9).filter(_ECH9.employee_id == oid).count()
    return None


def _put9(url, body):
    if isinstance(body, str):
        return _req7("put", url, content=body, headers={"Content-Type": "application/json"})
    return _req7("put", url, json=body)


def _bad9(kind, url, oid, cases, extra_get=None):
    """Har holat: 400 SHART + qator va hisob yozuvlari o'zgarmagan."""
    for lbl, body in cases:
        s0, e0 = _raw9(kind, oid), _extra9(kind, oid)
        r = _put9(url, body)
        s1, e1 = _raw9(kind, oid), _extra9(kind, oid)
        check(f"PUT {url.rsplit('/', 1)[0]}/B ({lbl}) \u2192 {r.status_code} (400 shart)",
              r.status_code == 400, r.text[:140])
        ozg = [k for k in s0 if s0[k] != s1.get(k)]
        check(f"  \u21b3 qator va hisob yozuvlari o'zgarmadi ({lbl})",
              not ozg and e0 == e1, f"o'zgardi: {ozg[:4]} {e0}->{e1}")
        if extra_get:
            g = _req7("get", extra_get)
            check(f"  \u21b3 GET {extra_get} \u2192 {g.status_code} (200 shart, ro'yxat buzilmadi) ({lbl})",
                  g.status_code == 200, g.text[:100])
        if ozg:
            _restore9(kind, oid, s0)


# --- 9a. Material: PUT /api/inventory/{id} ---
_bad9("inv", f"/api/inventory/{B_INV9}", B_INV9, [
    ("narx manfiy", {"price_per_unit": -5000}),
    ("narx 1e20", {"price_per_unit": 1e20}),
    ("narx true", {"price_per_unit": True}),
    ("narx matn \"5000\"", {"price_per_unit": "5000"}),
    ("narx NaN", '{"price_per_unit": NaN}'),
    ("hajm 0", {"volume_per_unit": 0}),
    ("hajm manfiy", {"volume_per_unit": -1}),
    ("min qoldiq manfiy", {"min_stock": -3}),
    ("stock_quantity to'g'ridan", {"stock_quantity": 999}),
    ("is_default_penoplast", {"is_default_penoplast": True}),
    ("nom bo'sh", {"item_name": ""}),
    ("nom null", {"item_name": None}),
    ("birlik null", {"unit": None}),
    ("nom 101 belgi", {"item_name": "x" * 101}),
    ("company_id", {"company_id": 1}),
    ("id", {"id": 999999}),
    ("conversion_factor Infinity", '{"conversion_factor": Infinity}'),
    ("is_penoplast \"yes\" (pydantic JIM true qilardi)", {"is_penoplast": "yes"}),
])
_bad9("inv", f"/api/inventory/{B_DEF9}", B_DEF9, [
    ("asosiy penoplast \u2192 is_penoplast false", {"is_penoplast": False}),
])

# --- 9b. Tayyor mahsulot: PUT /api/finished/{id} ---
_bad9("fp", f"/api/finished/{B_FP9}", B_FP9, [
    ("miqdor manfiy", {"quantity": -5}),
    ("miqdor to'g'ridan (20)", {"quantity": 20}),
    ("narx manfiy", {"unit_price": -1}),
    ("narx 1e20", {"unit_price": 1e20}),
    ("narx Infinity", '{"unit_price": Infinity}'),
    ("nom bo'sh", {"name": ""}),
    ("nom null", {"name": None}),
    ("company_id", {"company_id": 1}),
])

# --- 9c. Usta: PUT /api/masters/{id} ---
_bad9("ms", f"/api/masters/{B_M9}", B_M9, [
    ("cashback manfiy", {"cashback_percent": -10}),
    ("cashback 500", {"cashback_percent": 500}),
    ("cashback NaN", '{"cashback_percent": NaN}'),
    ("kpi manfiy", {"kpi_percent": -1}),
    ("ism bo'sh", {"name": ""}),
    ("telefon null", {"phone": None}),
    ("is_active matn", {"is_active": "ha"}),
    ("is_active 0 (pydantic JIM false qilardi)", {"is_active": 0}),
    ("ism 101 belgi", {"name": "x" * 101}),
    ("telegram_id true", {"telegram_id": True}),
])

# --- 9d. Hodim: PUT /api/employees/{id} ---
_bad9("em", f"/api/employees/{B_E9}", B_E9, [
    ("oylik manfiy", {"fixed_amount": -1000000}),
    ("oylik 1e20", {"fixed_amount": 1e20}),
    ("foiz 500", {"percent_value": 500}),
    ("qo'shimcha manfiy", {"extra_monthly": -1}),
    ("pay_type noto'g'ri", {"pay_type": "xato_tur"}),
    ("pay_type null", {"pay_type": None}),
    ("birlik turi noto'g'ri", {"per_unit_type": "kg", "fixed_amount": 5}),
    ("effective_year 1999", {"effective_year": 1999, "fixed_amount": 5}),
    ("effective_month true", {"effective_month": True, "fixed_amount": 5}),
    ("ism bo'sh", {"name": ""}),
])

# --- 9e. Loyiha: PUT /api/projects/{id} ---
_bad9("pr", f"/api/projects/{B_P9}", B_P9, [
    ("total_paid qo'lda", {"total_paid": 100}),
    ("total_paid manfiy", {"total_paid": -100}),
    ("byudjet manfiy", {"total_budget": -5}),
    ("byudjet 1e20", {"total_budget": 1e20}),
    ("status noma'lum", {"status": "yoq_status"}),
    ("status null", {"status": None}),
    ("nom bo'sh", {"project_name": ""}),
    ("mijoz null", {"client_name": None}),
    ("izoh son", {"notes": 123}),
], extra_get="/api/projects")

# --- 9f. Ta'minotchi: PUT /api/suppliers/{id} ---
_bad9("sp", f"/api/suppliers/{B_S9}", B_S9, [
    ("nom bo'sh", {"name": ""}),
    ("nom null", {"name": None}),
    ("nom 151 belgi", {"name": "x" * 151}),
    ("is_active matn", {"is_active": "ha"}),
    ("telefon 21 belgi", {"phone": "1" * 21}),
])

# --- 9g. Begona ID + noto'g'ri tana → 404 (400 emas — ID borligi oshkor bo'lmasin) ---
for _kind9, _url9, _aid9, _body9 in (
        ("inv", "/api/inventory/{}", A_INV9, {"price_per_unit": -1}),
        ("fp", "/api/finished/{}", A_FP9, {"unit_price": -1}),
        ("ms", "/api/masters/{}", A_M9, {"cashback_percent": 500}),
        ("em", "/api/employees/{}", A_E9, {"fixed_amount": -1}),
        ("pr", "/api/projects/{}", A_P9, {"status": "yoq_status"}),
        ("sp", "/api/suppliers/{}", A_S9, {"name": ""})):
    s0 = _raw9(_kind9, _aid9)
    r = _put9(_url9.format(_aid9), _body9)
    s1 = _raw9(_kind9, _aid9)
    check(f"PUT {_url9.format('A')} (begona ID + noto'g'ri tana) \u2192 {r.status_code} (404 shart) va A o'zgarmadi",
          r.status_code == 404 and s0 == s1, f"{r.text[:100]}")
    if s0 != s1:
        _restore9(_kind9, _aid9, s0)


# --- 9h. Ildiz qatlami: crud to'g'ridan (marshrutsiz) → ValueError ---
def _root9(lbl, kind, oid, fn):
    s0 = _raw9(kind, oid)
    try:
        fn()
        natija = "xato chiqmadi"
    except ValueError as e:
        natija = "ValueError" if "ValidationError" not in type(e).__name__ else "pydantic"
    except Exception as e:                           # noqa: BLE001
        natija = f"{type(e).__name__}"
    db.rollback()
    s1 = _raw9(kind, oid)
    check(f"ildiz: {lbl} \u2192 {natija} (ValueError shart) va qator o'zgarmadi",
          natija == "ValueError" and s0 == s1, f"{[k for k in s0 if s0[k] != s1.get(k)][:4]}")
    if s0 != s1:
        _restore9(kind, oid, s0)


_root9("update_item(narx -1)", "inv", B_INV9,
       lambda: crud.update_item(db, B_INV9, schemas.InventoryUpdate(price_per_unit=-1)))
_root9("update_item(stock_quantity 999)", "inv", B_INV9,
       lambda: crud.update_item(db, B_INV9, schemas.InventoryUpdate(stock_quantity=999)))
_root9("update_finished_product(quantity 999)", "fp", B_FP9,
       lambda: crud.update_finished_product(db, B_FP9, {"quantity": 999}, company_id=2))
_root9("update_master(cashback 500)", "ms", B_M9,
       lambda: crud.update_master(db, B_M9, schemas.MasterUpdate(cashback_percent=500), company_id=2))
_root9("update_employee(pay_type xato)", "em", B_E9,
       lambda: crud.update_employee(db, B_E9, schemas.EmployeeUpdate(pay_type="xato_tur")))
_root9("update_project(status noma'lum)", "pr", B_P9,
       lambda: crud.update_project(db, B_P9, {"status": "yoq_status"}))
_root9("update_project(total_paid qo'lda)", "pr", B_P9,
       lambda: crud.update_project(db, B_P9, schemas.ProjectUpdate(total_paid=5)))
_root9("update_supplier(nom bo'sh)", "sp", B_S9,
       lambda: crud.update_supplier(db, B_S9, schemas.SupplierUpdate(name="")))

# --- 9i. Statik: qoida jadvalida bog'lanish (FK) maydoni yo'q, hammasi ustun ---
try:
    _rules9 = crud._upd_rules()
    _taqiq9 = crud._UPD_TAQIQ
    _mod9 = {"Inventory": Inventory, "FinishedProduct": _FP9, "Master": _MS9,
             "Employee": _EM9, "Project": _PR9, "Supplier": _SP9}
    _yomon9 = []
    for _mn9, _r9 in _rules9.items():
        _cols9 = {c.name for c in _mod9[_mn9].__table__.columns}
        for _f9 in _r9:
            if _f9 in ("id", "company_id") or (_f9.endswith("_id") and _f9 != "telegram_id"):
                _yomon9.append(f"{_mn9}.{_f9} (bog'lanish)")
            if _f9 not in _cols9 and not (_mn9 == "Employee" and _f9 in (
                    "effective_year", "effective_month", "reason")):
                _yomon9.append(f"{_mn9}.{_f9} (ustun yo'q)")
        for _t9 in _taqiq9.get(_mn9, {}):
            if _t9 in _r9:
                _yomon9.append(f"{_mn9}.{_t9} (taqiqlangan, lekin ruxsat ro'yxatida)")
    check("statik: ruxsat ro'yxatlarida PK/FK maydoni yo'q, taqiqlanganlar ruxsatda emas",
          not _yomon9 and set(_rules9) == set(_mod9), str(_yomon9[:5]))
except Exception as _e9:                               # noqa: BLE001
    check("statik: ruxsat ro'yxatlarida PK/FK maydoni yo'q, taqiqlanganlar ruxsatda emas",
          False, f"{type(_e9).__name__}: {_e9}")

# --- 9j. Nazorat: interfeys AYNAN yuboradigan tanalar → 200 VA haqiqatan yozildi ---
def _ok9(lbl, kind, oid, url, body, kutilgan):
    r = _put9(url, body)
    s1 = _raw9(kind, oid)
    farq = {k: (s1.get(k), v) for k, v in kutilgan.items() if s1.get(k) != v}
    check(f"nazorat: PUT {url.rsplit('/', 1)[0]}/B ({lbl}) \u2192 {r.status_code} (200 shart) VA yozildi",
          r.status_code == 200 and not farq, f"{r.text[:100]} | {farq}")


_ok9("inventory.html: kategoriya", "inv", B_INV9, f"/api/inventory/{B_INV9}",
     {"category": "Sinov9"}, {"category": "Sinov9"})
_ok9("API: nom + min qoldiq + narx 0 + hajm", "inv", B_INV9, f"/api/inventory/{B_INV9}",
     {"item_name": "BBB_INV9_Y", "min_stock": 5, "price_per_unit": 0, "volume_per_unit": 2.5},
     {"item_name": "BBB_INV9_Y", "min_stock": 5.0, "volume_per_unit": 2.5})
_ok9("finished.html: narx", "fp", B_FP9, f"/api/finished/{B_FP9}",
     {"unit_price": 6500}, {"quantity": 10.0})
check("  \u21b3 tayyor mahsulot narxi 6500 ga yozildi",
      float(_raw9("fp", B_FP9)["unit_price"]) == 6500.0, str(_raw9("fp", B_FP9)["unit_price"]))
_ok9("masters.html: to'liq forma (notes \"\")", "ms", B_M9, f"/api/masters/{B_M9}",
     {"name": "BBB_USTA9_Y", "phone": "+998901119998", "region": None,
      "cashback_percent": 2.5, "notes": "", "telegram_id": None},
     {"name": "BBB_USTA9_Y", "phone": "+998901119998", "cashback_percent": 2.5})
_ok9("masters_manage.html: telefonsiz", "ms", B_M9, f"/api/masters/{B_M9}",
     {"name": "BBB_USTA9_Z", "region": None, "telegram_id": None, "notes": None},
     {"name": "BBB_USTA9_Z", "phone": "+998901119998"})
_ok9("masters_manage.html: faollashtirish", "ms", B_M9, f"/api/masters/{B_M9}",
     {"is_active": True}, {"is_active": 1})
_h0_9 = _extra9("em", B_E9)
_ok9("kpi.html: to'liq forma (to'lov turi o'zgaradi)", "em", B_E9, f"/api/employees/{B_E9}",
     {"name": "BBB_HODIM9_Y", "position": None, "pay_type": "per_unit", "fixed_amount": 0,
      "percent_value": 0, "per_unit_rate": 1500, "per_unit_type": "metr",
      "extra_monthly": None, "production_type": "penoplast", "notes": None,
      "effective_year": 2026, "effective_month": 9, "reason": "sinov9"},
     {"name": "BBB_HODIM9_Y", "pay_type": "PER_UNIT", "per_unit_type": "metr"})
# create_employee joriy oy uchun tarix yozuvini o'zi ochadi; bir oy uchun
# bitta yozuv (dizayn) — shuning uchun 2026-09 yozuvi YANGILANGANI tekshiriladi.
db.rollback()
_hist9 = db.execute(_text9(f"SELECT pay_type, per_unit_rate, reason FROM {_ECH9.__tablename__} "
                           "WHERE employee_id = :e AND effective_year = 2026 AND effective_month = 9"),
                    {"e": B_E9}).mappings().all()
check("  \u21b3 hodim to'lov tarixi (2026-09) yangi to'lov turi va sabab bilan yozildi",
      len(_hist9) == 1 and _hist9[0]["pay_type"] == "PER_UNIT"
      and float(_hist9[0]["per_unit_rate"]) == 1500.0 and _hist9[0]["reason"] == "sinov9",
      f"{[dict(x) for x in _hist9]} | yozuvlar soni {_h0_9} -> {_extra9('em', B_E9)}")
_ok9("projects.html: tahrir formasi", "pr", B_P9, f"/api/projects/{B_P9}",
     {"client_name": "BBB_MIJOZ9_Y", "client_phone": None, "project_name": "BBB_L9_Y",
      "client_address": None, "total_budget": 1500000, "status": "ACTIVE", "notes": None},
     {"project_name": "BBB_L9_Y", "client_name": "BBB_MIJOZ9_Y", "status": "ACTIVE"})
_ok9("projects.html: yakunlash", "pr", B_P9, f"/api/projects/{B_P9}",
     {"status": "COMPLETED"}, {"status": "COMPLETED"})
_ok9("suppliers.html: forma", "sp", B_S9, f"/api/suppliers/{B_S9}",
     {"name": "BBB_TAM9_Y", "phone": None, "notes": None}, {"name": "BBB_TAM9_Y"})

# ══════════════════════════════════════════════════════════════
section("10. YARATISH TANASI (15-band): material / usta / hodim / loyiha / ta'minotchi")
# ══════════════════════════════════════════════════════════════
# 2026-09-21 — O'LCHANGAN (asl kod, lokal TestClient): POST sxemalari
# deyarli cheklovsiz edi — manfiy narx / byudjet / qo'shimcha oylik
# SAQLANARDI; 1e13 / 1e20 (PostgreSQL Numeric(12,2) da 500); Infinity
# SAQLANARDI, NaN yo 500, yo JIM bo'sh qiymat; `true` → 1.0, "5000" → 5000
# JIM; ustun sig'imidan uzun matn (PostgreSQL da 500); bo'shliqdan iborat
# nom / birlik / telefon; noto'g'ri `pay_type` JIMGINA "fixed" (200),
# noto'g'ri `per_unit_type` / `production_type` yozilardi. Funksional:
# usta `kpi_percent` yozilmasdi (7 → 0), loyiha "Muddati" (`deadline`)
# JIMGINA tashlanardi; material qayta yaratilganda (qayta ishlatish yo'li)
# boshlang'ich qoldiq xaridsiz, eski izoh o'chardi, yagona asosiy
# penoplast yo'qolardi. Begona korxonaga sizish YO'Q edi (company_id
# e'tiborsiz) — endi noma'lum kalit 400.
# Har prob: 400 SHART + 7 jadvaldagi qatorlar soni o'zgarmagan (asl kodda
# qator yaratilsa ham keyingi prob mustaqil — soni NISBIY solishtiriladi).
from models import (InventoryPurchase as _IP10, Master as _MS10,          # noqa: E402
                    Employee as _EM10, Project as _PR10, Supplier as _SP10,
                    EmployeeCompensationHistory as _ECH10)

_JAD10 = [Inventory.__tablename__, _IP10.__tablename__, _MS10.__tablename__,
          _EM10.__tablename__, _ECH10.__tablename__, _PR10.__tablename__,
          _SP10.__tablename__]


def _cnt10():
    db.rollback()
    return tuple(db.execute(_text9(f"SELECT COUNT(*) FROM {t}")).scalar() for t in _JAD10)


_n10c = [0]


def _n10(p):
    _n10c[0] += 1
    return f"{p}10_{_n10c[0]:03d}"


def _tel10():
    _n10c[0] += 1
    return f"+99897{_n10c[0]:07d}"


def _post10(url, body):
    if isinstance(body, str):
        return _req7("post", url, content=body, headers={"Content-Type": "application/json"})
    return _req7("post", url, json=body)


def _bad10(url, cases):
    for lbl, body in cases:
        c0 = _cnt10()
        r = _post10(url, body)
        c1 = _cnt10()
        check(f"POST {url} ({lbl}) \u2192 {r.status_code} (400 shart) VA hech narsa yaratilmadi",
              r.status_code == 400 and c0 == c1, f"{r.text[:110]} | {c0} -> {c1}")


def _inv10(**kw):
    b = {"item_name": _n10("BBB_M"), "unit": "kg"}
    b.update(kw)
    return b


def _invraw10(frag):
    return '{"item_name":"%s","unit":"kg",%s}' % (_n10("BBB_M"), frag)


# --- 10a. Material ---
_bad10("/api/inventory", [
    ("narx -5000", _inv10(price_per_unit=-5000)),
    ("narx 1e13 > Numeric(12,2)", _inv10(price_per_unit=1e13)),
    ("narx \"5000\" matn", _inv10(price_per_unit="5000")),
    ("narx true", _inv10(price_per_unit=True)),
    ("narx NaN", _invraw10('"price_per_unit":NaN')),
    ("narx Infinity", _invraw10('"price_per_unit":Infinity')),
    ("qoldiq 1e20", _inv10(stock_quantity=1e20)),
    ("qoldiq true", _inv10(stock_quantity=True)),
    ("qoldiq NaN", _invraw10('"stock_quantity":NaN')),
    ("qoldiq Infinity", _invraw10('"stock_quantity":Infinity')),
    ("min qoldiq NaN", _invraw10('"min_stock":NaN')),
    ("hajm Infinity", _invraw10('"volume_per_unit":Infinity')),
    ("konversiya NaN", _invraw10('"conversion_factor":NaN')),
    ("birlik bo'sh", _inv10(unit="")),
    ("birlik faqat bo'shliq", _inv10(unit="   ")),
    ("birlik 30 belgi", _inv10(unit="x" * 30)),
    ("kategoriya 80 belgi", _inv10(category="c" * 80)),
    ("base_unit 30 belgi", _inv10(base_unit="g" * 30)),
    ("is_penoplast \"yes\"", _inv10(is_penoplast="yes")),
    ("is_penoplast 0", _inv10(is_penoplast=0)),
    ("is_default_penoplast \"yes\"", _inv10(is_default_penoplast="yes")),
    ("nom faqat bo'shliq", {"item_name": "   ", "unit": "kg"}),
    ("nom ' a ' (bo'shliqsiz 1 belgi)", {"item_name": " a ", "unit": "kg"}),
    ("company_id kaliti", _inv10(company_id=1)),
    ("id kaliti", _inv10(id=999999)),
    ("is_deleted kaliti", _inv10(is_deleted=True)),
    ("miqdor x narx > Numeric(12,2)", _inv10(stock_quantity=1e9, price_per_unit=1000)),
    ("birliksiz (majburiy)", {"item_name": _n10("BBB_M")}),
])


# --- 10b. Usta ---
def _ms10(**kw):
    b = {"name": _n10("BBB_U"), "phone": _tel10()}
    b.update(kw)
    return b


def _msraw10(frag):
    return '{"name":"%s","phone":"%s",%s}' % (_n10("BBB_U"), _tel10(), frag)


_bad10("/api/masters", [
    ("cashback true", _ms10(cashback_percent=True)),
    ("cashback \"5\" matn", _ms10(cashback_percent="5")),
    ("cashback NaN", _msraw10('"cashback_percent":NaN')),
    ("cashback 500 %", _ms10(cashback_percent=500)),
    ("kpi NaN", _msraw10('"kpi_percent":NaN')),
    ("kpi -1", _ms10(kpi_percent=-1)),
    ("ism faqat bo'shliq", _ms10(name="   ")),
    ("telefon faqat bo'shliq", {"name": _n10("BBB_U"), "phone": "       "}),
    ("hudud 80 belgi", _ms10(region="r" * 80)),
    ("telegram_id 60 belgi", _ms10(telegram_id="1" * 60)),
    ("is_active kaliti", _ms10(is_active=False)),
    ("company_id kaliti", _ms10(company_id=1)),
    ("telefonsiz (majburiy)", {"name": _n10("BBB_U")}),
])


# --- 10c. Hodim ---
def _em10(**kw):
    b = {"name": _n10("BBB_H"), "pay_type": "fixed", "fixed_amount": 1000}
    b.update(kw)
    return b


def _emraw10(frag):
    return '{"name":"%s","pay_type":"fixed",%s}' % (_n10("BBB_H"), frag)


_bad10("/api/employees", [
    ("pay_type \"xato\" (ilgari JIMGINA fixed)", _em10(pay_type="xato")),
    ("oylik 1e13", _em10(fixed_amount=1e13)),
    ("oylik true", _em10(fixed_amount=True)),
    ("oylik NaN", _emraw10('"fixed_amount":NaN')),
    ("oylik Infinity", _emraw10('"fixed_amount":Infinity')),
    ("foiz NaN", _emraw10('"percent_value":NaN')),
    ("foiz 500", _em10(percent_value=500)),
    ("birlik narxi 1e13", _em10(per_unit_rate=1e13)),
    ("per_unit_type \"xato\"", _em10(per_unit_type="xato")),
    ("per_unit_type \"gips_metr\" (eski)", _em10(per_unit_type="gips_metr")),
    ("qo'shimcha -1 000 000", _em10(extra_monthly=-1000000)),
    ("qo'shimcha 1e13", _em10(extra_monthly=1e13)),
    ("qo'shimcha NaN", _emraw10('"extra_monthly":NaN')),
    ("production_type \"xato\"", _em10(production_type="xato")),
    ("lavozim 150 belgi", _em10(position="p" * 150)),
    ("ism faqat bo'shliq", _em10(name="    ")),
    ("is_active kaliti", _em10(is_active=False)),
    ("company_id kaliti", _em10(company_id=1)),
    ("pay_type siz (majburiy)", {"name": _n10("BBB_H")}),
])


# --- 10d. Loyiha ---
def _pr10(**kw):
    b = {"project_name": _n10("BBB_L"), "client_name": "BBB_Mijoz10"}
    b.update(kw)
    return b


def _prraw10(frag):
    return '{"project_name":"%s","client_name":"BBB_Mijoz10",%s}' % (_n10("BBB_L"), frag)


_bad10("/api/projects", [
    ("byudjet -5", _pr10(total_budget=-5)),
    ("byudjet 1e13", _pr10(total_budget=1e13)),
    ("byudjet true", _pr10(total_budget=True)),
    ("byudjet NaN", _prraw10('"total_budget":NaN')),
    ("byudjet Infinity", _prraw10('"total_budget":Infinity')),
    ("mijoz telefoni 30 belgi", _pr10(client_phone="9" * 30)),
    ("mijoz faqat bo'shliq", _pr10(client_name="   ")),
    ("total_paid qo'lda", _pr10(total_paid=999)),
    ("status COMPLETED", _pr10(status="COMPLETED")),
    ("company_id kaliti", _pr10(company_id=1)),
    ("muddat \"15.10.2026\"", _pr10(deadline="15.10.2026")),
    ("muddat 1990 yil", _pr10(deadline="1990-01-01")),
    ("muddat son", _pr10(deadline=5)),
    ("mijozsiz (majburiy)", {"project_name": _n10("BBB_L")}),
])

for _lbl, _body, _soz in (("total_paid", _pr10(total_paid=999), "to'lovlardan"),
                         ("status", _pr10(status="COMPLETED"), "faol holatda")):
    r = _post10("/api/projects", _body)
    check(f"  \u21b3 loyiha {_lbl}: 400 aniq sabab bilan (\"{_soz}\")",
          r.status_code == 400 and _soz in r.text, r.text[:110])

# --- 10e. Ta'minotchi ---
_bad10("/api/suppliers", [
    ("telefon 30 belgi", {"name": _n10("BBB_T"), "phone": "9" * 30}),
    ("nom faqat bo'shliq", {"name": "    "}),
    ("nom ' b ' (bo'shliqsiz 1 belgi)", {"name": " b "}),
    ("telefon son", {"name": _n10("BBB_T"), "phone": 123}),
    ("is_active kaliti", {"name": _n10("BBB_T"), "is_active": False}),
    ("company_id kaliti", {"name": _n10("BBB_T"), "company_id": 1}),
    ("nomsiz (majburiy)", {"phone": "998901234567"}),
])


# --- 10f. Material qayta yaratish (qayta ishlatish yo'li) ---
def _inv_row10(nm):
    db.rollback()
    db.expire_all()
    return db.query(Inventory).filter(Inventory.company_id == 2, Inventory.item_name == nm).first()


def _purch10(iid):
    db.rollback()
    return db.query(_IP10).filter(_IP10.inventory_id == iid).count()


# (1) ishlatilmagan (qoldiq 0, xaridsiz) qator — qoldiq 50 bilan qayta
_nm = _n10("BBB_R")
_req7("post", "/api/inventory", json={"item_name": _nm, "unit": "kg", "stock_quantity": 0,
                                      "notes": "asl izoh"})
_o = _inv_row10(_nm)
_p0 = _purch10(_o.id) if _o else None
r = _req7("post", "/api/inventory", json={"item_name": _nm, "unit": "kg", "stock_quantity": 50,
                                          "price_per_unit": 1000})
_o = _inv_row10(_nm)
check(f"qayta yaratish (ishlatilmagan): qoldiq 50 \u2192 {r.status_code}, xarid yozuvi yaratildi",
      r.status_code == 200 and _o is not None and _o.stock_quantity == 50
      and _p0 == 0 and _purch10(_o.id) == 1, f"{r.text[:90]} | xarid {_p0} -> {_purch10(_o.id) if _o else None}")
check("  \u21b3 izoh berilmagan — eski izoh saqlandi",
      _o is not None and _o.notes == "asl izoh", repr(_o.notes if _o else None))

# (2) o'chirilgan (yumshoq) qator — qoldiq 30 bilan tiriltirish
_nm = _n10("BBB_R")
r0 = _req7("post", "/api/inventory", json={"item_name": _nm, "unit": "kg", "stock_quantity": 7,
                                           "price_per_unit": 500})
_o = _inv_row10(_nm)
if _o is not None:
    _req7("delete", f"/api/inventory/{_o.id}")
_o = _inv_row10(_nm)
_soft = bool(_o is not None and _o.is_deleted)
_p0 = _purch10(_o.id) if _o else None
r = _req7("post", "/api/inventory", json={"item_name": _nm, "unit": "kg", "stock_quantity": 30,
                                          "price_per_unit": 600})
_o = _inv_row10(_nm)
check(f"qayta yaratish (o'chirilgan): qoldiq 30 \u2192 {r.status_code}, yangi xarid yozuvi yaratildi",
      _soft and r.status_code == 200 and _o is not None and not _o.is_deleted
      and _p0 == 1 and _purch10(_o.id) == 2,
      f"yumshoq={_soft} {r.text[:80]} | xarid {_p0} -> {_purch10(_o.id) if _o else None}")

# (3) korxonaning ASOSIY penoplasti qayta yaratilganda
_nm = _n10("BBB_P")
_req7("post", "/api/inventory", json={"item_name": _nm, "unit": "blok", "stock_quantity": 0,
                                      "is_penoplast": True})
_px = _inv_row10(_nm)
_px_id = _px.id if _px is not None else -1
_rs = _req7("post", f"/api/inventory/{_px_id}/set-default-penoplast")


def _def10():
    db.rollback()
    db.expire_all()
    return [x.id for x in db.query(Inventory).filter(
        Inventory.company_id == 2, Inventory.is_default_penoplast == True).all()]  # noqa: E712


check(f"  (tayyorgarlik: yangi penoplast asosiy qilindi \u2192 {_rs.status_code})",
      _rs.status_code == 200 and _def10() == [_px_id], f"{_rs.text[:80]} | {_def10()}")
r = _req7("post", "/api/inventory", json={"item_name": _nm, "unit": "blok", "is_penoplast": True,
                                          "is_default_penoplast": False})
check(f"qayta yaratish (asosiy penoplast, is_default false) \u2192 {r.status_code}, korxonada asosiy penoplast SAQLANDI",
      r.status_code == 200 and _def10() == [_px_id], f"{r.text[:80]} | asosiylar: {_def10()}")
c0 = _cnt10()
r = _req7("post", "/api/inventory", json={"item_name": _nm, "unit": "blok", "is_penoplast": False})
_o = _inv_row10(_nm)
check(f"qayta yaratish (asosiy penoplast \u2192 oddiy material) \u2192 {r.status_code} (400 shart), o'zgarmadi",
      r.status_code == 400 and _o is not None and _o.is_penoplast and _def10() == [_px_id]
      and c0 == _cnt10(), f"{r.text[:90]} | peno={_o.is_penoplast if _o else None} asosiylar={_def10()}")
_rs = _req7("post", f"/api/inventory/{B_DEF9}/set-default-penoplast")
check(f"  (tiklash: B ning asl asosiy penoplasti qaytarildi \u2192 {_rs.status_code})",
      _rs.status_code == 200 and _def10() == [B_DEF9], f"{_rs.text[:80]} | {_def10()}")


# --- 10g. Ildiz: crud to'g'ridan-to'g'ri (pydantic o'tkazadigan, qoida rad etadigan) ---
def _root10(lbl, fn):
    c0 = _cnt10()
    try:
        with contextlib.redirect_stdout(_quiet):
            fn()
        ok, why = False, "xato chiqmadi"
    except ValueError as e:
        ok, why = True, str(e)[:60]
    except Exception as e:                           # noqa: BLE001
        ok, why = False, f"{type(e).__name__}: {str(e)[:60]}"
    db.rollback()
    c1 = _cnt10()
    check(f"ildiz: {lbl} \u2192 ValueError VA hech narsa yaratilmadi",
          ok and c0 == c1, f"{why} | {c0} -> {c1}")


_root10("add_item narx -5", lambda: crud.add_item(db, schemas.InventoryCreate(
    item_name=_n10("BBB_M"), unit="kg", price_per_unit=-5), company_id=2))
_root10("add_item birlik '   '", lambda: crud.add_item(db, schemas.InventoryCreate(
    item_name=_n10("BBB_M"), unit="   "), company_id=2))
_root10("create_master hudud 80 belgi", lambda: crud.create_master(db, schemas.MasterCreate(
    name=_n10("BBB_U"), phone=_tel10(), region="r" * 80), company_id=2))
_root10("create_employee pay_type 'xato'", lambda: crud.create_employee(db, schemas.EmployeeCreate(
    name=_n10("BBB_H"), pay_type="xato"), company_id=2))
_root10("create_employee production_type 'xato'", lambda: crud.create_employee(
    db, schemas.EmployeeCreate(name=_n10("BBB_H"), pay_type="fixed", production_type="xato"),
    company_id=2))
_root10("create_project byudjet -5", lambda: crud.create_project(db, schemas.ProjectCreate(
    project_name=_n10("BBB_L"), client_name="BBB_Mijoz10", total_budget=-5), company_id=2))
_root10("create_supplier nom '   '", lambda: crud.create_supplier(db, schemas.SupplierCreate(
    name="   "), company_id=2))

_c0 = _cnt10()
try:
    with contextlib.redirect_stdout(_quiet):
        _e10 = crud.create_employee(db, schemas.EmployeeCreate(
            name=_n10("BBB_H"), pay_type="PERCENT_SALES", percent_value=5), company_id=2)
    _pt10 = _e10.pay_type.value
except Exception as _x10:                              # noqa: BLE001
    db.rollback()
    _pt10 = f"{type(_x10).__name__}: {_x10}"
check("ildiz nazorat: create_employee pay_type 'PERCENT_SALES' \u2192 percent_sales (JIMGINA fixed EMAS)",
      _pt10 == "percent_sales", str(_pt10)[:100])

# --- 10h. Statik: yaratish qoidalarida PK/FK yo'q, hammasi ustun ---
try:
    _cr10 = crud._create_rules()
    _mod10 = {"Inventory": Inventory, "Master": _MS10, "Employee": _EM10,
              "Project": _PR10, "Supplier": _SP10}
    _yomon10 = []
    for _mn, _r in _cr10.items():
        _cols = {c.name: c for c in _mod10[_mn].__table__.columns}
        for _f in _r:
            if _f == "id" or _f == "company_id" or _f.endswith("_id") and _f != "telegram_id":
                _yomon10.append(f"{_mn}.{_f} (bog'lanish)")
            elif _f not in _cols:
                _yomon10.append(f"{_mn}.{_f} (ustun yo'q)")
            elif _cols[_f].primary_key or _cols[_f].foreign_keys:
                _yomon10.append(f"{_mn}.{_f} (PK/FK)")
        for _t in crud._CREATE_TAQIQ.get(_mn, {}):
            if _t in _r:
                _yomon10.append(f"{_mn}.{_t} (taqiqlangan, lekin ruxsatda)")
        for _t in crud._CREATE_MAJBURIY.get(_mn, {}):
            if _t not in _r:
                _yomon10.append(f"{_mn}.{_t} (majburiy, lekin ruxsatda yo'q)")
    check("statik: yaratish qoidalarida PK/FK yo'q, hammasi ustun, taqiq/majburiy mos",
          not _yomon10 and set(_cr10) == set(_mod10) == set(crud._CREATE_MAJBURIY), str(_yomon10[:5]))
except Exception as _e10:                              # noqa: BLE001
    check("statik: yaratish qoidalarida PK/FK yo'q, hammasi ustun, taqiq/majburiy mos",
          False, f"{type(_e10).__name__}: {_e10}")


# --- 10i. Nazorat: interfeys AYNAN yuboradigan tanalar → 200 VA haqiqatan yozildi ---
def _ok10(lbl, url, body, qator, kutilgan):
    r = _post10(url, body)
    db.rollback()
    db.expire_all()
    o = qator()
    farq = {} if o is None else {k: (getattr(o, k), v) for k, v in kutilgan.items()
                                 if getattr(o, k) != v}
    check(f"nazorat: POST {url} ({lbl}) \u2192 {r.status_code} (200 shart) VA yozildi",
          r.status_code == 200 and o is not None and not farq,
          f"{r.text[:100]} | {'YOZILMADI' if o is None else farq}")
    return o


_nm = _n10("BBB_M")
_ok10("supplier_receive.html: yangi penoplast", "/api/inventory",
      {"item_name": _nm, "category": "Penoplast", "unit": "blok", "stock_quantity": 0,
       "min_stock": 0, "is_penoplast": True, "is_default_penoplast": False, "volume_per_unit": 1.5},
      lambda: _inv_row10(_nm),
      {"unit": "blok", "category": "Penoplast", "is_penoplast": True, "volume_per_unit": 1.5})
check("  \u21b3 korxonada asosiy penoplast o'zgarmadi", _def10() == [B_DEF9], str(_def10()))
_nm = _n10("BBB_M")
_ok10("suppliers.html: yangi material", "/api/inventory",
      {"item_name": _nm, "category": "Kimyo", "unit": "kg", "stock_quantity": 0, "min_stock": 0},
      lambda: _inv_row10(_nm), {"category": "Kimyo", "stock_quantity": 0.0})
_nm = _n10("BBB_M")
_o = _ok10("API: boshlang'ich qoldiq 10 × 1000", "/api/inventory",
           {"item_name": _nm, "unit": "kg", "stock_quantity": 10, "price_per_unit": 1000},
           lambda: _inv_row10(_nm), {"stock_quantity": 10.0})
check("  \u21b3 boshlang'ich qoldiq xaridi (10 000) yozildi",
      _o is not None and _purch10(_o.id) == 1, str(_purch10(_o.id) if _o else None))

for _src, _reg in (("kpi.html", None), ("masters_manage.html", "Andijon")):
    _nm, _tl = _n10("BBB_U"), _tel10()
    _ok10(f"{_src}: usta formasi", "/api/masters",
          {"name": _nm, "region": _reg, "telegram_id": None, "notes": None, "phone": _tl},
          lambda: db.query(_MS10).filter(_MS10.company_id == 2, _MS10.name == _nm).first(),
          {"phone": _tl, "region": _reg, "is_active": True})
_nm = _n10("BBB_U")
_ok10("API: cashback 5 + kpi 7 (ilgari kpi YOZILMASDI)", "/api/masters",
      {"name": _nm, "phone": _tel10(), "cashback_percent": 5, "kpi_percent": 7},
      lambda: db.query(_MS10).filter(_MS10.company_id == 2, _MS10.name == _nm).first(),
      {"cashback_percent": 5.0, "kpi_percent": 7.0})

_nm = _n10("BBB_H")
_o = _ok10("kpi.html: hodim formasi (qoplama)", "/api/employees",
           {"name": _nm, "position": None, "pay_type": "fixed_plus_coating", "fixed_amount": 2000000,
            "percent_value": 0, "per_unit_rate": 1000, "per_unit_type": "metr",
            "extra_monthly": None, "production_type": "penoplast", "notes": None},
           lambda: db.query(_EM10).filter(_EM10.company_id == 2, _EM10.name == _nm).first(),
           {"per_unit_type": "metr", "production_type": "penoplast", "extra_monthly": None})
check("  \u21b3 to'lov turi fixed_plus_coating VA boshlang'ich tarix yozuvi (1 ta)",
      _o is not None and _o.pay_type.value == "fixed_plus_coating"
      and db.query(_ECH10).filter(_ECH10.employee_id == _o.id).count() == 1,
      str(_o.pay_type if _o else None))

_nm = _n10("BBB_L")
_o = _ok10("projects.html: yangi loyiha + muddat", "/api/projects",
           {"client_name": "BBB_Mijoz10", "client_phone": None, "client_address": None,
            "notes": None, "project_name": _nm, "total_budget": 1500000, "deadline": "2026-10-15"},
           lambda: db.query(_PR10).filter(_PR10.company_id == 2, _PR10.project_name == _nm).first(),
           {"client_name": "BBB_Mijoz10"})
check("  \u21b3 muddat 2026-10-15 saqlandi (ilgari JIMGINA tashlanardi), byudjet 1 500 000",
      _o is not None and _o.deadline is not None and _o.deadline.date().isoformat() == "2026-10-15"
      and float(_o.total_budget) == 1500000.0,
      f"{_o.deadline if _o else None} / {_o.total_budget if _o else None}")
_nm = _n10("BBB_L")
_ok10("projects.html: muddatsiz (deadline null)", "/api/projects",
      {"client_name": "BBB_Mijoz10", "client_phone": None, "client_address": None,
       "notes": None, "project_name": _nm, "total_budget": 0, "deadline": None},
      lambda: db.query(_PR10).filter(_PR10.company_id == 2, _PR10.project_name == _nm).first(),
      {"deadline": None})
check("  \u21b3 GET /api/projects \u2192 200", _req7("get", "/api/projects").status_code == 200)

_nm = _n10("BBB_T")
_ok10("supplier_receive.html: yangi ta'minotchi", "/api/suppliers", {"name": _nm, "phone": None},
      lambda: db.query(_SP10).filter(_SP10.company_id == 2, _SP10.name == _nm).first(),
      {"phone": None})
_nm = _n10("BBB_T")
_ok10("suppliers.html: forma", "/api/suppliers",
      {"name": _nm, "phone": "+998901234567", "notes": "izoh10"},
      lambda: db.query(_SP10).filter(_SP10.company_id == 2, _SP10.name == _nm).first(),
      {"phone": "+998901234567", "notes": "izoh10"})

# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 66)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
print(f"tenant_context statistikasi: {_tc.get_stats()}")
if FAILED:
    print("\nSIZISHLAR:")
    for f in FAILED:
        print("   \u2717 " + f)
print("=" * 66)
sys.exit(1 if FAIL else 0)
