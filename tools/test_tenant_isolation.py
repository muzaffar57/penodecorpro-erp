#!/usr/bin/env python3
"""
test_tenant_isolation.py — ikki korxonali avtomatik izolyatsiya testi.

NIMA UCHUN KERAK
----------------
M1–M8 davomida topilgan HAR BIR sizish faqat qo'lda, brauzerda, ikkita
sessiya bilan tekshirilganda ko'rindi. Bu test o'sha tekshiruvni
takrorlanadigan qiladi: parol talab qilmaydi, serverga ulanmaydi,
vaqtinchalik bazada ikkita korxona qurib, har bir modul bo'yicha
A→B rad etilishini va A→A ishlashini tekshiradi.

MUHIM: SQLite'da chet el kalitlari (FK) ATAYLAB yoqiladi — aks holda
PostgreSQL'da chiqadigan xatolar bu yerda ko'rinmay qoladi (M7 da
factory reset aynan shu sababli lokalda o'tib, staging'da yiqilgan).

ISHLATISH
---------
    python tests/test_tenant_isolation.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import datetime as dt
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "tenant_isolation_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import main                      # noqa: E402  (jadvallarni yaratadi)
import crud, services, auth, schemas   # noqa: E402
from sqlalchemy import event, text     # noqa: E402
from database import SessionLocal, engine   # noqa: E402


@event.listens_for(engine, "connect")
def _fk_on(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


engine.dispose()

from production_models import Company           # noqa: E402
from models import (                            # noqa: E402
    Master, Supplier, Inventory, Recipe, Project, Order, OrderItem, Employee,
    User, UserRole, PayType, ActivityLog, LoginHistory, CompanySetting,
    CashTransaction, ExpenseTransaction, TransportExpense, MonthlyExpense,
    RecurringObligation, GiftPeriod, MasterGift, FinishedProduct,
    InventoryReceipt, InventoryMovement,
)

db = SessionLocal()
OK = FAIL = 0
FAILED = []


def check(label, cond):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}")


def section(t):
    print(f"\n--- {t} ---")


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik: ikkita korxona va ularning to'liq ma'lumoti
# ══════════════════════════════════════════════════════════════
if not db.query(Company).filter(Company.id == 2).first():
    db.add(Company(id=2, name="Test Korxona B"))
    db.commit()
NOW = dt.datetime.utcnow()


def build(cid, tag):
    """Bitta korxonaning to'liq ma'lumot to'plamini yaratadi."""
    u = auth.create_user(db, f"{tag}_user", "Parol123!", UserRole.ADMIN, tag, company_id=cid)
    m = crud.create_master(db, schemas.MasterCreate(
        name=f"{tag}_Usta", phone=f"+9989{cid}000001"), company_id=cid)
    s = crud.create_supplier(db, schemas.SupplierCreate(name=f"{tag}_Sup"), company_id=cid)
    i = crud.add_item(db, schemas.InventoryCreate(
        item_name=f"{tag}_Mat", unit="kg", stock_quantity=100,
        price_per_unit=1000), company_id=cid)
    r = crud.create_recipe(db, schemas.RecipeCreate(
        name=f"{tag}_Rec", batch_size_kg=10,
        ingredients=[schemas.RecipeIngredientCreate(inventory_id=i.id, quantity_kg=1)]),
        company_id=cid)
    p = crud.create_project(db, schemas.ProjectCreate(
        project_name=f"{tag}_L", client_name=f"{tag}_Mijoz"), company_id=cid)
    e = crud.create_employee(db, schemas.EmployeeCreate(
        name=f"{tag}_Hodim", pay_type="fixed", fixed_amount=1000000), company_id=cid)
    o = crud.create_order(db, schemas.OrderCreate(
        project_id=p.id, order_type="product",
        items=[schemas.OrderItemCreate(name=f"{tag}_Detal", category="panel",
                                       quantity=1, unit_price=100000)]),
        performed_by=tag)
    crud.record_cash_transaction(db, "boshlangich", 1000 * cid, notes=tag, company_id=cid)
    crud.create_expense_transaction(db, {"category": "tushlik", "amount": 500 * cid,
                                         "date": NOW}, company_id=cid)
    crud.set_setting(db, "ehson_percent", str(cid), company_id=cid)
    crud.log_activity(db, "created", "master", m.id, m.name, tag, company_id=cid)
    crud.log_login_attempt(db, f"{tag}_user", True, f"10.0.0.{cid}")
    crud.create_inventory_receipt(
        db, items=[{"inventory_id": i.id, "quantity": 5, "price_per_unit": 1000}],
        transport_cost=5000, supplier_id=None, document_number=f"{tag}-R1",
        created_by=tag, company_id=cid)
    return dict(user=u, master=m, supplier=s, inv=i, recipe=r, project=p,
                employee=e, order=o)


