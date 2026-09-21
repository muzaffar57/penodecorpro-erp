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
print("\n" + "=" * 66)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
print(f"tenant_context statistikasi: {_tc.get_stats()}")
if FAILED:
    print("\nSIZISHLAR:")
    for f in FAILED:
        print("   \u2717 " + f)
print("=" * 66)
sys.exit(1 if FAIL else 0)
