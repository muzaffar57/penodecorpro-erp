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
print("\n" + "=" * 66)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
print(f"tenant_context statistikasi: {_tc.get_stats()}")
if FAILED:
    print("\nSIZISHLAR:")
    for f in FAILED:
        print("   \u2717 " + f)
print("=" * 66)
sys.exit(1 if FAIL else 0)