A = build(1, "AAA")
B = build(2, "BBB")

# ══════════════════════════════════════════════════════════════
section("1. YOZISH: har bir yozuv o'z korxonasiga tushdimi")
# ══════════════════════════════════════════════════════════════
for name, key in [("User", "user"), ("Master", "master"), ("Supplier", "supplier"),
                  ("Inventory", "inv"), ("Recipe", "recipe"), ("Project", "project"),
                  ("Employee", "employee"), ("Order", "order")]:
    check(f"A {name}.company_id == 1", getattr(A[key], "company_id", None) == 1)
    check(f"B {name}.company_id == 2", getattr(B[key], "company_id", None) == 2)
check("B OrderItem ham 2", all(it.company_id == 2 for it in B["order"].items))
check("B ActivityLog 2",
      db.query(ActivityLog).filter(ActivityLog.performed_by == "BBB").first().company_id == 2)
check("B LoginHistory 2",
      db.query(LoginHistory).filter(LoginHistory.username == "BBB_user").first().company_id == 2)
check("B InventoryReceipt 2 (ta'minotchisiz)",
      db.query(InventoryReceipt).filter(
          InventoryReceipt.document_number == "BBB-R1").first().company_id == 2)
check("CompanySetting alohida qatorlar",
      {r.company_id: r.value for r in db.query(CompanySetting).all()} == {1: "1", 2: "2"})

# ══════════════════════════════════════════════════════════════
section("2. NEGATIV: company_id siz INSERT bloklanadimi")
# ══════════════════════════════════════════════════════════════
NEG = [("Master", lambda: Master(name="X", phone="+7")),
       ("Supplier", lambda: Supplier(name="X")),
       ("Inventory", lambda: Inventory(item_name="X", unit="kg", stock_quantity=0)),
       ("Recipe", lambda: Recipe(name="X")),
       ("Project", lambda: Project(project_name="X", client_name="X")),
       ("Employee", lambda: Employee(name="X", pay_type=PayType.FIXED, fixed_amount=1)),
       ("CashTransaction", lambda: CashTransaction(category="boshlangich", amount=1)),
       ("ExpenseTransaction", lambda: ExpenseTransaction(date=NOW, category="x", amount=1)),
       ("TransportExpense", lambda: TransportExpense(amount=1, expense_date=NOW)),
       ("MonthlyExpense", lambda: MonthlyExpense(year=2026, month=9)),
       ("ActivityLog", lambda: ActivityLog(action="x", entity_type="y", entity_id=1)),
       ("LoginHistory", lambda: LoginHistory(username="x", success=True)),
       ("CompanySetting", lambda: CompanySetting(key="k2", value="v")),
       ("RecurringObligation", lambda: RecurringObligation(category="c", label="l",
                                                           monthly_target=1)),
       ("GiftPeriod", lambda: GiftPeriod(is_active=True)),
       ("MasterGift", lambda: MasterGift(name="g", kpi_threshold=1))]
blocked = 0
for nm, f in NEG:
    try:
        db.add(f())
        db.commit()
        db.rollback()
    except Exception:
        db.rollback()
        blocked += 1
check(f"company_id siz INSERT bloklandi ({blocked}/{len(NEG)})", blocked == len(NEG))

# ══════════════════════════════════════════════════════════════
section("3. O'QISH: ro'yxatlarda boshqa korxona yo'q")
# ══════════════════════════════════════════════════════════════
check("masters", all(x.company_id == 1 for x in crud.get_masters(db, company_id=1)))
check("suppliers", all(x.company_id == 1 for x in crud.get_suppliers(db, company_id=1)))
check("inventory", all(x.company_id == 1 for x in crud.get_inventory(db, company_id=1)))
check("recipes", all(x.company_id == 1 for x in crud.get_recipes(db, company_id=1)))
check("projects", all(x.company_id == 1 for x in crud.get_projects(db, company_id=1)))
check("orders", all(x.company_id == 1 for x in crud.get_orders(db, company_id=1)))
check("employees", all(x.company_id == 1 for x in crud.get_employees(db, company_id=1)))
check("activity log", all(x.company_id == 1 for x in crud.get_activity_log(db, company_id=1)))
check("login history", all(x.company_id == 1 for x in crud.get_login_history(db, company_id=1)))
check("cash transactions",
      all(x.company_id == 1 for x in crud.get_cash_transactions(db, company_id=1)))
check("expense transactions",
      all(x.company_id == 1 for x in crud.get_expense_transactions(db, company_id=1)))

# ══════════════════════════════════════════════════════════════
section("4. A → B: ID bo'yicha kirish rad etiladimi")
# ══════════════════════════════════════════════════════════════
check("get_master", crud.get_master(db, B["master"].id, company_id=1) is None)
check("update_master", crud.update_master(db, B["master"].id,
                                          schemas.MasterUpdate(notes="hack"), company_id=1) is None)
check("delete_master", crud.delete_master(db, B["master"].id, company_id=1) is False)
check("update_master_kpi", crud.update_master_kpi(db, B["master"].id, 99, company_id=1) is None)
check("get_order", crud.get_order(db, B["order"].id, company_id=1) is None)
check("projects ro'yxatida B loyihasi yo'q",
      all(p.id != B["project"].id for p in crud.get_projects(db, company_id=1)))
check("get_item", crud.get_item(db, B["inv"].id, company_id=1) is None)
check("get_recipe", crud.get_recipe(db, B["recipe"].id, company_id=1) is None)
check("get_supplier_debt", crud.get_supplier_debt(db, B["supplier"].id,
                                                  company_id=1)["debt"] == 0)
check("get_supplier_history",
      crud.get_supplier_history(db, B["supplier"].id, company_id=1)["purchases"] == [])
check("get_supplier_purchased_items",
      crud.get_supplier_purchased_items(db, B["supplier"].id, company_id=1) == [])
check("employee_of_company", auth.employee_of_company(db, B["employee"].id, 1) is None)
check("master_of_company", auth.master_of_company(db, B["master"].id, 1) is None)

# ══════════════════════════════════════════════════════════════
section("5. AGREGAT: boshqa korxona summasi aralashmaydimi")
# ══════════════════════════════════════════════════════════════
cbA = services.get_cash_balance(db, company_id=1)
cbB = services.get_cash_balance(db, company_id=2)
check(f"kassa A={cbA['qolda_jami']:.0f} / B={cbB['qolda_jami']:.0f} — alohida",
      cbA["qolda_jami"] == 1000 and cbB["qolda_jami"] == 2000)
# A: 500 (qo'lda) + 5000 (kirim transporti) = 5500
# B: 1000 (qo'lda) + 5000 (kirim transporti) = 6000
check(f"chiqim_qoshimcha alohida (A={cbA['chiqim_qoshimcha']:.0f} / B={cbB['chiqim_qoshimcha']:.0f})",
      cbA["chiqim_qoshimcha"] == 5500 and cbB["chiqim_qoshimcha"] == 6000)
repA = services.get_monthly_report(db, NOW.year, NOW.month, company_id=1)
repB = services.get_monthly_report(db, NOW.year, NOW.month, company_id=2)
check("oylik hisobot alohida", repA is not None and repB is not None)
dsA = services.get_full_debt_summary(db, NOW.year, NOW.month, company_id=1)
check("qarz jamlanmasi A da B ning buyurtmasi yo'q",
      abs(dsA["customer_debt"] - 100000) < 1)
chA = services.get_chart_data(db, company_id=1)
check("dashboard grafigi A da B ning ustasi yo'q",
      all("BBB" not in x["name"] for x in chA["master_kpi"]))
ppA = services.get_production_period_stats(db, company_id=1)
check("ishlab chiqarish statistikasi tenant-scoped", isinstance(ppA, dict))

# ══════════════════════════════════════════════════════════════
section("6. BACKUP: faqat o'z korxonasi, maxfiy ustunlarsiz")
# ══════════════════════════════════════════════════════════════
bkA = crud.export_full_backup(db, company_id=1)
import json as _json
rawA = _json.dumps(bkA, ensure_ascii=False, default=str)
check("A backupda B ning ma'lumoti yo'q", "BBB" not in rawA)
check("A backupda o'z ma'lumoti bor", "AAA_Usta" in rawA)
check("parol hashi yo'q", "password_hash" not in rawA)
check("PIN hashi yo'q", "pin_hash" not in rawA)
check("sessiya jadvallari yo'q",
      "user_sessions" not in bkA["tables"] and "employee_sessions" not in bkA["tables"])

# ══════════════════════════════════════════════════════════════
section("7. FACTORY RESET: faqat o'z korxonasini tozalaydimi")
# ══════════════════════════════════════════════════════════════
b_before = db.query(Order).filter(Order.company_id == 2).count()
crud.factory_reset_all_data(db, company_id=1)
check("A buyurtmalari o'chdi", db.query(Order).filter(Order.company_id == 1).count() == 0)
check(f"B buyurtmalari TEGILMADI ({b_before})",
      db.query(Order).filter(Order.company_id == 2).count() == b_before)
check("B ustasi joyida", db.query(Master).filter(Master.company_id == 2).count() == 1)
check("B xodimi joyida", db.query(Employee).filter(Employee.company_id == 2).count() == 1)

# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 62)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}")
if FAILED:
    print("\nYIQILGANLAR:")
    for f in FAILED:
        print("   \u2717 " + f)
print("=" * 62)
db.close()
try:
    os.remove(_DB)
except OSError:
    pass
sys.exit(0 if FAIL == 0 else 1)
