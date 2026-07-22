"""
PenoDecorPro ERP — Biznes mantiqi (Services)
==============================================
Avtomatik hisob-kitob va ishlab chiqarish nazorati.

Asosiy funksiyalar:
1. check_admin_role() — faqat admin uchun ruxsat
2. process_cutting() — kesish: penoplast blok hisob-kitob
3. process_coating() — qoplama: retsept bo'yicha ombor kamayishi
4. check_low_stock() — minimal qoldiq ogohlantirishi
"""

from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import (
    User, UserRole, Inventory, Recipe, Order, OrderItem,
    Master, OrderStatus
)


# ============================================================
# 1. ADMIN NAZORATI
# ============================================================

def check_admin_role(user: User):
    """Faqat admin foydalanuvchisi bu amalni qila oladi.
    Xato bo'lsa HTTPException ko'taradi."""
    if not user or user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Bu amal faqat ADMIN uchun ruxsat etilgan!"
        )


def check_role(user: User, allowed_roles: List[UserRole]):
    """Belgilangan rollar ro'yxatidagi foydalanuvchilar uchun ruxsat."""
    if not user or user.role not in allowed_roles:
        roles_str = ", ".join([r.value for r in allowed_roles])
        raise HTTPException(
            status_code=403,
            detail=f"Bu amal faqat quyidagi rollar uchun: {roles_str}"
        )


# ============================================================
# 2. AVTOMATIK KESISH (Penoplast bloklari)
# ============================================================

# Standart penoplast blok hajmi (m³)
PENOPLAST_BLOCK_VOLUME_M3 = 1.0  # 1 m × 1 m × 1 m = 1 m³
# Yo'qotish foizi (kesish vaqtida)
CUTTING_LOSS_PERCENT = 5.0  # 5% yo'qotish


def calculate_blocks_needed(volume_m3: float, loss_percent: float = CUTTING_LOSS_PERCENT) -> Dict:
    """Berilgan hajm uchun necha blok kerakligini hisoblaydi.

    Misol: 2.5 m³ kerak bo'lsa, 5% yo'qotish bilan = 2.625 m³
    Demak 3 ta blok (har biri 1 m³) kerak bo'ladi.
    """
    actual_needed = volume_m3 * (1 + loss_percent / 100)
    blocks_needed = int(actual_needed / PENOPLAST_BLOCK_VOLUME_M3)
    if actual_needed % PENOPLAST_BLOCK_VOLUME_M3 > 0:
        blocks_needed += 1  # Yaxlitlash yuqoriga

    return {
        "volume_m3_requested": volume_m3,
        "volume_m3_with_loss": actual_needed,
        "blocks_needed": blocks_needed,
        "loss_percent": loss_percent
    }


def process_cutting(db: Session, order_id: int, volume_m3: float) -> Dict:
    """Kesish jarayonini boshqaradi.

    Formula: total_volume / volume_per_unit = necha dona blok kerak
    Misol: 2.5 m³ kerak, blok hajmi 1.0 m³ -> 3 dona blok
    """
    if volume_m3 <= 0:
        return {"success": False, "message": "Hajm 0 dan katta bo'lishi kerak"}

    # Inventory dan penoplast topish
    penoplast = db.query(Inventory).filter(
        Inventory.item_name.ilike("%penoplast%")
    ).with_for_update().first()

    if not penoplast:
        return {
            "success": False,
            "message": "Omborda 'Penoplast' xomashyosi yo'q!"
        }

    # Yo'qotish bilan haqiqiy hajm
    actual_needed = volume_m3 * (1 + CUTTING_LOSS_PERCENT / 100)

    # Blok hajmiga bo'lib, donalar sonini topamiz
    block_volume = penoplast.volume_per_unit or 1.0
    blocks_needed = int(actual_needed / block_volume)
    if actual_needed % block_volume > 0:
        blocks_needed += 1

    if penoplast.stock_quantity < blocks_needed:
        return {
            "success": False,
            "message": f"Penoplast yetarli emas! Kerak: {blocks_needed} dona, omborda: {penoplast.stock_quantity:.0f} {penoplast.unit}",
            "needed": blocks_needed,
            "available": penoplast.stock_quantity
        }

    # Kamaytirish
    penoplast.stock_quantity -= blocks_needed
    db.commit()

    return {
        "success": True,
        "message": f"Kesish bajarildi! {blocks_needed} ta blok ishlatildi.",
        "calculation": {
            "volume_m3_requested": volume_m3,
            "volume_m3_with_loss": actual_needed,
            "block_volume_m3": block_volume,
            "blocks_needed": blocks_needed
        },
        "inventory_updated": {
            "item": penoplast.item_name,
            "deducted": blocks_needed,
            "remaining": penoplast.stock_quantity
        }
    }


# ============================================================
# 3. AVTOMATIK QOPLAMA (Retsept bo'yicha)
# ============================================================

# Standart: 1 m² qoplama uchun ~2 kg loy ketadi
KG_PER_SQUARE_METER = 2.0


def calculate_coating_materials(coated_area_m2: float, recipe: Recipe) -> Dict:
    """Berilgan qoplama maydoni uchun retsept bo'yicha materiallar hisobi.

    Misol: 50 m² qoplama uchun 100 kg loy kerak.
    Retsept 150 kg uchun yozilgan bo'lsa, 100/150 = 0.667 koeffitsient.
    Har bir ingredient shu koeffitsientga ko'paytirilib hisoblanadi.
    """
    total_kg_needed = coated_area_m2 * KG_PER_SQUARE_METER
    coefficient = total_kg_needed / recipe.batch_size_kg if recipe.batch_size_kg else 0

    materials = {ing.item_name: float(ing.quantity_kg or 0) * coefficient for ing in recipe.ingredients}

    # Faqat qiymati 0 dan katta bo'lganlarini qoldiramiz
    materials = {k: v for k, v in materials.items() if v > 0}

    return {
        "coated_area_m2": coated_area_m2,
        "total_loy_kg": total_kg_needed,
        "batches": coefficient,
        "materials": materials
    }


def process_coating(db: Session, order_id: int, coated_area_m2: float) -> Dict:
    """Qoplama jarayonini boshqaradi.

    1. Buyurtmadagi retseptni oladi
    2. Maydonga qarab materiallar miqdorini hisoblaydi
    3. Har birini Inventory dan ayiradi
    4. Yetarli emas bo'lsa xato qaytaradi
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    # Buyurtmadagi item lardan recipe_id topish
    recipe_id = None
    for item in order.items:
        if item.recipe_id:
            recipe_id = item.recipe_id
            break

    if not recipe_id:
        return {"success": False, "message": "Buyurtmaga retsept biriktirilmagan"}

    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        return {"success": False, "message": "Retsept topilmadi"}

    # Materiallar hisobi
    calc = calculate_coating_materials(coated_area_m2, recipe)

    # Avval barcha materiallar yetarliligini tekshiramiz
    shortages = []
    items_to_deduct = []

    for comp_name, qty_needed in calc["materials"].items():
        inv_item = db.query(Inventory).filter(
            Inventory.item_name.ilike(f"%{comp_name}%")
        ).with_for_update().first()

        if not inv_item:
            shortages.append(f"{comp_name}: omborda yo'q")
            continue

        if inv_item.stock_quantity < qty_needed:
            shortages.append(
                f"{inv_item.item_name}: kerak {qty_needed:.2f}, bor {inv_item.stock_quantity:.2f} {inv_item.unit}"
            )
        else:
            items_to_deduct.append((inv_item, qty_needed))

    if shortages:
        return {
            "success": False,
            "message": "Xomashyo yetarli emas!",
            "shortages": shortages
        }

    # Hammasi yetarli — kamaytiramiz
    deducted = []
    for inv_item, qty in items_to_deduct:
        inv_item.stock_quantity -= qty
        deducted.append({
            "item": inv_item.item_name,
            "deducted": round(qty, 2),
            "unit": inv_item.unit,
            "remaining": round(inv_item.stock_quantity, 2)
        })

    db.commit()

    return {
        "success": True,
        "message": f"Qoplama bajarildi! {coated_area_m2} m² maydon uchun materiallar ishlatildi.",
        "calculation": calc,
        "deducted_items": deducted
    }


# ============================================================
# 4. MINIMAL QOLDIQ OGOHLANTIRISHI
# ============================================================

def get_top_products_report(db: Session, days: int = 90, limit: int = 15) -> list:
    """Eng ko'p daromad keltirgan mahsulotlar — nomi bo'yicha guruhlangan,
    tayyor (READY/DELIVERED) buyurtmalardagi OrderItem'lardan. Faqat o'qish."""
    from models import OrderItem, Order, OrderStatus
    from sqlalchemy import func
    from datetime import datetime, timedelta

    period_start = datetime.utcnow() - timedelta(days=days)
    rows = db.query(
        OrderItem.name,
        func.sum(OrderItem.total_price).label("revenue"),
        func.sum(OrderItem.quantity).label("qty"),
        func.count(OrderItem.id).label("times_ordered")
    ).join(Order, OrderItem.order_id == Order.id).filter(
        Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED]),
        Order.completed_at >= period_start
    ).group_by(OrderItem.name).order_by(func.sum(OrderItem.total_price).desc()).limit(limit).all()

    return [{
        "name": r.name,
        "revenue": round(float(r.revenue or 0)),
        "quantity": round(float(r.qty or 0), 1),
        "times_ordered": r.times_ordered,
    } for r in rows]


def get_top_finished_products_sold(db: Session, days: int = 30, limit: int = 5) -> list:
    """Dashboard uchun — FAQAT 'Tayyor mahsulotlar' bo'limidan sotilgan
    tovarlar (OrderItem.finished_product_id to'ldirilgan, ya'ni buyurtma
    tayyor ombordan berilgan — maxsus buyurtma qilingan detal EMAS).
    Qaytarilgan miqdor (ReturnItem) — nomi va buyurtma ID'si bo'yicha
    moslashtirilib, sotilgan miqdordan AYRIB tashlanadi. Faqat o'qish."""
    from models import OrderItem, Order, OrderStatus, ReturnItem
    from sqlalchemy import func
    from datetime import datetime, timedelta

    period_start = datetime.utcnow() - timedelta(days=days)

    sold_rows = db.query(
        OrderItem.name,
        OrderItem.order_id,
        func.sum(OrderItem.total_price).label("revenue"),
        func.sum(OrderItem.quantity).label("qty")
    ).join(Order, OrderItem.order_id == Order.id).filter(
        OrderItem.finished_product_id.isnot(None),
        Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED]),
        Order.completed_at >= period_start
    ).group_by(OrderItem.name, OrderItem.order_id).all()

    # Qaytarishlarni (nomi + buyurtma bo'yicha) yig'amiz, keyin ayiramiz
    returns = db.query(
        ReturnItem.item_name, ReturnItem.order_id,
        func.sum(ReturnItem.quantity).label("ret_qty")
    ).filter(ReturnItem.returned_at >= period_start).group_by(
        ReturnItem.item_name, ReturnItem.order_id
    ).all()
    returned_map = {(r.item_name, r.order_id): float(r.ret_qty or 0) for r in returns}

    totals = {}
    for r in sold_rows:
        qty = float(r.qty or 0)
        revenue = float(r.revenue or 0)
        ret_qty = returned_map.get((r.name, r.order_id), 0)
        if ret_qty > 0 and qty > 0:
            # Qaytgan ulushga mos ravishda, daromadni ham proportsional kamaytiramiz
            keep_ratio = max(0, (qty - ret_qty) / qty)
            qty = qty * keep_ratio
            revenue = revenue * keep_ratio

        if r.name not in totals:
            totals[r.name] = {"name": r.name, "revenue": 0.0, "quantity": 0.0, "times_ordered": 0}
        totals[r.name]["revenue"] += revenue
        totals[r.name]["quantity"] += qty
        totals[r.name]["times_ordered"] += 1

    result = sorted(totals.values(), key=lambda x: x["revenue"], reverse=True)[:limit]
    for r in result:
        r["revenue"] = round(r["revenue"])
        r["quantity"] = round(r["quantity"], 1)
    return result


def get_top_materials_report(db: Session, days: int = 90, limit: int = 15) -> list:
    """Eng ko'p ishlatilgan (chiqim bo'lgan) xomashyolar — InventoryMovement
    jurnalidan, nomi bo'yicha guruhlangan. Faqat o'qish."""
    from models import InventoryMovement
    from sqlalchemy import func
    from datetime import datetime, timedelta

    period_start = datetime.utcnow() - timedelta(days=days)
    rows = db.query(
        InventoryMovement.item_name,
        InventoryMovement.unit,
        func.sum(InventoryMovement.quantity).label("total_qty"),
        func.count(InventoryMovement.id).label("movement_count")
    ).filter(
        InventoryMovement.movement_type == "out",
        InventoryMovement.created_at >= period_start
    ).group_by(InventoryMovement.item_name, InventoryMovement.unit).order_by(func.sum(InventoryMovement.quantity).desc()).limit(limit).all()

    return [{
        "item_name": r.item_name,
        "unit": r.unit,
        "total_qty": round(float(r.total_qty or 0), 2),
        "movement_count": r.movement_count,
    } for r in rows]


def get_top_customers_report(db: Session, days: int = 90, limit: int = 10) -> list:
    """Eng ko'p daromad keltirgan mijozlar (loyihalar) — tayyor buyurtmalar
    bo'yicha, mijoz nomi bo'yicha guruhlangan. Faqat o'qish."""
    from models import Order, Project, OrderStatus
    from sqlalchemy import func
    from datetime import datetime, timedelta

    period_start = datetime.utcnow() - timedelta(days=days)
    rows = db.query(
        Project.client_name,
        func.sum(Order.total_amount).label("revenue"),
        func.count(Order.id).label("orders_count")
    ).join(Project, Order.project_id == Project.id).filter(
        Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED]),
        Order.completed_at >= period_start
    ).group_by(Project.client_name).order_by(func.sum(Order.total_amount).desc()).limit(limit).all()

    return [{
        "client_name": r.client_name,
        "revenue": round(float(r.revenue or 0)),
        "orders_count": r.orders_count,
    } for r in rows]


def get_top_suppliers_report(db: Session, days: int = 90, limit: int = 10) -> list:
    """Eng ko'p xarid qilingan yetkazib beruvchilar — xarid summasi bo'yicha.
    Faqat o'qish."""
    from models import InventoryPurchase, Supplier
    from sqlalchemy import func
    from datetime import datetime, timedelta

    period_start = datetime.utcnow() - timedelta(days=days)
    rows = db.query(
        Supplier.name,
        func.sum(InventoryPurchase.total_amount).label("total"),
        func.count(InventoryPurchase.id).label("purchase_count")
    ).join(Supplier, InventoryPurchase.supplier_id == Supplier.id).filter(
        InventoryPurchase.purchased_at >= period_start
    ).group_by(Supplier.name).order_by(func.sum(InventoryPurchase.total_amount).desc()).limit(limit).all()

    return [{
        "supplier_name": r.name,
        "total": round(float(r.total or 0)),
        "purchase_count": r.purchase_count,
    } for r in rows]


def get_monthly_comparison(db: Session, year: int, month: int) -> dict:
    """Joriy oyni o'tgan oy bilan solishtiradi — Daromad, Xarajat, Sof foyda,
    Rentabellik. Mavjud get_monthly_report()dan foydalanadi, hech qanday
    yangi hisob-kitob qoidasi kiritmaydi — faqat ikkita natijani solishtiradi."""
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1

    current = get_monthly_report(db, year, month)
    previous = get_monthly_report(db, prev_year, prev_month)

    def pct_change(cur, prev):
        if not prev:
            return 0.0 if not cur else 100.0
        return round((cur - prev) / abs(prev) * 100, 1)

    metrics = ["daromad", "jami_xarajat", "sof_foyda", "foyda_foiz"]
    comparison = {}
    for m in metrics:
        cur_val = float(current.get(m, 0) or 0)
        prev_val = float(previous.get(m, 0) or 0)
        comparison[m] = {
            "current": cur_val,
            "previous": prev_val,
            "change_pct": pct_change(cur_val, prev_val)
        }
    return comparison


def get_simple_forecast(db: Session, year: int, month: int) -> dict:
    """Oddiy statistik bashorat — shu oyning HOZIRGACHA bo'lgan kunlik
    o'rtachasi asosida, oy oxirigacha taxminiy natijani hisoblaydi.
    Bu — sun'iy intellekt emas, oddiy chiziqli ekstrapolyatsiya."""
    from datetime import datetime
    import calendar

    now = datetime.utcnow()
    days_in_month = calendar.monthrange(year, month)[1]

    if year == now.year and month == now.month:
        days_passed = now.day
    elif (year, month) < (now.year, now.month):
        days_passed = days_in_month  # O'tgan oy — to'liq
    else:
        days_passed = 0  # Kelajak oy — hali ma'lumot yo'q

    report = get_monthly_report(db, year, month)

    if days_passed <= 0:
        return {"available": False, "message": "Bu oy uchun hali ma'lumot yo'q"}

    daromad_kunlik = float(report.get("daromad", 0) or 0) / days_passed
    foyda_kunlik = float(report.get("sof_foyda", 0) or 0) / days_passed

    return {
        "available": True,
        "days_passed": days_passed,
        "days_in_month": days_in_month,
        "forecast_daromad": round(daromad_kunlik * days_in_month),
        "forecast_foyda": round(foyda_kunlik * days_in_month),
        "current_daromad": round(float(report.get("daromad", 0) or 0)),
        "current_foyda": round(float(report.get("sof_foyda", 0) or 0)),
    }


def get_business_alerts(db: Session) -> list:
    """Muhim ogohlantirishlar ro'yxati — oddiy, aniq belgilangan
    chegaralar asosida. Faqat o'qish, hech narsani o'zgartirmaydi."""
    from models import Inventory, Order, OrderStatus
    from datetime import datetime

    alerts = []

    # 1) Kam qolgan xomashyo (min_stock dan kam)
    low_stock = db.query(Inventory).filter(
        Inventory.is_deleted.isnot(True),
        Inventory.stock_quantity <= Inventory.min_stock,
        Inventory.min_stock > 0
    ).all()
    for item in low_stock[:5]:
        alerts.append({
            "level": "red",
            "text": f"Omborda {item.item_name} kamaymoqda ({item.stock_quantity:g} {item.unit} qoldi)"
        })

    # 2) Muddati o'tgan qarzdorlar (30+ kun oldin yaratilgan, hali qarzi bor)
    old_debt_orders = db.query(Order).filter(
        Order.is_deleted.isnot(True),
        Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED, OrderStatus.IN_PROGRESS])
    ).all()
    overdue_count = 0
    for o in old_debt_orders:
        if float(o.debt_amount or 0) > 0 and o.created_at and (datetime.utcnow() - o.created_at).days > 30:
            overdue_count += 1
    if overdue_count > 0:
        alerts.append({"level": "red", "text": f"{overdue_count} ta qarzdorning muddati 30 kundan oshgan"})

    # 3) Bugungi savdo rekord (oxirgi 30 kunning eng yuqorisi)
    today_summary = get_daily_finance_summary(db, datetime.utcnow().date())
    if today_summary["sales"]["total"] > 0:
        alerts.append({"level": "green", "text": f"Bugun {today_summary['sales']['orders_count']} ta buyurtma yakunlandi"})

    priority = {"red": 0, "orange": 1, "green": 2}
    alerts.sort(key=lambda a: priority.get(a["level"], 3))
    return alerts


def get_business_health(db: Session) -> dict:
    """6 ta asosiy ko'rsatkich bo'yicha oddiy holat (yashil/sariq/qizil).
    Chegaralar oddiy, tushunarli qoidalarga asoslangan. Faqat o'qish."""
    from datetime import datetime
    from models import Order

    now = datetime.utcnow()
    report = get_monthly_report(db, now.year, now.month)

    foyda_foiz = float(report.get("foyda_foiz", 0) or 0)
    rentabellik_status = "green" if foyda_foiz >= 15 else ("orange" if foyda_foiz >= 5 else "red")

    orders = db.query(Order).filter(Order.is_deleted.isnot(True)).all()
    total_debt = sum(float(o.debt_amount or 0) for o in orders)
    total_revenue = sum(float(o.agreed_amount or o.total_amount or 0) for o in orders) or 1
    debt_ratio = total_debt / total_revenue * 100
    debt_status = "green" if debt_ratio < 15 else ("orange" if debt_ratio < 30 else "red")

    return {
        "pul_oqimi": "green" if float(report.get("sof_foyda", 0) or 0) >= 0 else "red",
        "ombor": "green",
        "rentabellik": rentabellik_status,
        "qarzdorlik": debt_status,
        "ishlab_chiqarish": "green",
        "material_sarfi": "orange" if float(report.get("naqd_xarajat_jami", 0) or 0) > float(report.get("daromad", 1) or 1) * 0.5 else "green",
    }


def get_recurring_obligations(db: Session) -> list:
    """Barcha sozlangan doimiy majburiyatlar (Arenda, Soliq, Transport va
    ISTALGAN boshqa kategoriya) ro'yxati — sozlash sahifasi uchun."""
    from models import RecurringObligation
    rows = db.query(RecurringObligation).order_by(RecurringObligation.label).all()
    return [{
        "id": r.id, "category": r.category, "label": r.label, "icon": r.icon or "📦",
        "monthly_target": float(r.monthly_target or 0), "due_day": r.due_day or 5,
        "is_active": r.is_active
    } for r in rows]


def set_recurring_obligation(db: Session, category: str, label: str, monthly_target: float,
                              icon: str = "📦", due_day: int = 5) -> dict:
    """Doimiy majburiyat kategoriyasini yaratadi yoki yangilaydi. Admin
    ISTALGAN yangi kategoriya nomini kiritishi mumkin."""
    from models import RecurringObligation
    obl = db.query(RecurringObligation).filter(RecurringObligation.category == category).first()
    if obl:
        obl.label = label
        obl.monthly_target = monthly_target
        obl.icon = icon
        obl.due_day = due_day
    else:
        obl = RecurringObligation(category=category, label=label, monthly_target=monthly_target,
                                   icon=icon, due_day=due_day, is_active=True)
        db.add(obl)
    db.commit()
    db.refresh(obl)
    return {"id": obl.id, "category": obl.category, "label": obl.label, "monthly_target": float(obl.monthly_target)}


def delete_recurring_obligation(db: Session, obligation_id: int) -> bool:
    """Doimiy majburiyat kategoriyasini o'chiradi (xarajat tarixi saqlanib qoladi)."""
    from models import RecurringObligation
    obl = db.query(RecurringObligation).filter(RecurringObligation.id == obligation_id).first()
    if not obl:
        return False
    db.delete(obl)
    db.commit()
    return True


def _obligation_status(debt: float, due_day: int, today) -> str:
    """Holatni avtomatik aniqlaydi: to'liq/qisman/muddat yaqin/muddati o'tgan."""
    if debt <= 0.5:
        return "full"
    if today.day > due_day:
        return "overdue"
    if due_day - today.day <= 3:
        return "due_soon"
    return "partial"


def get_company_obligations_status(db: Session, year: int, month: int) -> dict:
    """Kompaniyaning O'ZI kimlarga qarzdorligini — bitta joyda yig'ib beradi:
    1) Hodimlarga (oylik hisob-kitobdagi 'qolgan')
    2) Doimiy majburiyatlar (Arenda, Soliq, Transport va h.k.)
    Ikkalasi ham — FAQAT o'qish, mavjud, sinalgan hisob-kitoblardan foydalanadi."""
    from models import RecurringObligation, ExpenseTransaction
    from sqlalchemy import func
    from datetime import datetime

    today = datetime.utcnow()

    emp_result = calculate_monthly_employee_pay(db, year, month, 0, 0, 0, 0, 0)
    employees = [
        {
            "employee_id": e["employee_id"], "name": e["name"], "detail": e["detail"],
            "amount": e["amount"], "avans": e["avans"], "qolgan": e["qolgan"],
            "status": "overdue" if (e["qolgan"] > 0.5 and today.day > 5) else ("partial" if e["qolgan"] > 0.5 else "full")
        }
        for e in emp_result["breakdown"]
    ]
    employees_with_debt = [e for e in employees if e["qolgan"] > 0.5]
    total_employee_debt = sum(e["qolgan"] for e in employees_with_debt)

    recurring = []
    obligations = db.query(RecurringObligation).filter(RecurringObligation.is_active == True).all()
    for obl in obligations:
        target = float(obl.monthly_target or 0)
        if target <= 0:
            continue
        txs = db.query(ExpenseTransaction).filter(
            ExpenseTransaction.category == obl.category,
            func.extract('year', ExpenseTransaction.date) == year,
            func.extract('month', ExpenseTransaction.date) == month
        ).order_by(ExpenseTransaction.date.desc()).all()
        paid = sum(float(t.amount or 0) for t in txs)
        debt = max(0, target - paid)
        last_payment = txs[0].date.isoformat() if txs else None

        recurring.append({
            "category": obl.category, "label": obl.label, "icon": obl.icon or "📦",
            "target": round(target), "paid": round(paid), "debt": round(debt),
            "due_day": obl.due_day or 5, "last_payment": last_payment,
            "status": _obligation_status(debt, obl.due_day or 5, today)
        })
    recurring_with_debt = [r for r in recurring if r["debt"] > 0.5]
    total_recurring_debt = sum(r["debt"] for r in recurring_with_debt)

    return {
        "employees": employees_with_debt,
        "total_employee_debt": round(total_employee_debt),
        "recurring": recurring_with_debt,
        "recurring_all": recurring,
        "total_recurring_debt": round(total_recurring_debt),
        "total_company_debt": round(total_employee_debt + total_recurring_debt),
    }


def get_obligation_timeline(db: Session, category: str, year: int, month: int) -> list:
    """Bitta kategoriya uchun, shu oydagi barcha to'lovlar tarixi (timeline)."""
    from models import ExpenseTransaction
    from sqlalchemy import func
    txs = db.query(ExpenseTransaction).filter(
        ExpenseTransaction.category == category,
        func.extract('year', ExpenseTransaction.date) == year,
        func.extract('month', ExpenseTransaction.date) == month
    ).order_by(ExpenseTransaction.date.desc()).all()
    return [{
        "date": t.date.isoformat(), "amount": float(t.amount or 0),
        "notes": t.notes, "created_by": t.created_by
    } for t in txs]


def get_employee_payment_timeline(db: Session, employee_id: int, year: int, month: int) -> list:
    """Bitta hodim uchun, shu oydagi barcha to'lovlar (avans+yakuniy) tarixi."""
    advances = get_employee_advances_list(db, employee_id, year, month)
    return [{"date": a["date"], "amount": a["amount"], "notes": a["notes"] or "Avans/to'lov",
              "created_by": a["given_by"]} for a in advances]


def close_employee_debt(db: Session, employee_id: int, year: int, month: int, amount: float, paid_by: str = None) -> dict:
    """Hodimning shu oydagi qolgan qarzini to'lash — mavjud, sinalgan
    EmployeeAdvance mexanizmining o'zidan foydalanadi (avans va yakuniy
    to'lov — matematik jihatdan bir xil narsa: ikkalasi ham hisoblangan
    oylikdan ayriladi)."""
    from datetime import datetime
    import crud as _crud
    adv_date = datetime(year, month, min(28, datetime.utcnow().day) if (year, month) == (datetime.utcnow().year, datetime.utcnow().month) else 28)
    adv = _crud.create_employee_advance(db, employee_id, amount, notes="Oy oxiri — qolgan oylik to'landi",
                                         given_by=paid_by, adv_date=adv_date)
    return {"success": adv is not None}



    """Bosh sahifadagi 'Bugungi vazifalar' bloki uchun — faqat o'qish,
    mavjud funksiyalardan (get_today_stats, low stock, loyihalar) foydalanadi."""
    from models import Order, OrderStatus, Project, ProjectStatus, Inventory
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    tasks = []

    due_today = db.query(Order).filter(
        Order.deadline >= today_start, Order.deadline < today_end,
        Order.status.notin_([OrderStatus.DELIVERED, OrderStatus.CANCELLED]),
        Order.is_deleted.isnot(True)
    ).count()
    if due_today > 0:
        tasks.append({"level": "red", "icon": "🔴", "text": f"{due_today} ta buyurtma bugun topshirilishi kerak"})

    low_count = db.query(Inventory).filter(
        Inventory.stock_quantity <= Inventory.min_stock, Inventory.min_stock > 0
    ).count()
    if low_count > 0:
        tasks.append({"level": "orange", "icon": "🟡", "text": f"{low_count} ta xomashyo minimal qoldiqdan past"})

    completed_today = db.query(Project).filter(
        Project.completed_at >= today_start, Project.completed_at < today_end,
        Project.status == ProjectStatus.COMPLETED
    ).count()
    if completed_today > 0:
        tasks.append({"level": "green", "icon": "🟢", "text": f"{completed_today} ta loyiha bugun yakunlandi"})

    if not tasks:
        tasks.append({"level": "green", "icon": "✅", "text": "Bugun shoshilinch vazifalar yo'q"})

    return tasks


def get_production_period_stats(db: Session) -> dict:
    """Ishlab chiqarish — bugun/hafta/oy bo'yicha nechta mahsulot chiqqani.
    Faqat o'qish, FinishedProduct.created_at (source=produced) asosida."""
    from models import FinishedProduct, StockSource
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    def _count_since(since):
        items = db.query(FinishedProduct).filter(
            FinishedProduct.source == StockSource.PRODUCED,
            FinishedProduct.created_at >= since
        ).all()
        return round(sum(float(i.quantity or 0) for i in items))

    return {
        "today": _count_since(today_start),
        "week": _count_since(week_start),
        "month": _count_since(month_start),
    }


def get_notifications(db: Session) -> list:
    """Bosh sahifa va butun tizim uchun bildirishnomalar — faqat o'qish.

    Uch turi:
    - 🔴 Xomashyo butunlay tugagan
    - 🟠 Joriy sarf tezligiga qarab, N kun ichida tugashi kutilmoqda
      (InventoryMovement jurnalidagi oxirgi 14 kunlik 'chiqim' asosida)
    - 🟢 Bugun yetkazilgan/tayyor buyurtmalar soni
    """
    from models import Inventory, InventoryMovement, Order, OrderStatus
    from sqlalchemy import func
    from datetime import datetime, timedelta

    notifications = []
    now = datetime.utcnow()

    # ── 🔴 Butunlay tugagan ──────────────────────────────────
    # "Tayyor loy (...)" — bular oddiy xomashyo emas, balki ISHLAB
    # CHIQARISHDAN ORTIB QOLGAN qoldiq (keyingi buyurtmaga ishlatish
    # uchun). Ular ODATDA 0 bo'lib turadi — bu me'yor, muammo emas,
    # shuning uchun bu ogohlantirishlarga kiritilmaydi.
    empty_items = db.query(Inventory).filter(
        Inventory.stock_quantity <= 0,
        ~Inventory.item_name.like('Tayyor loy%')
    ).all()
    for item in empty_items:
        notifications.append({
            "level": "red",
            "icon": "🔴",
            "text": f"{item.item_name} qolmadi",
            "category": "stock_empty",
            "created_at": now.isoformat(),
        })

    # ── 🟠 Sarf tezligiga qarab tugash bashorati ─────────────
    period_start = now - timedelta(days=14)
    items = db.query(Inventory).filter(
        Inventory.stock_quantity > 0,
        ~Inventory.item_name.like('Tayyor loy%')
    ).all()
    for item in items:
        total_out = db.query(func.sum(InventoryMovement.quantity)).filter(
            InventoryMovement.inventory_id == item.id,
            InventoryMovement.movement_type == "out",
            InventoryMovement.created_at >= period_start
        ).scalar()
        total_out = float(total_out or 0)
        if total_out <= 0:
            continue  # Sarf tarixi yo'q — bashorat qilib bo'lmaydi
        daily_rate = total_out / 14
        days_left = float(item.stock_quantity) / daily_rate if daily_rate > 0 else None
        if days_left is not None and days_left <= 7:
            notifications.append({
                "level": "orange",
                "icon": "🟠",
                "text": f"{item.item_name} {max(1, round(days_left))} kundan keyin tugaydi",
                "category": "stock_predicted",
                "created_at": now.isoformat(),
            })

    # ── 🟢 Bugun yetkazilgan/tayyor buyurtmalar ──────────────
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    today_count = db.query(Order).filter(
        Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED]),
        Order.completed_at >= today_start, Order.completed_at < today_end,
        Order.is_deleted.isnot(True)
    ).count()
    if today_count > 0:
        notifications.append({
            "level": "green",
            "icon": "🟢",
            "text": f"Bugun {today_count} ta buyurtma topshirildi",
            "category": "orders_today",
            "created_at": now.isoformat(),
        })

    # Muhimlik bo'yicha: qizil > sariq > yashil
    order_map = {"red": 0, "orange": 1, "green": 2}
    notifications.sort(key=lambda n: order_map.get(n["level"], 9))
    return notifications


def check_low_stock(db: Session) -> List[Dict]:
    """Min qoldiqdan kam bo'lgan xomashyolar ro'yxati.

    Admin dashboardida ko'rsatish uchun.
    """
    low_items = db.query(Inventory).filter(
        Inventory.stock_quantity <= Inventory.min_stock,
        Inventory.min_stock > 0
    ).all()

    result = []
    for item in low_items:
        result.append({
            "id": item.id,
            "item_name": item.item_name,
            "stock_quantity": float(item.stock_quantity),
            "min_stock": float(item.min_stock),
            "unit": item.unit,
            "deficit": float(item.min_stock - item.stock_quantity),
            "alert": "⚠️ Xomashyo yetishmayapti!"
        })

    return result


def get_today_stats(db: Session) -> Dict:
    """Dashboard yuqori qatori uchun 'bugungi kun' statistikasi.

    Barchasi bazadagi haqiqiy yozuvlardan hisoblanadi:
    - Bugungi tushum: bugun qabul qilingan to'lovlar summasi (Payment.paid_at)
    - Ishlab chiqarishda: status = in_progress yoki coating bo'lgan buyurtmalar
    - Bugun topshiriladi: deadline bugunga to'g'ri keladigan, hali yopilmagan buyurtmalar
    - Ishlayotgan ustalar: hozir faol buyurtmasi bor noyob ustalar soni
    - Sof foyda (bugun): bugun yakunlangan (completed_at) buyurtmalar bo'yicha calculate_order_profit yig'indisi
    """
    from models import Order, OrderStatus, Master, Payment
    from sqlalchemy import func
    from datetime import datetime, timedelta

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    today_revenue = db.query(func.sum(Payment.amount)).filter(
        Payment.paid_at >= today_start, Payment.paid_at < today_end
    ).scalar() or 0

    active_orders = db.query(Order).filter(
        Order.status.notin_([OrderStatus.READY, OrderStatus.DELIVERED, OrderStatus.CANCELLED]),
        Order.is_deleted.isnot(True)
    ).count()

    in_production = db.query(Order).filter(
        Order.status.in_([OrderStatus.IN_PROGRESS, OrderStatus.COATING]),
        Order.is_deleted.isnot(True)
    ).count()

    due_today = db.query(Order).filter(
        Order.deadline >= today_start, Order.deadline < today_end,
        Order.status.notin_([OrderStatus.DELIVERED, OrderStatus.CANCELLED]),
        Order.is_deleted.isnot(True)
    ).count()

    active_masters = db.query(Order.master_id).filter(
        Order.master_id.isnot(None),
        Order.status.in_([OrderStatus.NEW, OrderStatus.IN_PROGRESS, OrderStatus.COATING]),
        Order.is_deleted.isnot(True)
    ).distinct().count()

    completed_today = db.query(Order).filter(
        Order.completed_at >= today_start, Order.completed_at < today_end,
        Order.status == OrderStatus.READY,
        Order.is_deleted.isnot(True)
    ).all()
    today_profit = 0.0
    for o in completed_today:
        try:
            p = calculate_order_profit(db, o.id)
            if p.get("success"):
                today_profit += p.get("foyda", 0)
        except Exception:
            db.rollback()

    return {
        "today_revenue": float(today_revenue),
        "active_orders": active_orders,
        "in_production": in_production,
        "due_today": due_today,
        "active_masters": active_masters,
        "today_profit": today_profit,
    }


def get_dashboard_stats(db: Session) -> Dict:
    """Admin dashboard uchun umumiy statistika."""
    from models import Project, Master

    total_projects = db.query(Project).count()
    total_orders = db.query(Order).filter(Order.is_deleted.isnot(True)).count()
    active_orders = db.query(Order).filter(Order.status != OrderStatus.READY, Order.is_deleted.isnot(True)).count()
    ready_orders = db.query(Order).filter(Order.status == OrderStatus.READY, Order.is_deleted.isnot(True)).count()
    total_masters = db.query(Master).filter(Master.is_active == True).count()
    total_inventory_items = db.query(Inventory).count()
    low_stock = check_low_stock(db)

    return {
        "total_projects": total_projects,
        "total_orders": total_orders,
        "active_orders": active_orders,
        "ready_orders": ready_orders,
        "total_masters": total_masters,
        "total_inventory_items": total_inventory_items,
        "low_stock_count": len(low_stock),
        "low_stock_items": low_stock
    }


# ============================================================
# 5. TO'LIQ BUYURTMA YAKUNLASH (Cutting + Coating + KPI)
# ============================================================

def complete_order(db: Session, order_id: int, loy_kg: Optional[float] = None) -> Dict:
    """Buyurtmani to'liq yakunlash — barcha avtomatika:

    1. AVVAL — xomashyo yetarliligini tekshirish
    2. Penoplast bloklarini ayirish (kesish)
    3. Retsept bo'yicha xomashyoni ayirish (qoplama)
    4. Usta KPI hisoblash (3% + 1000/m)
    5. Status -> READY
    """
    from datetime import datetime

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    if order.status == OrderStatus.READY:
        return {"success": False, "message": "Bu buyurtma allaqachon tayyor"}

    # === HAMMA NARSA TAYYOR — BAJARAMIZ ===
    result = {
        "success": True,
        "message": "✓ Buyurtma yakunlandi!",
        "inventory_changes": [],
        "master_kpi": None
    }

    # === LOY HISOB-KITOBI ===
    # Buyurtma yaratilganda rejalashtirilgan loy allaqachon ayirilgan.
    # Endi haqiqiy miqdor bilan solishtiramiz.
    # MUHIM: agar shu buyurtmada Termopanel (bazalt) detali ham bo'lsa, uning
    # rejalashtirilgan loyi ham SHU YAGONA savolga qo'shib hisoblanadi —
    # hodim faqat BITTA umumiy raqam kiritadi.
    import crud as _crud
    order_planned = _get_planned_loy(order)
    termo_planned = _crud.get_termopanel_planned_loy(order)
    planned_loy = order_planned + termo_planned
    actual_loy = float(loy_kg or 0)

    # MUHIM FARQ:
    # - TO'LIQ yakunlashda (yoki hali hech narsa topshirilmagan holatda) —
    #   hodim REJA bo'yicha loy aralashtirgan, ortgani — HAQIQATAN aralashtirilgan,
    #   faqat ishlatilmagan tayyor loy. "Tayyor loy" ombor pozitsiyasiga qo'shiladi.
    # - QISMAN yakunlashda — hodim FAQAT bajargan ishiga yarasha loy tayyorlaydi,
    # rejadagi qolgan qismni umuman ARALASHTIRMAYDI HAM. Demak "ortgan" qism —
    # bu XOM XOMASHYO (Akril, Qum va h.k.), ular o'z joyiga qaytishi kerak,
    # "Tayyor loy" ga emas.
    is_partial_completion = bool(order.deliveries) and not order.is_fully_delivered

    if actual_loy > 0:
        recipe = _get_order_recipe(db, order)
        diff = actual_loy - planned_loy

        if diff > 0.01:
            # Ko'proq ketdi — farq uchun xomashyo ayiramiz (ikkala holatda ham bir xil)
            loy_log = deduct_loy_ingredients(db, order, diff)
            result["inventory_changes"].extend(loy_log)
            result["loy_info"] = {
                "planned": planned_loy,
                "actual": actual_loy,
                "diff": round(diff, 1),
                "action": "qoshimcha",
                "message": f"Rejadan {diff:.1f} kg ko'p ketdi — xomashyo ayirildi"
            }
        elif diff < -0.01:
            extra = abs(diff)
            if is_partial_completion:
                # Aralashtirilmagan — xom xomashyo o'z joyiga qaytadi
                ing_log = return_loy_ingredients(db, order, extra)
                result["inventory_changes"].extend(ing_log)
                result["loy_info"] = {
                    "planned": planned_loy,
                    "actual": actual_loy,
                    "diff": round(diff, 1),
                    "action": "ortdi",
                    "message": f"Qisman yakunlandi — {extra:.1f} kg uchun XOM XOMASHYO (aralashtirilmagan) o'z joyiga qaytdi"
                }
            else:
                # To'liq yakunlangan — haqiqatan aralashtirilgan, tayyor loy sifatida saqlanadi
                msg = add_loy_to_stock(db, recipe, extra)
                if msg:
                    result["inventory_changes"].append(msg)
                result["loy_info"] = {
                    "planned": planned_loy,
                    "actual": actual_loy,
                    "diff": round(diff, 1),
                    "action": "ortdi",
                    "message": f"{extra:.1f} kg loy ortdi — omborga (Tayyor loy) qo'shildi"
                }
        else:
            result["loy_info"] = {
                "planned": planned_loy,
                "actual": actual_loy,
                "diff": 0,
                "action": "teng",
                "message": "Reja bo'yicha ketdi"
            }

        # Termopanel detallarining "reja" belgisini ham — o'z ulushiga qarab —
        # haqiqiy qiymatga yangilaymiz (keyingi audit/tarix uchun to'g'ri saqlansin).
        if termo_planned > 0:
            _crud.settle_termopanel_loy_share(order, planned_loy, actual_loy)
            db.commit()
    elif planned_loy > 0:
        # Haqiqiy miqdor kiritilmadi — reja bo'yicha deb hisoblaymiz
        result["loy_info"] = {
            "planned": planned_loy,
            "actual": planned_loy,
            "diff": 0,
            "action": "teng",
            "message": "Reja bo'yicha hisoblandi"
        }

    # === QISMAN TOPSHIRILGAN HOLATDA YAKUNLASH ===
    # Agar buyurtma ALLAQACHON qisman topshirilgan bo'lsa-yu (masalan 64%),
    # shu holda "Tayyor" bosilsa — bu "qolgani kerak emas, shu bilan yakunlaymiz"
    # degani. Qolgan (topshirilmagan) qism uchun xomashyo omborga qaytadi.
    # (Hali hech narsa topshirilmagan — oddiy holat — bunga tegilmaydi.)
    if is_partial_completion:
        partial_log = return_inventory_for_order_partial(db, order)
        if partial_log:
            result["inventory_changes"].extend(partial_log)
            result["partial_return"] = {
                "delivery_percent": order.delivery_percent,
                "message": f"Qisman topshirilgan ({order.delivery_percent:.0f}%) — qolgan qism uchun xomashyo omborga qaytdi"
            }

        # Buyurtma miqdori/summasi — HAQIQATDA berilgan miqdorga tushiriladi
        fin = _crud.finalize_partial_order_quantities(db, order)
        result["finalized"] = fin
        msg = f"Buyurtma summasi {fin['old_total']:.0f} → {fin['new_total']:.0f} so'mga tushirildi (haqiqatda berilgan miqdorga mos)."
        if fin["overpaid"]:
            msg += f" ⚠️ Mijoz {fin['overpaid']:.0f} so'm ortiqcha to'lagan — QAYTARILISHI kerak!"
        elif fin["debt"] > 0:
            msg += f" Qarz qoldi: {fin['debt']:.0f} so'm."
        else:
            msg += " To'lov to'liq yopilgan."
        result["finalized"]["message"] = msg
    elif not order.deliveries:
        # Hali HECH NARSA topshirilmagan — bu odatiy holat.
        # "Tayyor" bosilishi bilan — mahsulot BIR YO'LA, TO'LIQ topshirilgan deb
        # avtomatik yozib qo'yamiz (alohida "Bir yo'la to'liq topshirish"
        # tugmasini bosish shart emas).
        from schemas import DeliveryCreate, DeliveryItemCreate
        delivery_items = []
        for item in order.items:
            remaining = item.remaining_qty
            if remaining > 0.001:
                delivery_items.append(DeliveryItemCreate(order_item_id=item.id, quantity=remaining))

        if delivery_items:
            dcreate = DeliveryCreate(order_id=order.id, items=delivery_items)
            dres = _crud.create_delivery(db, dcreate, delivered_by="Avtomatik (Tayyor deb belgilashda)")
            if dres.get("success"):
                result["auto_delivery"] = {
                    "delivery_id": dres.get("delivery_id"),
                    "message": "✅ Barcha mahsulot avtomatik ravishda BIR YO'LA topshirilgan deb belgilandi."
                }

    # 3. USTA KPI
    if order.master_id:
        master = db.query(Master).filter(Master.id == order.master_id).first()
        if master:
            cashback = float(order.total_amount) * 0.03
            total_meters = sum(
                (item.length or 0) * item.quantity for item in order.items if item.is_coated
            )
            meter_bonus = total_meters * 1000
            total_kpi = cashback + meter_bonus
            result["master_kpi"] = {
                "master": master.name,
                "cashback_3%": round(cashback),
                "meter_bonus": round(meter_bonus),
                "total_kpi": round(total_kpi),
                "total_meters": total_meters
            }

    # 4. Status yangilash
    order.status = OrderStatus.READY
    order.completed_at = datetime.utcnow()
    # Loy miqdorini notes ga saqlaymiz (foyda hisoblash uchun)
    if loy_kg and loy_kg > 0:
        existing_notes = order.notes or ''
        parts = [p.strip() for p in existing_notes.split(',')
                 if p.strip() and not p.strip().startswith('loy_kg=')]
        parts.append(f'loy_kg={loy_kg}')
        order.notes = ','.join(parts)
    db.commit()
    db.refresh(order)

    return result


def get_inventory_kpi(db: Session) -> Dict:
    """Omborxona sahifasi uchun KPI ko'rsatkichlari — faqat o'qish, hech narsani o'zgartirmaydi."""
    from models import Inventory, InventoryMovement
    from sqlalchemy import func
    from datetime import datetime, timedelta

    items = db.query(Inventory).all()
    total_items = len(items)
    low_count = sum(1 for i in items if float(i.stock_quantity or 0) <= float(i.min_stock or 0))
    total_value = sum(float(i.stock_quantity or 0) * float(i.price_per_unit or 0) for i in items)

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    today_in = db.query(func.count(InventoryMovement.id)).filter(
        InventoryMovement.movement_type == "in",
        InventoryMovement.created_at >= today_start, InventoryMovement.created_at < today_end
    ).scalar() or 0
    today_out = db.query(func.count(InventoryMovement.id)).filter(
        InventoryMovement.movement_type == "out",
        InventoryMovement.created_at >= today_start, InventoryMovement.created_at < today_end
    ).scalar() or 0

    return {
        "total_items": total_items,
        "low_count": low_count,
        "total_value": total_value,
        "today_in_count": today_in,
        "today_out_count": today_out,
    }


def get_low_stock_warnings(db: Session) -> List[Dict]:
    """check_low_stock ning alias — eski kodlarga moslik uchun."""
    return check_low_stock(db)


# ============================================================
# DASHBOARD UCHUN KENGAYTIRILGAN STATISTIKA
# ============================================================

def get_chart_data(db: Session) -> Dict:
    """Dashboard grafiklari uchun ma'lumotlar."""
    from models import Project, Master, Order, OrderItem, OrderStatus
    from sqlalchemy import func
    from datetime import datetime, timedelta

    # --- 1. Oxirgi 6 oylik buyurtmalar soni ---
    months_data = []
    now = datetime.utcnow()
    for i in range(5, -1, -1):
        # Har bir oy boshi va oxiri
        month_start = (now.replace(day=1) - timedelta(days=i*30)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)
        if i == 0:
            month_end = now
        else:
            next_month = month_start.replace(day=28) + timedelta(days=4)
            month_end = next_month.replace(day=1)

        count = db.query(Order).filter(
            Order.created_at >= month_start,
            Order.created_at < month_end,
            Order.is_deleted.isnot(True)
        ).count()

        revenue = db.query(func.sum(Order.total_amount)).filter(
            Order.created_at >= month_start,
            Order.created_at < month_end,
            Order.status == OrderStatus.READY,
            Order.is_deleted.isnot(True)
        ).scalar() or 0

        months_data.append({
            "label": month_start.strftime("%b %Y"),
            "orders": count,
            "revenue": float(revenue)
        })

    # --- 2. Buyurtma holatlari (donut chart) ---
    statuses = {}
    for status in OrderStatus:
        try:
            cnt = db.query(Order).filter(Order.status == status, Order.is_deleted.isnot(True)).count()
            statuses[status.value] = cnt
        except Exception:
            # Enum bazada hali yo'q bo'lsa
            db.rollback()
            statuses[status.value] = 0

    # --- 3. Ustalar KPI (top 5) ---
    masters = db.query(Master).filter(Master.is_active == True).all()
    master_kpi = []
    for m in masters:
        total = db.query(func.sum(Order.total_amount)).filter(
            Order.master_id == m.id,
            Order.status == OrderStatus.READY,
            Order.is_deleted.isnot(True)
        ).scalar() or 0
        order_count = db.query(Order).filter(
            Order.master_id == m.id,
            Order.is_deleted.isnot(True)
        ).count()
        master_kpi.append({
            "name": m.name,
            "total": float(total),
            "orders": order_count
        })
    # Eng ko'p ishlagani birinchi
    master_kpi.sort(key=lambda x: x["total"], reverse=True)
    master_kpi = master_kpi[:5]

    # --- 4. Umumiy moliyaviy ko'rsatkichlar ---
    total_revenue = db.query(func.sum(Order.total_amount)).filter(
        Order.status == OrderStatus.READY
    ).scalar() or 0

    total_paid = db.query(func.sum(Project.total_paid)).scalar() or 0
    total_budget = db.query(func.sum(Project.total_budget)).scalar() or 0
    total_debt = float(total_budget) - float(total_paid)

    # --- 5. Omborxona holati (top yetishmayotganlar) ---
    low_stock = check_low_stock(db)

    return {
        "months": months_data,
        "statuses": statuses,
        "master_kpi": master_kpi,
        "finance": {
            "total_revenue": float(total_revenue),
            "total_paid": float(total_paid),
            "total_budget": float(total_budget),
            "total_debt": max(0, total_debt)
        },
        "low_stock": low_stock[:5]
    }


# ============================================================
# BUYURTMA FOYDA VA TAN NARXI HISOBLASH (faqat Admin uchun)
# ============================================================

def calculate_order_profit(db: Session, order_id: int) -> Dict:
    """
    Buyurtma uchun tan narxi va foyda hisoblaydi.

    Tan narxi = Penoplast xarajati + Qoplama xomashyosi xarajati
    Foyda = Sotuv narxi - Tan narxi
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    # Kelishilgan (chegirmadan keyingi, haqiqatan mijoz to'laydigan) summadan
    # hisoblanadi — shunda har qanday chegirma (boshidagi ham, keyin
    # "kechirilgan" ham) foyda hisobotida to'g'ri, avtomatik hisobga olinadi.
    sotuv_narxi = float(order.agreed_amount or order.total_amount or 0)
    breakdown = []
    tan_narxi_jami = 0.0

    # ── 1. PENOPLAST XARAJATI ────────────────────────────────
    penoplast = db.query(Inventory).filter(
        Inventory.item_name.ilike("%penoplast%")
    ).first()

    total_volume_m3 = 0.0
    for item in order.items:
        cat = (item.category or '').lower()
        qty = float(item.quantity or 1)

        if cat == 'profil':
            if item.width and item.thickness and item.length:
                # Profil: /2 bilan (narx formulasi bilan bir xil)
                vol = (item.width/100) * (item.thickness/100) / 2 * float(item.length)
                total_volume_m3 += vol

        elif cat == 'panel':
            if item.width and item.thickness:
                # JS bilan bir xil: Eni(m) × Qalinlik(m) × Miqdor
                vol = (item.width/100) * (item.thickness/100) * qty
                total_volume_m3 += vol

        elif cat == 'dona':
            if item.unit_price and float(item.unit_price) > 0:
                p = db.query(Inventory).filter(
                    Inventory.item_name.ilike("%penoplast%")
                ).first()
                if p and p.price_per_unit and p.volume_per_unit:
                    narx_per_m3 = float(p.price_per_unit) / float(p.volume_per_unit)
                    if narx_per_m3 > 0:
                        vol = float(item.unit_price) / narx_per_m3 * qty
                        total_volume_m3 += vol

    penoplast_xarajat = 0.0
    if penoplast and penoplast.price_per_unit and total_volume_m3 > 0:
        # 1 m³ narxi = 1 blok narxi ÷ 1 blok hajmi (m³)
        volume_per_unit = float(penoplast.volume_per_unit or 1.0)
        narx_per_m3 = float(penoplast.price_per_unit) / volume_per_unit
        penoplast_xarajat = total_volume_m3 * narx_per_m3
        breakdown.append({
            "nomi": f"Penoplast ({total_volume_m3:.2f} m³ × {narx_per_m3:,.0f} so'm/m³)",
            "summa": penoplast_xarajat
        })
        tan_narxi_jami += penoplast_xarajat

    # ── 2. QOPLAMA XOMASHYOSI XARAJATI ──────────────────────
    coated_items = [i for i in order.items if i.is_coated]
    if coated_items:
        # Loy miqdorini order.notes dan olamiz (tayyor bosilganda saqlangan)
        loy_kg = 0.0
        if order.notes:
            try:
                for part in order.notes.split(','):
                    p = part.strip()
                    if p.startswith('loy_kg='):
                        loy_kg = float(p.split('=')[1].strip())
                        break
            except:
                pass

        # Agar loy_kg saqlanmagan bo'lsa — 2 kg/m² dan hisoblash
        if loy_kg <= 0:
            for item in coated_items:
                if item.width and item.length:
                    perimetr_m = (item.width * 2 + (item.thickness or item.width) * 2) / 100
                    loy_kg += perimetr_m * (item.length or 1) * float(item.quantity or 1) * 2.0

        # Retsept bo'yicha 1 kg loy narxi
        recipe = None
        for item in order.items:
            if item.recipe_id:
                recipe = db.query(Recipe).filter(Recipe.id == item.recipe_id).first()
                break

        if recipe and loy_kg > 0:
            batch = float(recipe.batch_size_kg or 100)
            narx_per_kg = 0.0
            for ing in recipe.ingredients:
                mat_kg = float(ing.quantity_kg or 0)
                if mat_kg <= 0 or not ing.inventory or not ing.inventory.price_per_unit:
                    continue
                narx_per_kg += (mat_kg / batch) * float(ing.inventory.price_per_unit)

            qoplama_xarajat = loy_kg * narx_per_kg
            if qoplama_xarajat > 0:
                breakdown.append({
                    "nomi": f"Qoplama ({loy_kg:.1f} kg loy × {narx_per_kg:,.0f} so'm/kg)",
                    "summa": qoplama_xarajat
                })
                tan_narxi_jami += qoplama_xarajat

    # ── 3. USTA HAQI (cashback% — foydadan) ─────────────────
    usta_haqi = 0.0
    if order.master and order.master.cashback_percent > 0:
        # Avval foydani hisoblaymiz (tan narxisiz)
        foyda_before_usta = sotuv_narxi - tan_narxi_jami
        usta_haqi = max(0, foyda_before_usta * order.master.cashback_percent / 100)
        breakdown.append({
            "nomi": f"Usta haqi ({order.master.name}, {order.master.cashback_percent}% foydadan)",
            "summa": usta_haqi
        })
        tan_narxi_jami += usta_haqi

    # ── 4. NATIJA ────────────────────────────────────────────
    foyda = sotuv_narxi - tan_narxi_jami
    foyda_foiz = (foyda / sotuv_narxi * 100) if sotuv_narxi > 0 else 0

    return {
        "success": True,
        "order_number": order.order_number,
        "sotuv_narxi": sotuv_narxi,
        "tan_narxi": tan_narxi_jami,
        "foyda": foyda,
        "foyda_foiz": round(foyda_foiz, 1),
        "breakdown": breakdown,
        "volume_m3": round(total_volume_m3, 3),
    }


# ============================================================
# OYLIK HISOBOT
# ============================================================

def get_daily_finance_summary(db: Session, target_date) -> Dict:
    """Bitta kun uchun to'liq moliyaviy ko'rinish:
    - Savdo (shu kun 'Tayyor' bo'lgan buyurtmalar): sotuv, tan narx, foyda
    - Xarajat: xomashyo xaridi (nimaga qancha) + boshqa xarajatlar (nimaga qancha)
    """
    from models import InventoryPurchase, ExpenseTransaction
    from datetime import datetime as dt, timedelta

    start = dt.combine(target_date, dt.min.time())
    end = start + timedelta(days=1)

    # ── 1) SAVDO — shu kun yakunlangan buyurtmalar ──
    orders_today = db.query(Order).filter(
        Order.completed_at >= start,
        Order.completed_at < end,
        Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED]),
        Order.is_deleted.isnot(True)
    ).all()

    total_sales = 0.0
    total_cost = 0.0
    for o in orders_today:
        p = calculate_order_profit(db, o.id)
        if p.get("success"):
            total_sales += p["sotuv_narxi"]
            total_cost += p["tan_narxi"]
    total_profit = total_sales - total_cost

    # ── 2) XARAJAT — xomashyo xaridi (nimaga qancha) ──
    purchases_today = db.query(InventoryPurchase).filter(
        InventoryPurchase.purchased_at >= start,
        InventoryPurchase.purchased_at < end
    ).all()
    material_total = sum(float(p.total_amount or 0) for p in purchases_today)
    material_breakdown = {}
    for p in purchases_today:
        material_breakdown[p.item_name] = material_breakdown.get(p.item_name, 0.0) + float(p.total_amount or 0)

    # ── 3) XARAJAT — boshqa (arenda, elektr va h.k.) ──
    other_today = db.query(ExpenseTransaction).filter(
        ExpenseTransaction.date >= start,
        ExpenseTransaction.date < end
    ).all()
    other_total = sum(float(e.amount or 0) for e in other_today)
    other_breakdown = {}
    for e in other_today:
        other_breakdown[e.category] = other_breakdown.get(e.category, 0.0) + float(e.amount or 0)

    # ── 4) XARAJAT — transport (kompaniya o'z zimmasiga olgan yetkazish xarajati) ──
    from models import Delivery
    deliveries_today = db.query(Delivery).filter(
        Delivery.delivered_at >= start,
        Delivery.delivered_at < end,
        Delivery.transport_cost > 0
    ).all()
    transport_total = sum(d.company_transport_cost for d in deliveries_today)

    total_expense = material_total + other_total + transport_total

    return {
        "date": target_date.isoformat(),
        "sales": {
            "orders_count": len(orders_today),
            "total": round(total_sales),
            "cost": round(total_cost),
            "profit": round(total_profit),
        },
        "expenses": {
            "total": round(total_expense),
            "material": {
                "total": round(material_total),
                "breakdown": [{"nomi": k, "summa": round(v)} for k, v in sorted(material_breakdown.items(), key=lambda x: -x[1])]
            },
            "transport": {
                "total": round(transport_total)
            },
            "other": {
                "total": round(other_total),
                "breakdown": [{"nomi": k, "summa": round(v)} for k, v in sorted(other_breakdown.items(), key=lambda x: -x[1])]
            }
        }
    }


def get_finance_history(db: Session, months_count: int = 12) -> list:
    """Oxirgi N oy uchun moliyaviy tarix — grafik va 'Xarajatlar tarixi' jadvali uchun.
    MUHIM: hech qanday yangi hisob-kitob yo'q — faqat mavjud get_monthly_report()
    funksiyasini har oy uchun alohida chaqiradi va natijalarni ro'yxatga yig'adi."""
    from datetime import datetime

    today = datetime.utcnow()
    y, m = today.year, today.month
    history = []
    for i in range(months_count):
        yy, mm = y, m - i
        while mm <= 0:
            mm += 12
            yy -= 1
        try:
            rep = get_monthly_report(db, yy, mm)
            rep["year"] = yy
            rep["month"] = mm
            history.append(rep)
        except Exception:
            continue
    return list(reversed(history))  # eskisidan yangisiga


def _monthly_category_amount(db: Session, year: int, month: int, category: str, fallback: float) -> float:
    """Berilgan oy/kategoriya uchun ExpenseTransaction yig'indisini qaytaradi.

    Agar shu oy/kategoriya uchun BIRON-BIR tranzaksiya bo'lsa — ularning yig'indisi qaytadi
    (bu — SaaS uchun yangi, tranzaksiya-asosidagi hisoblash).
    Agar tranzaksiya UMUMAN topilmasa (masalan, bu funksiya qo'shilishidan oldingi eski oy) —
    eski `fallback` qiymati (MonthlyExpense'dan) qaytadi. Shu tariqa hech qanday eski
    hisobot o'zgarmaydi, faqat yangi tranzaksiyalar mavjud bo'lgan oylar aniqroq hisoblanadi.
    """
    from models import ExpenseTransaction
    from sqlalchemy import func, extract
    try:
        exists = db.query(ExpenseTransaction.id).filter(
            extract('year', ExpenseTransaction.date) == year,
            extract('month', ExpenseTransaction.date) == month,
            ExpenseTransaction.category == category
        ).first()
        if not exists:
            return float(fallback or 0)
        total = db.query(func.sum(ExpenseTransaction.amount)).filter(
            extract('year', ExpenseTransaction.date) == year,
            extract('month', ExpenseTransaction.date) == month,
            ExpenseTransaction.category == category
        ).scalar()
        return float(total or 0)
    except Exception:
        return float(fallback or 0)


def get_monthly_report(db: Session, year: int, month: int) -> Dict:
    """
    Berilgan oy uchun to'liq moliyaviy hisobot:
    Daromad - Xarajatlar = Sof foyda
    """
    from models import Order, OrderStatus, MonthlyExpense, OrderItem
    from sqlalchemy import func, extract
    from datetime import datetime

    # ── 1. DAROMAD va SOF FOYDA (tayyor buyurtmalar) ────────
    ready_orders = db.query(Order).filter(
        Order.status == OrderStatus.READY,
        extract('year',  Order.completed_at) == year,
        extract('month', Order.completed_at) == month,
        Order.is_deleted.isnot(True)
    ).all()

    daromad = sum(float(o.total_amount or 0) for o in ready_orders)
    buyurtmalar_soni = len(ready_orders)

    # Har buyurtma uchun foyda hisoblaymiz
    ishlab_chiqarish_xarajat = 0.0
    for order in ready_orders:
        try:
            profit_data = calculate_order_profit(db, order.id)
            ishlab_chiqarish_xarajat += float(profit_data.get("tan_narxi", 0))
        except:
            pass

    sof_daromad = daromad - ishlab_chiqarish_xarajat

    # ── 2. QOPLAMACHI BONUS hisoblash ───────────────────────
    # Profil/karniz → uzunlik (metr) × miqdor × 1000 so'm
    # Panel/boshqa  → miqdor × 1000 so'm
    orders_this_month = db.query(Order).filter(
        Order.status == OrderStatus.READY,
        extract('year',  Order.completed_at) == year,
        extract('month', Order.completed_at) == month,
        Order.is_deleted.isnot(True)
    ).all()

    jami_metr = 0.0   # Profil uchun (metr)
    jami_panel_metr = 0.0  # Panel uchun (metr)
    jami_dona = 0.0   # Donali uchun (dona)

    for order in orders_this_month:
        for item in order.items:
            if not item.is_coated:
                continue
            category = (item.category or "").lower()
            if category in ["profil", "karniz"]:
                # Profil: uzunlik (m) × miqdor
                uzunlik_m = float(item.length or 0)
                jami_metr += uzunlik_m * float(item.quantity or 1)
            elif category == "panel":
                # Panel: eni (m) × miqdor
                uzunlik_m = float(item.length or 0)
                jami_panel_metr += uzunlik_m * float(item.quantity or 1)
            else:
                # Donali
                jami_dona += float(item.quantity or 1)

    qoplamachi_bonus_avtomatik = (jami_metr + jami_panel_metr + jami_dona) * 1000
    jami_m2 = jami_metr + jami_panel_metr

    # Jami ishlatilgan blok (hodim to'lovi "per_unit: blok" uchun)
    jami_blok = 0.0
    default_p = get_default_penoplast(db)
    for order in orders_this_month:
        for item in order.items:
            if getattr(item, 'finished_product_id', None):
                continue
            vol = _item_volume_m3(db, item, default_p)
            pid = item.penoplast_id or (default_p.id if default_p else None)
            p = db.query(Inventory).filter(Inventory.id == pid).first() if pid else None
            if p and p.volume_per_unit:
                jami_blok += vol / float(p.volume_per_unit)

    from models import FinishedProduct, StockSource
    from datetime import datetime as _dt
    fp_start = _dt(year, month, 1)
    fp_end = _dt(year + 1, 1, 1) if month == 12 else _dt(year, month + 1, 1)
    finished_this_month = db.query(FinishedProduct).filter(
        FinishedProduct.source == StockSource.PRODUCED,
        FinishedProduct.created_at >= fp_start,
        FinishedProduct.created_at < fp_end
    ).all()
    for fp in finished_this_month:
        if fp.penoplast_id and fp.volume_m3:
            p = db.query(Inventory).filter(Inventory.id == fp.penoplast_id).first()
            if p and p.volume_per_unit:
                jami_blok += float(fp.volume_m3) / float(p.volume_per_unit)

    # ── 3. XARAJATLAR (bazadan) ──────────────────────────────
    expense = db.query(MonthlyExpense).filter(
        MonthlyExpense.year  == year,
        MonthlyExpense.month == month
    ).first()

    if not expense:
        # Bo'sh xarajat
        xarajatlar = {
            "arenda": 0, "elektr": 0, "tushlik": 0, "soliqlar": 0,
            "hodim1_ism": "Hodim 1", "hodim1_oylik": 0,
            "hodim2_ism": "Hodim 2", "hodim2_oylik": 0,
            "hodim3_ism": "Hodim 3", "hodim3_oylik": 0,
            "qoplamachi_ism": "Qoplamachi", "qoplamachi_oylik": 0,
            "qoplamachi_bonus": qoplamachi_bonus_avtomatik,
            "notes": ""
        }
    else:
        xarajatlar = {
            "arenda":    float(expense.arenda or 0),
            "elektr":    float(expense.elektr or 0),
            "tushlik":   float(expense.tushlik or 0),
            "soliqlar":  float(expense.soliqlar or 0),
            "hodim1_ism":   expense.hodim1_ism,
            "hodim1_oylik": float(expense.hodim1_oylik or 0),
            "hodim2_ism":   expense.hodim2_ism,
            "hodim2_oylik": float(expense.hodim2_oylik or 0),
            "hodim3_ism":   expense.hodim3_ism,
            "hodim3_oylik": float(expense.hodim3_oylik or 0),
            "qoplamachi_ism":   expense.qoplamachi_ism,
            "qoplamachi_oylik": float(expense.qoplamachi_oylik or 0),
            "qoplamachi_bonus": float(expense.qoplamachi_bonus or qoplamachi_bonus_avtomatik),
            "notes": expense.notes or ""
        }

    # ── YANGI: mavjud bo'lsa, ExpenseTransaction yig'indisidan olamiz;
    # aks holda yuqoridagi (MonthlyExpense'dan) qiymat saqlanadi (orqaga moslik) ──
    xarajatlar["arenda"]   = _monthly_category_amount(db, year, month, "arenda",   xarajatlar["arenda"])
    xarajatlar["elektr"]   = _monthly_category_amount(db, year, month, "elektr",   xarajatlar["elektr"])
    xarajatlar["tushlik"]  = _monthly_category_amount(db, year, month, "tushlik",  xarajatlar["tushlik"])
    xarajatlar["soliqlar"] = _monthly_category_amount(db, year, month, "soliqlar", xarajatlar["soliqlar"])

    # ── 4a2. YANGI (moslashuvchan) kategoriyalar — Reklama, Kutilmagan xarajat
    # va h.k. — bular MonthlyExpense'da "qattiq" maydon sifatida yo'q,
    # shuning uchun ExpenseTransaction'dan TO'G'RIDAN-TO'G'RI, dinamik yig'ib olinadi.
    from models import ExpenseTransaction
    from sqlalchemy import func as _func, extract as _extract
    KNOWN_FIXED_CATEGORIES = {"arenda", "elektr", "tushlik", "soliqlar"}
    extra_rows = db.query(
        ExpenseTransaction.category, _func.sum(ExpenseTransaction.amount)
    ).filter(
        _extract('year', ExpenseTransaction.date) == year,
        _extract('month', ExpenseTransaction.date) == month,
        ~ExpenseTransaction.category.in_(KNOWN_FIXED_CATEGORIES)
    ).group_by(ExpenseTransaction.category).all()
    qoshimcha_xarajatlar = {cat: float(total or 0) for cat, total in extra_rows}
    qoshimcha_xarajat_jami = sum(qoshimcha_xarajatlar.values())

    # Jami xarajat (arenda/elektr/tushlik/soliq/reklama/kutilmagan va h.k. — hodim
    # to'lovi endi "Ustalar KPI / Hodimlar" bo'limida alohida hisoblanadi)
    jami_xarajat_eski = (
        xarajatlar["arenda"] +
        xarajatlar["elektr"] +
        xarajatlar["tushlik"] +
        xarajatlar["soliqlar"] +
        qoshimcha_xarajat_jami
    )

    # ── 4b. USTA YILLIK KPI (oylik ulush) ─────────────────────
    kpi_result = calculate_monthly_master_kpi(db, year, month)
    usta_kpi_xarajat = kpi_result["total"]

    # ── 4c. MOSLASHUVCHAN HODIMLAR ─────────────────────────────
    # Foyda (hodim xarajatigacha) — sotuvdan% / foydadan% hisoblash uchun
    sof_foyda_before_emp = sof_daromad - jami_xarajat_eski - usta_kpi_xarajat
    emp_result = calculate_monthly_employee_pay(
        db, year, month, daromad, sof_foyda_before_emp,
        jami_metr + jami_panel_metr, jami_dona, jami_blok,
        jami_qoplama_birlik=jami_metr + jami_panel_metr + jami_dona
    )
    hodimlar_moslashuvchan_xarajat = emp_result["total"]
    jami_xarajat = jami_xarajat_eski + usta_kpi_xarajat + hodimlar_moslashuvchan_xarajat

    sof_foyda = sof_daromad - jami_xarajat
    foyda_foiz = (sof_foyda / daromad * 100) if daromad > 0 else 0

    # ── 5. NAQD XARAJATLAR (xomashyo xaridi + transport) ─────
    # Diqqat: bu "ishlab_chiqarish_xarajat" dan FARQ QILADI —
    # u shu oy TUGAGAN buyurtmalarga sarflangan xomashyo tan narxi,
    # bu esa shu oy SOTIB OLINGAN xomashyo puli (hali ishlatilmagan bo'lishi mumkin).
    purchase_stats = get_purchase_stats_for_period(db, year, month)
    transport_stats = get_transport_stats_for_period(db, year, month)

    xomashyo_xaridi = purchase_stats["total_amount"]
    transport_kirish = transport_stats["inbound_total"]
    transport_chiqish = transport_stats["outbound_company"]
    naqd_xarajat_jami = xomashyo_xaridi + transport_kirish + transport_chiqish

    return {
        "year": year,
        "month": month,
        "month_name": [
            "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
            "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"
        ][month],
        "daromad": daromad,
        "ishlab_chiqarish_xarajat": ishlab_chiqarish_xarajat,
        "sof_daromad": sof_daromad,
        "buyurtmalar_soni": buyurtmalar_soni,
        "jami_m2": round(jami_m2, 2),
        "jami_metr": round(jami_metr, 2),
        "jami_dona": int(jami_dona),
        "qoplamachi_bonus_avtomatik": qoplamachi_bonus_avtomatik,
        "xarajatlar": xarajatlar,
        "qoshimcha_xarajatlar": qoshimcha_xarajatlar,
        "hodimlar_breakdown": emp_result["breakdown"],
        "jami_xarajat": jami_xarajat,
        "sof_foyda": sof_foyda,
        "foyda_foiz": round(foyda_foiz, 1),
        "expense_id": expense.id if expense else None,
        # Usta yillik KPI (oylik ulush)
        "usta_kpi_xarajat": usta_kpi_xarajat,
        "usta_kpi_breakdown": kpi_result["breakdown"],
        # Moslashuvchan hodimlar
        "hodimlar_moslashuvchan_xarajat": hodimlar_moslashuvchan_xarajat,
        "hodimlar_moslashuvchan_breakdown": emp_result["breakdown"],
        "jami_blok": round(jami_blok, 2),
        # Naqd xarajatlar (alohida ko'rsatkich — foyda hisobiga kirmaydi)
        "xomashyo_xaridi": xomashyo_xaridi,
        "xomashyo_by_material": purchase_stats["by_material"],
        "transport_kirish": transport_kirish,
        "transport_chiqish_company": transport_chiqish,
        "naqd_xarajat_jami": naqd_xarajat_jami,
    }


def get_purchase_stats_for_period(db: Session, year: int, month: int) -> dict:
    """Berilgan oy uchun xomashyo xaridi statistikasi."""
    from models import InventoryPurchase
    from datetime import datetime as dt

    start = dt(year, month, 1)
    end = dt(year + 1, 1, 1) if month == 12 else dt(year, month + 1, 1)

    purchases = db.query(InventoryPurchase).filter(
        InventoryPurchase.purchased_at >= start,
        InventoryPurchase.purchased_at < end
    ).all()

    by_material = {}
    total = 0.0
    for p in purchases:
        key = p.item_name
        if key not in by_material:
            by_material[key] = {"name": key, "quantity": 0.0, "total": 0.0, "unit": p.unit}
        by_material[key]["quantity"] += float(p.quantity)
        by_material[key]["total"] += float(p.total_amount)
        total += float(p.total_amount)

    items = sorted(by_material.values(), key=lambda x: x["total"], reverse=True)
    for it in items:
        it["total"] = round(it["total"])

    return {"total_amount": round(total), "by_material": items}


def get_transport_stats_for_period(db: Session, year: int, month: int) -> dict:
    """Berilgan oy uchun transport xarajatlari."""
    from models import TransportExpense, Delivery
    from datetime import datetime as dt

    start = dt(year, month, 1)
    end = dt(year + 1, 1, 1) if month == 12 else dt(year, month + 1, 1)

    inbound = db.query(TransportExpense).filter(
        TransportExpense.expense_date >= start,
        TransportExpense.expense_date < end
    ).all()
    inbound_total = sum(float(e.amount) for e in inbound)

    deliveries = db.query(Delivery).filter(
        Delivery.delivered_at >= start,
        Delivery.delivered_at < end,
        Delivery.transport_cost > 0
    ).all()
    outbound_company = sum(d.company_transport_cost for d in deliveries)

    return {
        "inbound_total": round(inbound_total),
        "outbound_company": round(outbound_company),
    }


def save_monthly_expense(db: Session, year: int, month: int, data: dict, performed_by: Optional[str] = None):
    """Oylik xarajatlarni saqlaydi yoki yangilaydi.

    O'ZGARMAGAN: MonthlyExpense jadvaliga yozish — bu hech qanday o'zgarishsiz,
    avvalgi holatidek ishlaydi (backward compatibility).

    YANGI (qo'shimcha): shu bilan bir vaqtda 4 ta asosiy kategoriya
    (arenda/elektr/tushlik/soliqlar) uchun ExpenseTransaction yozuvlari ham
    sinxronlanadi — bu get_monthly_report() endi shu tranzaksiyalardan
    hisoblashi uchun kerak. Faqat 'monthly_form' manbali eski tranzaksiyalar
    almashtiriladi — qo'lda kiritilgan tranzaksiyalarga tegilmaydi.
    """
    from models import MonthlyExpense, ExpenseTransaction
    from sqlalchemy import extract
    from datetime import datetime as _datetime

    expense = db.query(MonthlyExpense).filter(
        MonthlyExpense.year  == year,
        MonthlyExpense.month == month
    ).first()

    if not expense:
        expense = MonthlyExpense(year=year, month=month)
        db.add(expense)

    expense.arenda   = data.get("arenda", 0)
    expense.elektr   = data.get("elektr", 0)
    expense.tushlik  = data.get("tushlik", 0)
    expense.soliqlar = data.get("soliqlar", 0)
    expense.hodim1_ism    = data.get("hodim1_ism", "Hodim 1")
    expense.hodim1_oylik  = data.get("hodim1_oylik", 0)
    expense.hodim2_ism    = data.get("hodim2_ism", "Hodim 2")
    expense.hodim2_oylik  = data.get("hodim2_oylik", 0)
    expense.hodim3_ism    = data.get("hodim3_ism", "Hodim 3")
    expense.hodim3_oylik  = data.get("hodim3_oylik", 0)
    expense.qoplamachi_ism    = data.get("qoplamachi_ism", "Qoplamachi")
    expense.qoplamachi_oylik  = data.get("qoplamachi_oylik", 0)
    expense.qoplamachi_bonus  = data.get("qoplamachi_bonus", 0)
    expense.notes = data.get("notes", "")

    db.commit()
    db.refresh(expense)

    # ── YANGI: ExpenseTransaction sinxronlash (xato bo'lsa ham asosiy saqlashga ta'sir qilmasin) ──
    try:
        tx_date = _datetime(year, month, 1)
        for cat in ("arenda", "elektr", "tushlik", "soliqlar"):
            amount = data.get(cat, 0) or 0
            # Avvalgi 'monthly_form' manbali tranzaksiyani o'chirib, yangisini yozamiz
            db.query(ExpenseTransaction).filter(
                extract('year', ExpenseTransaction.date) == year,
                extract('month', ExpenseTransaction.date) == month,
                ExpenseTransaction.category == cat,
                ExpenseTransaction.source == "monthly_form"
            ).delete(synchronize_session=False)
            if amount > 0:
                db.add(ExpenseTransaction(
                    date=tx_date, category=cat, amount=amount,
                    notes=data.get("notes") or None,
                    created_by=performed_by, source="monthly_form"
                ))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"⚠️ ExpenseTransaction sinxronlashda xato (asosiy saqlash bajarildi): {e}")

    return expense


# ============================================================
# BUYURTMA SAQLASHDA OMBOR TEKSHIRUVI VA AYIRISH
# ============================================================

def get_bazalt_list(db: Session):
    """Barcha bazalt (plotnost/qalinlik) turlari — nomi bo'yicha aniqlanadi,
    xuddi penoplast kabi. Kirim qilishda nomiga 'bazalt' so'zini qo'shish kifoya."""
    from models import Inventory
    items = db.query(Inventory).filter(
        Inventory.item_name.ilike("%bazalt%"),
        Inventory.is_deleted.isnot(True)
    ).order_by(Inventory.item_name).all()
    return items


def get_default_bazalt(db: Session):
    """Asosiy bazalt turi — birinchi topilgani (ID bo'yicha)."""
    from models import Inventory
    return db.query(Inventory).filter(
        Inventory.item_name.ilike("%bazalt%"),
        Inventory.is_deleted.isnot(True)
    ).order_by(Inventory.id).first()


def find_kley(db: Session, lock: bool = False):
    """Kleyni avtomatik topadi — omborda faqat bitta turi bo'ladi deb hisoblanadi.
    volume_per_unit maydonida '1 m² serpiyankaga necha kg kley ketishi' saqlanadi —
    Omborxonada bu qiymatni tahrirlasangiz, tizim darhol yangisidan hisoblaydi."""
    from models import Inventory
    q = db.query(Inventory).filter(Inventory.item_name.ilike("%kley%"), Inventory.is_deleted.isnot(True))
    if lock:
        q = q.with_for_update()
    return q.first()


def find_serpiyanka(db: Session, lock: bool = False):
    """Serpiyankani avtomatik topadi — omborda faqat bitta turi bo'ladi
    deb hisoblanadi (Kley kabi), shuning uchun tanlash shart emas."""
    from models import Inventory
    q = db.query(Inventory).filter(Inventory.item_name.ilike("%serpiyank%"), Inventory.is_deleted.isnot(True))
    if lock:
        q = q.with_for_update()
    return q.first()


def get_penoplast_list(db: Session):
    """Barcha penoplast (plotnost) turlari."""
    from models import Inventory
    from sqlalchemy import or_
    try:
        items = db.query(Inventory).filter(
            or_(
                Inventory.is_penoplast == True,
                Inventory.item_name.ilike("%penoplast%")
            ),
            Inventory.is_deleted.isnot(True)
        ).order_by(Inventory.item_name).all()
        return items
    except Exception:
        db.rollback()
        return db.query(Inventory).filter(
            Inventory.item_name.ilike("%penoplast%")
        ).all()


def get_default_penoplast(db: Session):
    """Asosiy plotnost."""
    from models import Inventory
    p = db.query(Inventory).filter(
        Inventory.is_penoplast == True,
        Inventory.is_default_penoplast == True,
        Inventory.is_deleted.isnot(True)
    ).first()
    if p:
        return p
    p = db.query(Inventory).filter(Inventory.is_penoplast == True, Inventory.is_deleted.isnot(True)).first()
    if p:
        return p
    return db.query(Inventory).filter(
        Inventory.item_name.ilike("%penoplast%"), Inventory.is_deleted.isnot(True)
    ).first()


def _item_volume_m3(db, item, default_penoplast=None) -> float:
    """Bitta detalning hajmini (m³) hisoblaydi.

    Donali mahsulot uchun:
        hajm = (1 dona narxi ÷ 1 m³ sotuv narxi) × miqdor
    unit_price — QOPLAMASIZ narx (qoplama hajmga ta'sir qilmaydi).
    """
    from models import Inventory

    # Tayyor mahsulotdan olingan — xomashyo hisoblanmaydi
    if getattr(item, 'finished_product_id', None):
        return 0.0

    cat = (item.category or '').lower()
    qty = float(item.quantity or 1)

    if cat == 'profil':
        if item.width and item.thickness and item.length:
            return (item.width/100) * (item.thickness/100) / 2 * float(item.length)
    elif cat == 'panel':
        if item.width and item.thickness:
            return (item.width/100) * (item.thickness/100) * qty
    elif cat == 'dona':
        unit_price = float(item.unit_price or 0)
        if unit_price <= 0:
            return 0.0

        # 1 m³ sotuv narxi — detalda saqlangan bo'lsa shuni olamiz
        price_m3 = float(getattr(item, 'price_per_m3', None) or 0)

        # Bo'lmasa — buyurtmadagi boshqa detallardan, oxirida penoplast tan narxidan
        if price_m3 <= 0:
            pid = getattr(item, 'penoplast_id', None)
            p = db.query(Inventory).filter(Inventory.id == pid).first() if pid else default_penoplast
            if p and p.price_per_unit and p.volume_per_unit:
                # Tan narxi: blok narxi ÷ blok hajmi = 1 m³ tan narxi
                price_m3 = float(p.price_per_unit) / float(p.volume_per_unit)

        if price_m3 <= 0:
            return 0.0

        return (unit_price / price_m3) * qty

    elif cat == 'blok':
        # Butun blok evaziga hisoblanadi. quantity = blokdan CHIQQAN metr (mijozga
        # ko'rsatiladigan), length = ISHLATILGAN blok soni (ombordan shuncha yechiladi).
        blok_soni = float(item.length or 0)
        pid = getattr(item, 'penoplast_id', None)
        p = db.query(Inventory).filter(Inventory.id == pid).first() if pid else default_penoplast
        if p and p.volume_per_unit and blok_soni > 0:
            return blok_soni * float(p.volume_per_unit)

    return 0.0


def _group_volumes_by_penoplast(db, items) -> dict:
    """Detallarni plotnost bo'yicha guruhlaydi.
    Qaytaradi: {penoplast_id: total_volume_m3}"""
    default_p = get_default_penoplast(db)
    default_id = default_p.id if default_p else None

    volumes = {}
    for item in items:
        vol = _item_volume_m3(db, item, default_p)
        if vol <= 0:
            continue
        pid = getattr(item, 'penoplast_id', None) or default_id
        if not pid:
            continue
        volumes[pid] = volumes.get(pid, 0.0) + vol
    return volumes


def check_inventory_for_order(db: Session, order_data) -> dict:
    """
    Buyurtma uchun xomashyo yetishini tekshiradi.
    Har detal o'z plotnostidan hisoblanadi.
    """
    from models import Inventory

    shortages = []
    volumes = _group_volumes_by_penoplast(db, order_data.items)
    total_volume_m3 = sum(volumes.values())

    if not volumes:
        return {"enough": True, "shortages": [], "total_volume_m3": 0}

    for pid, vol in volumes.items():
        p = db.query(Inventory).filter(Inventory.id == pid).first()
        if not p:
            continue
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks_needed = vol / vol_per_unit
        if float(p.stock_quantity) < blocks_needed:
            shortages.append(
                f"{p.item_name}: kerak {blocks_needed:.1f} blok, "
                f"qoldi {float(p.stock_quantity):.1f} blok"
            )

    return {
        "enough": len(shortages) == 0,
        "shortages": shortages,
        "total_volume_m3": round(total_volume_m3, 3)
    }


def deduct_inventory_for_order(db: Session, order) -> list:
    """
    Buyurtma saqlangandan keyin ombordan xomashyo ayiradi.
    Har detal o'z plotnostidan ayiriladi.
    """
    from models import Inventory

    log = []
    volumes = _group_volumes_by_penoplast(db, order.items)

    for pid, vol in volumes.items():
        p = db.query(Inventory).filter(Inventory.id == pid).with_for_update().first()
        if not p:
            continue
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks_needed = vol / vol_per_unit
        # MUHIM: 0 ga cheklamaymiz — agar admin "yetishmasa ham davom et"
        # deb tasdiqlagan bo'lsa, ombor MANFIY ko'rsatishi kerak (haqiqiy
        # tanqislik miqdorini yashirmaslik uchun — bu ataylab qilingan).
        p.stock_quantity = float(p.stock_quantity) - blocks_needed
        log.append(f"{p.item_name}: -{blocks_needed:.2f} blok")

    if volumes:
        db.commit()
    return log


def check_termopanel_for_order(db: Session, order_data) -> dict:
    """Buyurtmadagi termopanel (bazalt) detallari uchun xomashyo yetarliligini tekshiradi.
    Serpiyanka va kley avtomatik topiladi; ularning miqdori har bir tanlangan
    bazalt turining O'ZIDA saqlangan nisbatlar (serp_ratio_per_m2, kley_ratio_per_m2)
    bo'yicha hisoblanadi."""
    from models import Inventory

    shortages = []
    bazalt_needed = {}   # {item_id: jami dona}
    total_serp_m2 = 0.0
    total_kley_kg = 0.0

    for item in order_data.items:
        if (getattr(item, 'category', None) or '').lower() != 'termopanel':
            continue
        m2 = float(item.quantity or 0)
        if m2 <= 0:
            continue

        bazalt_id = getattr(item, 'bazalt_item_id', None)
        if bazalt_id:
            b = db.query(Inventory).filter(Inventory.id == bazalt_id).first()
            if b:
                area = float(b.volume_per_unit or 0.72)
                bazalt_needed[bazalt_id] = bazalt_needed.get(bazalt_id, 0.0) + (m2 / area)
                serp_ratio = float(b.serp_ratio_per_m2) if b.serp_ratio_per_m2 else 2.0
                kley_ratio = float(b.kley_ratio_per_m2) if b.kley_ratio_per_m2 else 0.8
                total_serp_m2 += m2 * serp_ratio
                total_kley_kg += m2 * kley_ratio
            else:
                shortages.append("Tanlangan bazalt turi ombordan topilmadi")

    for bazalt_id, needed in bazalt_needed.items():
        b = db.query(Inventory).filter(Inventory.id == bazalt_id).first()
        if b and float(b.stock_quantity) < needed:
            shortages.append(f"{b.item_name}: kerak {needed:.2f} dona, qoldi {float(b.stock_quantity):.2f} dona")

    if total_serp_m2 > 0:
        s = find_serpiyanka(db)
        if not s:
            shortages.append("Serpiyanka ombordan topilmadi (nomida 'serpiyanka' so'zi bo'lishi kerak)")
        else:
            area = float(s.volume_per_unit or 50.0)
            needed = total_serp_m2 / area
            if float(s.stock_quantity) < needed:
                shortages.append(f"{s.item_name}: kerak {needed:.2f} rulon, qoldi {float(s.stock_quantity):.2f} rulon")

    if total_kley_kg > 0:
        k = find_kley(db)
        if not k:
            shortages.append("Kley ombordan topilmadi (nomida 'kley' so'zi bo'lishi kerak)")
        elif float(k.stock_quantity) < total_kley_kg:
            shortages.append(f"{k.item_name}: kerak {total_kley_kg:.2f} kg, qoldi {float(k.stock_quantity):.2f} kg")

    return {"enough": len(shortages) == 0, "shortages": shortages}


def deduct_termopanel_for_order(db: Session, order, order_data) -> list:
    """Buyurtma yaratilgandan keyin — termopanel detallari uchun
    bazalt/serpiyanka/kley/loy'ni QULFLAB ombordan yechadi.

    order_data — asl so'rov (bazalt_item_id va h.k. shu yerda bor),
    order — yangi yaratilgan, ID'lari bor buyurtma. Ikkalasi bir xil
    tartibda kiritilgani uchun INDEKS bo'yicha mos qilinadi.

    Har bir detalning notes maydoniga qancha ishlatilgani yoziladi —
    keyinchalik buyurtma o'chirilsa, aynan shu miqdor qaytariladi."""
    from models import Inventory, Recipe

    log = []
    db_items = sorted(order.items, key=lambda x: x.id)
    for db_item, item_data in zip(db_items, order_data.items):
        if (db_item.category or '').lower() != 'termopanel':
            continue
        m2 = float(db_item.quantity or 0)
        if m2 <= 0:
            continue

        bazalt_id = getattr(item_data, 'bazalt_item_id', None)
        loy_kg = float(getattr(item_data, 'termo_loy_kg', None) or 0)

        used_parts = []
        serp_ratio = 2.0
        kley_ratio = 0.8

        if bazalt_id:
            b = db.query(Inventory).filter(Inventory.id == bazalt_id).with_for_update().first()
            if b:
                area = float(b.volume_per_unit or 0.72)
                sheets = m2 / area
                b.stock_quantity = float(b.stock_quantity) - sheets
                log.append(f"{b.item_name}: -{sheets:.2f} dona")
                used_parts.append(f"bazalt_id={bazalt_id},bazalt_qty={sheets:.4f}")
                if b.serp_ratio_per_m2:
                    serp_ratio = float(b.serp_ratio_per_m2)
                if b.kley_ratio_per_m2:
                    kley_ratio = float(b.kley_ratio_per_m2)

        # Serpiyanka — omborda yagona turi deb hisoblanadi, avtomatik topiladi.
        # Miqdori — TANLANGAN BAZALTNING o'zida saqlangan nisbat bo'yicha (standart: 2×)
        serp_m2 = m2 * serp_ratio
        s = find_serpiyanka(db, lock=True)
        if s:
            area = float(s.volume_per_unit or 50.0)
            rulon = serp_m2 / area
            s.stock_quantity = float(s.stock_quantity) - rulon
            log.append(f"{s.item_name}: -{rulon:.2f} rulon")
            used_parts.append(f"serp_id={s.id},serp_qty={rulon:.4f}")

        # Kley — TANLANGAN BAZALTNING o'zida saqlangan nisbat bo'yicha (1 m² bazaltga necha kg)
        k = find_kley(db, lock=True)
        if k:
            kley_kg = m2 * kley_ratio
            k.stock_quantity = float(k.stock_quantity) - kley_kg
            log.append(f"{k.item_name}: -{kley_kg:.2f} kg")
            used_parts.append(f"kley_id={k.id},kley_qty={kley_kg:.4f}")

        if loy_kg > 0:
            log.extend(deduct_loy_ingredients(db, order, loy_kg, use_stock=False))
            used_parts.append(f"loy_kg={loy_kg:.4f}")

        if used_parts:
            marker = " [TERMO:" + ",".join(used_parts) + "]"
            db_item.notes = (db_item.notes or "") + marker

    if log:
        db.commit()
    return log


def return_termopanel_for_order(db: Session, order) -> list:
    """Buyurtma o'chirilganda — termopanel detallari uchun ilgari yechilgan
    bazalt/serpiyanka/kley ombordan qaytariladi (loy qaytarilmaydi — ishlatib bo'lingan)."""
    from models import Inventory
    import re as _re

    log = []
    for item in order.items:
        if (item.category or '').lower() != 'termopanel' or not item.notes:
            continue
        m = _re.search(r'\[TERMO:([^\]]+)\]', item.notes)
        if not m:
            continue
        parts = dict(p.split('=') for p in m.group(1).split(',') if '=' in p)

        if 'bazalt_id' in parts and 'bazalt_qty' in parts:
            b = db.query(Inventory).filter(Inventory.id == int(parts['bazalt_id'])).with_for_update().first()
            if b:
                b.stock_quantity = float(b.stock_quantity) + float(parts['bazalt_qty'])
                log.append(f"{b.item_name}: +{float(parts['bazalt_qty']):.2f} dona qaytarildi")

        if 'serp_id' in parts and 'serp_qty' in parts:
            s = db.query(Inventory).filter(Inventory.id == int(parts['serp_id'])).with_for_update().first()
            if s:
                s.stock_quantity = float(s.stock_quantity) + float(parts['serp_qty'])
                log.append(f"{s.item_name}: +{float(parts['serp_qty']):.2f} rulon qaytarildi")

        if 'kley_id' in parts and 'kley_qty' in parts:
            k = db.query(Inventory).filter(Inventory.id == int(parts['kley_id'])).with_for_update().first()
            if k:
                k.stock_quantity = float(k.stock_quantity) + float(parts['kley_qty'])
                log.append(f"{k.item_name}: +{float(parts['kley_qty']):.2f} kg qaytarildi")

    if log:
        db.commit()
    return log


class _ProratedItem:
    """Buyurtma detalining faqat 'qolgan (topshirilmagan) qismi'ni ifodalovchi
    vaqtinchalik obyekt — mavjud hajm hisoblash funksiyalarini o'zgartirmasdan
    qayta ishlatish uchun."""
    def __init__(self, real_item, fraction):
        self.category = real_item.category
        self.width = real_item.width
        self.thickness = real_item.thickness
        self.penoplast_id = real_item.penoplast_id
        self.is_coated = real_item.is_coated
        self.price_per_m3 = real_item.price_per_m3
        self.finished_product_id = real_item.finished_product_id
        self.recipe_id = real_item.recipe_id
        cat = (real_item.category or '').lower()
        if cat == 'profil':
            self.length = float(real_item.length or 0) * fraction
            self.quantity = float(real_item.quantity or 1)
        else:
            self.length = real_item.length
            self.quantity = float(real_item.quantity or 0) * fraction


def get_undelivered_items(order):
    """Buyurtmadagi har bir detal uchun 'hali topshirilmagan' ulushni hisoblaydi.
    Qaytaradi: [(real_item, fraction, remaining_qty, ordered_qty), ...]
    fraction — 0 dan 1 gacha (masalan 0.36 — 36% hali topshirilmagan)."""
    result = []
    for item in order.items:
        if (item.finished_product_id or None):
            continue  # Tayyor mahsulotdan olingan — bu yerda hisoblanmaydi
        ordered = item.order_qty_normalized
        if ordered <= 0:
            continue
        delivered = item.delivered_qty
        remaining = max(ordered - delivered, 0)
        if remaining <= 0.001:
            continue  # To'liq topshirilgan — qaytariladigan narsa yo'q
        fraction = remaining / ordered
        result.append((item, fraction, remaining, ordered))
    return result


def return_inventory_for_order_partial(db: Session, order) -> list:
    """Qisman topshirilgan buyurtma bekor qilinganda/o'chirilganda —
    FAQAT hali topshirilmagan (mijozga berilmagan) qismi uchun xomashyoni
    omborga qaytaradi. Topshirib bo'lingan qism — mijozda, qaytmaydi."""
    from models import Inventory

    log = []
    undelivered = get_undelivered_items(order)
    if not undelivered:
        return log

    prorated_items = [_ProratedItem(item, fraction) for item, fraction, _, _ in undelivered]

    # 1) Penoplast — qolgan qism bo'yicha
    volumes = _group_volumes_by_penoplast(db, prorated_items)
    for pid, vol in volumes.items():
        p = db.query(Inventory).filter(Inventory.id == pid).with_for_update().first()
        if not p:
            continue
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks_to_return = vol / vol_per_unit
        p.stock_quantity = float(p.stock_quantity) + blocks_to_return
        log.append(f"{p.item_name}: +{blocks_to_return:.2f} blok qaytarildi (qolgan qism)")

    # 2) Termopanel (bazalt/serpiyanka/kley) — qolgan qism bo'yicha
    for item, fraction, remaining, ordered in undelivered:
        if (item.category or '').lower() != 'termopanel':
            continue
        import re as _re
        m = _re.search(r'\[TERMO:([^\]]+)\]', item.notes or '')
        if not m:
            continue
        parts = dict(p.split('=') for p in m.group(1).split(',') if '=' in p)
        if 'bazalt_id' in parts and 'bazalt_qty' in parts:
            b = db.query(Inventory).filter(Inventory.id == int(parts['bazalt_id'])).with_for_update().first()
            if b:
                qty = float(parts['bazalt_qty']) * fraction
                b.stock_quantity = float(b.stock_quantity) + qty
                log.append(f"{b.item_name}: +{qty:.2f} dona qaytarildi (qolgan qism)")
        if 'serp_id' in parts and 'serp_qty' in parts:
            s = db.query(Inventory).filter(Inventory.id == int(parts['serp_id'])).with_for_update().first()
            if s:
                qty = float(parts['serp_qty']) * fraction
                s.stock_quantity = float(s.stock_quantity) + qty
                log.append(f"{s.item_name}: +{qty:.2f} rulon qaytarildi (qolgan qism)")
        if 'kley_id' in parts and 'kley_qty' in parts:
            k = db.query(Inventory).filter(Inventory.id == int(parts['kley_id'])).with_for_update().first()
            if k:
                qty = float(parts['kley_qty']) * fraction
                k.stock_quantity = float(k.stock_quantity) + qty
                log.append(f"{k.item_name}: +{qty:.2f} kg qaytarildi (qolgan qism)")

    if log:
        db.commit()
    return log


def return_inventory_for_order(db: Session, order) -> list:
    """
    Buyurtma o'chirilganda omborga xomashyo qaytaradi.
    Har detal o'z plotnostiga qaytariladi.
    """
    from models import Inventory

    log = []
    volumes = _group_volumes_by_penoplast(db, order.items)

    for pid, vol in volumes.items():
        p = db.query(Inventory).filter(Inventory.id == pid).with_for_update().first()
        if not p:
            continue
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks_to_return = vol / vol_per_unit
        p.stock_quantity = float(p.stock_quantity) + blocks_to_return
        log.append(f"{p.item_name}: +{blocks_to_return:.2f} blok qaytarildi")

    if volumes:
        db.commit()
    return log


# ============================================================
# TAYYOR LOY ZAXIRASI
# ============================================================

def _get_planned_loy(order) -> float:
    """Buyurtma yaratilganda rejalashtirilgan loy miqdorini notes dan oladi."""
    notes = order.notes or ''
    for part in notes.split(','):
        part = part.strip()
        if part.startswith('planned_loy='):
            try:
                return float(part.split('=')[1])
            except (ValueError, IndexError):
                pass
    return 0.0


def _set_planned_loy(order, kg: float) -> None:
    """Rejalashtirilgan loyni notes ga yozadi."""
    notes = order.notes or ''
    parts = [p.strip() for p in notes.split(',') if p.strip() and not p.strip().startswith('planned_loy=')]
    parts.append(f'planned_loy={kg}')
    order.notes = ','.join(parts)


def _get_order_recipe(db: Session, order):
    """Buyurtmaning retseptini topadi."""
    from models import Recipe
    for item in order.items:
        if getattr(item, 'recipe_id', None):
            r = db.query(Recipe).filter(Recipe.id == item.recipe_id).first()
            if r:
                return r
    return db.query(Recipe).first()


def get_or_create_loy_stock(db: Session, recipe):
    """Retsept uchun 'Tayyor loy' ombor pozitsiyasini topadi yoki yaratadi."""
    from models import Inventory

    if not recipe:
        return None

    recipe_name = recipe.name.value if hasattr(recipe.name, 'value') else str(recipe.name)
    item_name = f"Tayyor loy ({recipe_name})"

    stock = db.query(Inventory).filter(Inventory.item_name == item_name).with_for_update().first()
    if stock:
        return stock

    stock = Inventory(
        item_name=item_name,
        stock_quantity=0.0,
        unit="kg",
        min_stock=0.0,
        price_per_unit=None,
        volume_per_unit=1.0,
        is_penoplast=False,
        notes="Buyurtmalardan ortgan tayyor loy — avtomatik yaratilgan"
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    print(f"✓ Ombor pozitsiyasi yaratildi: {item_name}")
    return stock


def add_loy_to_stock(db: Session, recipe, kg: float) -> str:
    """Ortgan loyni omborga qo'shadi."""
    if kg <= 0:
        return ""
    stock = get_or_create_loy_stock(db, recipe)
    if not stock:
        return ""
    stock.stock_quantity = float(stock.stock_quantity or 0) + kg
    db.commit()
    msg = f"{stock.item_name}: +{kg:.1f} kg (ortdi)"
    print(f"✓ {msg}")
    return msg


def take_loy_from_stock(db: Session, recipe, kg_needed: float, order=None, reason_override: str = None):
    """Ombordagi tayyor loydan oladi.
    Qaytaradi: (olingan_kg, qolgan_ehtiyoj_kg, log_matni)"""
    if kg_needed <= 0:
        return 0.0, 0.0, ""

    stock = get_or_create_loy_stock(db, recipe)
    if not stock:
        return 0.0, kg_needed, ""

    available = float(stock.stock_quantity or 0)
    if available <= 0:
        return 0.0, kg_needed, ""

    taken = min(available, kg_needed)
    stock.stock_quantity = available - taken
    if taken > 0:
        import crud as _crud
        _crud.log_movement(
            db, stock.id, stock.item_name, movement_type="out",
            quantity=taken, unit=stock.unit,
            reason=reason_override or f"Buyurtma {getattr(order, 'order_number', order.id) if order else '?'} (tayyor loy zaxirasidan)",
            order_id=order.id if order else None
        )
    db.commit()
    msg = f"{stock.item_name}: -{taken:.1f} kg (zaxiradan)"
    print(f"✓ {msg}")
    return taken, kg_needed - taken, msg


def deduct_raw_material_for_brak(db: Session, order_item, order, brak_qty: float, coating_applied: bool) -> list:
    """Brak bo'lgan detal uchun xomashyoni ombordan yechadi.

    - Penoplast — HAR DOIM yechiladi (detal shakli kesilgan bo'lsa, xomashyo
      allaqachon sarflangan — brak bo'lishidan qat'i nazar).
    - Loy (qoplama) — FAQAT coating_applied=True bo'lsa yechiladi (ya'ni
      brak AYNAN qoplama tortilgandan keyin, uni sindirib/tirnab
      yuborilgan bo'lsa). Agar qoplamagacha (masalan kesish jarayonida)
      brak bo'lgan bo'lsa — loy sarflanmagan, hisoblanmaydi.

    Faqat log qaytaradi, hech qanday moliyaviy hisob-kitobni o'zgartirmaydi
    (bu — create_return_item() dagi refund_amount hisobidan MUSTAQIL)."""
    from models import Inventory, InventoryMovement

    log = []
    if brak_qty <= 0 or not order_item:
        return log

    default_p = get_default_penoplast(db)
    total_volume = _item_volume_m3(db, order_item, default_p)
    qty_units = order_item.order_qty_normalized
    if total_volume > 0 and qty_units > 0:
        per_unit_volume = total_volume / qty_units
        brak_volume = per_unit_volume * brak_qty
        pid = order_item.penoplast_id or (default_p.id if default_p else None)
        if pid and brak_volume > 0:
            p = db.query(Inventory).filter(Inventory.id == pid).first()
            if p and p.volume_per_unit and p.volume_per_unit > 0:
                blocks = brak_volume / float(p.volume_per_unit)
                old_qty = float(p.stock_quantity or 0)
                p.stock_quantity = max(0, old_qty - blocks)
                db.add(InventoryMovement(
                    inventory_id=p.id, item_name=p.item_name, movement_type="out",
                    quantity=blocks, unit=p.unit,
                    reason=f"Brak — {order_item.name} ({brak_qty:g} birlik)",
                    order_id=order.id if order else None
                ))
                log.append(f"{p.item_name}: -{blocks:.3f} blok (brak uchun)")

    if coating_applied and order_item.is_coated and order:
        loy_kg = 0.0
        if order.notes:
            for part in str(order.notes).split(','):
                p2 = part.strip()
                if p2.startswith('loy_kg='):
                    try:
                        loy_kg = float(p2.split('=')[1])
                    except (ValueError, IndexError):
                        pass
                    break
        if loy_kg <= 0:
            loy_kg = _get_planned_loy(order)

        total_coated_units = 0.0
        for oi in order.items:
            if oi.is_coated:
                total_coated_units += oi.order_qty_normalized

        if loy_kg > 0 and total_coated_units > 0:
            loy_per_unit = loy_kg / total_coated_units
            brak_loy_kg = loy_per_unit * brak_qty
            if brak_loy_kg > 0:
                loy_log = deduct_loy_ingredients(
                    db, order, brak_loy_kg, recipe_id=order_item.recipe_id,
                    reason_override=f"Brak — {order_item.name} (qoplama, {brak_qty:g} birlik)"
                )
                log.extend([f"{l} (brak — qoplama)" for l in loy_log])

    db.commit()
    return log


def check_loy_ingredients_for_order(db: Session, order_recipe_id: int, loy_kg: float) -> dict:
    """Qoplama (loy) uchun kerakli xomashyo yetarli-yetarli emasligini
    OLDINDAN tekshiradi (hali hech narsa ayirilmasdan). Avval "tayyor loy"
    zaxirasi hisobga olinadi, keyin qolgan qism uchun retsept xomashyosi
    tekshiriladi — deduct_loy_ingredients() bilan BIR XIL mantiq."""
    from models import Recipe, Inventory

    if loy_kg <= 0:
        return {"enough": True, "shortages": []}

    recipe = db.query(Recipe).filter(Recipe.id == order_recipe_id).first() if order_recipe_id else db.query(Recipe).first()
    if not recipe:
        return {"enough": True, "shortages": []}

    # Tayyor loy zaxirasi bor-yo'qligini tekshiramiz (ayirmasdan, faqat o'qib)
    stock = get_or_create_loy_stock(db, recipe)
    available_stock = float(stock.stock_quantity or 0) if stock else 0.0
    remaining_kg = max(0.0, loy_kg - available_stock)

    if remaining_kg <= 0:
        return {"enough": True, "shortages": []}

    batch = float(recipe.batch_size_kg or 100)
    shortages = []
    for ing in recipe.ingredients:
        recipe_kg = float(ing.quantity_kg or 0)
        if recipe_kg <= 0 or not ing.inventory:
            continue
        needed_kg = remaining_kg * (recipe_kg / batch)
        inv_item = db.query(Inventory).filter(Inventory.id == ing.inventory_id).first()
        if inv_item and float(inv_item.stock_quantity or 0) < needed_kg:
            shortages.append(
                f"{inv_item.item_name} (loy uchun): kerak {needed_kg:.2f} {inv_item.unit}, "
                f"qoldi {float(inv_item.stock_quantity or 0):.2f} {inv_item.unit}"
            )

    return {"enough": len(shortages) == 0, "shortages": shortages}


def deduct_loy_ingredients(db: Session, order, loy_kg: float, use_stock: bool = True, recipe_id: int = None, reason_override: str = None) -> list:
    """
    Loy (qoplama) uchun ingredientlarni ombordan ayiradi.
    use_stock=True bo'lsa — avval tayyor loy zaxirasidan oladi.
    recipe_id berilsa — aynan O'SHA retsept ishlatiladi (masalan "Loy sotish"
    detali uchun, buyurtmaning umumiy qoplama retseptidan farqli bo'lishi
    mumkin). Berilmasa — avvalgidek, buyurtmadan avtomatik topiladi.
    reason_override berilsa — jurnal yozuvida standart "Buyurtma X (loy)"
    o'rniga shu matn ishlatiladi (masalan brak hisoboti uchun "Brak — ...").
    """
    from models import Inventory, Recipe

    if loy_kg <= 0:
        return []

    log = []

    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first() if recipe_id else _get_order_recipe(db, order)

    if not recipe:
        print("⚠ Retsept topilmadi — loy ingredientlari ayirilmadi")
        return []

    # 1) Avval tayyor loy zaxirasidan olamiz
    if use_stock:
        taken, loy_kg, msg = take_loy_from_stock(db, recipe, loy_kg, order=order, reason_override=reason_override)
        if msg:
            log.append(msg)
        if loy_kg <= 0:
            return log  # Zaxira yetdi, xomashyo kerak emas

    batch = float(recipe.batch_size_kg or 100)

    for ing in recipe.ingredients:
        recipe_kg = float(ing.quantity_kg or 0)
        if recipe_kg <= 0 or not ing.inventory:
            continue
        needed_kg = loy_kg * (recipe_kg / batch)
        inv_item = db.query(Inventory).filter(
            Inventory.id == ing.inventory_id
        ).with_for_update().first()
        if inv_item:
            inv_item.stock_quantity = float(inv_item.stock_quantity) - needed_kg
            log.append(f"{inv_item.item_name}: -{needed_kg:.2f} {inv_item.unit}")
            print(f"✓ {inv_item.item_name}: -{needed_kg:.2f} ayirildi")
            import crud as _crud
            _crud.log_movement(
                db, inv_item.id, inv_item.item_name, movement_type="out",
                quantity=needed_kg, unit=inv_item.unit,
                reason=reason_override or f"Buyurtma {getattr(order, 'order_number', order.id)} (loy)",
                order_id=order.id
            )

    db.commit()
    return log


def return_loy_ingredients(db: Session, order, loy_kg: float, recipe_id: int = None) -> list:
    """
    Loy ingredientlarini omborga qaytaradi (buyurtma o'chirilganda).
    recipe_id berilsa — aynan O'SHA retsept ishlatiladi.
    """
    from models import Inventory, Recipe

    if loy_kg <= 0:
        return []

    log = []

    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first() if recipe_id else None
    if not recipe:
        for item in order.items:
            if hasattr(item, 'recipe_id') and item.recipe_id:
                recipe = db.query(Recipe).filter(Recipe.id == item.recipe_id).first()
            if recipe:
                break
    if not recipe:
        recipe = db.query(Recipe).first()

    if not recipe:
        return []

    batch = float(recipe.batch_size_kg or 100)

    for ing in recipe.ingredients:
        recipe_kg = float(ing.quantity_kg or 0)
        if recipe_kg <= 0 or not ing.inventory:
            continue
        needed_kg = loy_kg * (recipe_kg / batch)
        inv_item = db.query(Inventory).filter(
            Inventory.id == ing.inventory_id
        ).with_for_update().first()
        if inv_item:
            inv_item.stock_quantity = float(inv_item.stock_quantity) + needed_kg
            log.append(f"{inv_item.item_name}: +{needed_kg:.2f} qaytarildi")
            import crud as _crud
            _crud.log_movement(
                db, inv_item.id, inv_item.item_name, movement_type="in",
                quantity=needed_kg, unit=inv_item.unit,
                reason=f"Buyurtma {getattr(order, 'order_number', order.id)} bekor qilindi (loy qaytarildi)",
                order_id=order.id
            )

    db.commit()
    return log


# ============================================================
# BUYURTMANI TAHRIRLASH — OMBORNI FARQ BO'YICHA TO'G'RILASH
# ============================================================

class _FakeItem:
    """Ombor hisobi uchun soxta detal (schema yoki dict dan)."""
    def __init__(self, d):
        self.category = d.get('category')
        self.width = d.get('width')
        self.thickness = d.get('thickness')
        self.length = d.get('length')
        self.quantity = d.get('quantity', 1)
        self.unit_price = d.get('unit_price', 0)
        self.penoplast_id = d.get('penoplast_id')
        self.price_per_m3 = d.get('price_per_m3')
        self.finished_product_id = d.get('finished_product_id')


def adjust_inventory_diff(db: Session, old_items, new_items) -> list:
    """Eski va yangi detallarni solishtirib, ombordagi penoplastni
    faqat farq miqdorida to'g'rilaydi.

    old_items / new_items — OrderItem obyektlari yoki dict lar ro'yxati.
    """
    from models import Inventory

    def _norm(items):
        out = []
        for it in items:
            out.append(_FakeItem(it) if isinstance(it, dict) else it)
        return out

    old_vol = _group_volumes_by_penoplast(db, _norm(old_items))
    new_vol = _group_volumes_by_penoplast(db, _norm(new_items))

    log = []
    all_ids = set(old_vol.keys()) | set(new_vol.keys())

    for pid in all_ids:
        old_v = old_vol.get(pid, 0.0)
        new_v = new_vol.get(pid, 0.0)
        diff = new_v - old_v          # + = ko'paydi, − = kamaydi

        if abs(diff) < 0.0001:
            continue

        p = db.query(Inventory).filter(Inventory.id == pid).with_for_update().first()
        if not p:
            continue

        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks = diff / vol_per_unit

        if blocks > 0:
            p.stock_quantity = max(0, float(p.stock_quantity) - blocks)
            log.append(f"{p.item_name}: -{blocks:.2f} blok (qo'shildi)")
        else:
            p.stock_quantity = float(p.stock_quantity) + abs(blocks)
            log.append(f"{p.item_name}: +{abs(blocks):.2f} blok (qaytdi)")

    if log:
        db.commit()
    return log


def _group_termo_materials(db: Session, items) -> dict:
    """Termopanel detallarini xomashyo bo'yicha guruhlaydi.
    Qaytaradi: {'bazalt': {item_id: jami_dona}, 'serp_m2': jami_m2, 'kley_kg': jami_kg, 'loy_kg': jami_kg}
    Serpiyanka/kley omborda yagona turi deb hisoblanadi — ID bo'yicha guruhlash shart emas,
    lekin ularning MIQDORI har bir tanlangan bazaltning o'zida saqlangan nisbatidan olinadi."""
    from models import Inventory
    result = {'bazalt': {}, 'serp_m2': 0.0, 'kley_kg': 0.0, 'loy_kg': 0.0}
    for it in items:
        cat = (it.get('category') if isinstance(it, dict) else getattr(it, 'category', None)) or ''
        if cat.lower() != 'termopanel':
            continue
        get = (lambda k: it.get(k)) if isinstance(it, dict) else (lambda k: getattr(it, k, None))
        m2 = float(get('quantity') or 0)
        if m2 <= 0:
            continue
        bazalt_id = get('bazalt_item_id')
        serp_ratio, kley_ratio = 2.0, 0.8
        if bazalt_id:
            result['bazalt'][bazalt_id] = result['bazalt'].get(bazalt_id, 0.0) + m2  # m² — keyin bo'linadi
            b = db.query(Inventory).filter(Inventory.id == bazalt_id).first()
            if b:
                if b.serp_ratio_per_m2:
                    serp_ratio = float(b.serp_ratio_per_m2)
                if b.kley_ratio_per_m2:
                    kley_ratio = float(b.kley_ratio_per_m2)
        result['serp_m2'] += m2 * serp_ratio
        result['kley_kg'] += m2 * kley_ratio
        result['loy_kg'] += float(get('termo_loy_kg') or 0)
    return result


def check_termopanel_diff(db: Session, old_items, new_items) -> dict:
    """Buyurtma TAHRIRLANGANDA — termopanel xomashyosi farqi yetarli ekanini tekshiradi.
    Faqat ORTIQCHA kerak bo'lgan qism uchun (kamaygan bo'lsa — tekshiruv shart emas)."""
    from models import Inventory

    old_g = _group_termo_materials(db, old_items)
    new_g = _group_termo_materials(db, new_items)
    shortages = []

    for bid in set(old_g['bazalt']) | set(new_g['bazalt']):
        old_m2 = old_g['bazalt'].get(bid, 0.0)
        new_m2 = new_g['bazalt'].get(bid, 0.0)
        diff_m2 = new_m2 - old_m2
        if diff_m2 <= 0:
            continue
        b = db.query(Inventory).filter(Inventory.id == bid).first()
        if not b:
            shortages.append("Bazalt plita ombordan topilmadi")
            continue
        area = float(b.volume_per_unit or 0.72)
        needed = diff_m2 / area
        if float(b.stock_quantity) < needed:
            shortages.append(f"{b.item_name}: qo'shimcha {needed:.2f} dona kerak, qoldi {float(b.stock_quantity):.2f} dona")

    serp_diff_m2 = new_g['serp_m2'] - old_g['serp_m2']
    if serp_diff_m2 > 0:
        s = find_serpiyanka(db)
        if not s:
            shortages.append("Serpiyanka ombordan topilmadi")
        else:
            area = float(s.volume_per_unit or 50.0)
            needed = serp_diff_m2 / area
            if float(s.stock_quantity) < needed:
                shortages.append(f"{s.item_name}: qo'shimcha {needed:.2f} rulon kerak, qoldi {float(s.stock_quantity):.2f} rulon")

    kley_diff = new_g['kley_kg'] - old_g['kley_kg']
    if kley_diff > 0:
        k = find_kley(db)
        if not k:
            shortages.append("Kley ombordan topilmadi")
        elif float(k.stock_quantity) < kley_diff:
            shortages.append(f"{k.item_name}: qo'shimcha {kley_diff:.2f} kg kerak, qoldi {float(k.stock_quantity):.2f} kg")

    return {"enough": len(shortages) == 0, "shortages": shortages}


def adjust_termopanel_diff(db: Session, old_items, new_items, recipe_id=None) -> list:
    """Buyurtma TAHRIRLANGANDA — termopanel xomashyosini FARQ bo'yicha to'g'irlaydi.
    Ko'proq kerak bo'lsa — ombordan yechadi; kamroq kerak bo'lsa — qaytaradi."""
    from models import Inventory

    old_g = _group_termo_materials(db, old_items)
    new_g = _group_termo_materials(db, new_items)
    log = []

    for bid in set(old_g['bazalt']) | set(new_g['bazalt']):
        diff_m2 = new_g['bazalt'].get(bid, 0.0) - old_g['bazalt'].get(bid, 0.0)
        if abs(diff_m2) < 0.001:
            continue
        b = db.query(Inventory).filter(Inventory.id == bid).with_for_update().first()
        if not b:
            continue
        area = float(b.volume_per_unit or 0.72)
        diff_sheets = diff_m2 / area
        b.stock_quantity = max(0, float(b.stock_quantity) - diff_sheets)
        log.append(f"{b.item_name}: {'-' if diff_sheets > 0 else '+'}{abs(diff_sheets):.2f} dona (tahrirlash)")

    serp_diff_m2 = new_g['serp_m2'] - old_g['serp_m2']
    if abs(serp_diff_m2) >= 0.001:
        s = find_serpiyanka(db, lock=True)
        if s:
            area = float(s.volume_per_unit or 50.0)
            diff_rulon = serp_diff_m2 / area
            s.stock_quantity = max(0, float(s.stock_quantity) - diff_rulon)
            log.append(f"{s.item_name}: {'-' if diff_rulon > 0 else '+'}{abs(diff_rulon):.2f} rulon (tahrirlash)")

    kley_diff = new_g['kley_kg'] - old_g['kley_kg']
    if abs(kley_diff) >= 0.001:
        k = find_kley(db, lock=True)
        if k:
            k.stock_quantity = max(0, float(k.stock_quantity) - kley_diff)
            log.append(f"{k.item_name}: {'-' if kley_diff > 0 else '+'}{abs(kley_diff):.2f} kg (tahrirlash)")

    loy_diff = new_g['loy_kg'] - old_g['loy_kg']
    if loy_diff > 0.001:
        class _FakeOrder:
            def __init__(self, rid):
                class _It:
                    pass
                it = _It(); it.recipe_id = rid
                self.items = [it]
                self.id = None
                self.order_number = "TAHRIRLASH"
        log.extend(deduct_loy_ingredients(db, _FakeOrder(recipe_id), loy_diff, use_stock=False))
    elif loy_diff < -0.001:
        class _FakeOrder:
            def __init__(self, rid):
                class _It:
                    pass
                it = _It(); it.recipe_id = rid
                self.items = [it]
                self.id = None
                self.order_number = "TAHRIRLASH"
        log.extend(return_loy_ingredients(db, _FakeOrder(recipe_id), abs(loy_diff)))

    if log:
        db.commit()
    return log


def check_inventory_diff(db: Session, old_items, new_items) -> dict:
    """Tahrirlashdan keyin xomashyo yetadimi — tekshiradi."""
    from models import Inventory

    def _norm(items):
        return [_FakeItem(it) if isinstance(it, dict) else it for it in items]

    old_vol = _group_volumes_by_penoplast(db, _norm(old_items))
    new_vol = _group_volumes_by_penoplast(db, _norm(new_items))

    shortages = []
    for pid in set(old_vol.keys()) | set(new_vol.keys()):
        diff = new_vol.get(pid, 0.0) - old_vol.get(pid, 0.0)
        if diff <= 0:
            continue
        p = db.query(Inventory).filter(Inventory.id == pid).first()
        if not p:
            continue
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks = diff / vol_per_unit
        if float(p.stock_quantity) < blocks:
            shortages.append(
                f"{p.item_name}: qo'shimcha {blocks:.1f} blok kerak, "
                f"qoldi {float(p.stock_quantity):.1f} blok"
            )

    return {"enough": len(shortages) == 0, "shortages": shortages}


def adjust_loy_diff(db: Session, order, old_loy: float, new_loy: float) -> list:
    """Loy rejasi o'zgarganda ombordagi xomashyoni to'g'rilaydi."""
    diff = float(new_loy or 0) - float(old_loy or 0)
    if abs(diff) < 0.01:
        return []

    log = []
    recipe = _get_order_recipe(db, order)

    if diff > 0:
        # Loy ko'paydi — farq uchun xomashyo ayiramiz
        log.extend(deduct_loy_ingredients(db, order, diff))
    else:
        # Loy kamaydi — farqni omborga qaytaramiz
        log.extend(return_loy_ingredients(db, order, abs(diff)))

    return log


def get_loy_cost_per_kg(db: Session, recipe_id: int = None) -> dict:
    """Retsept bo'yicha 1 kg loyning tan narxi."""
    from models import Recipe, Inventory

    recipe = None
    if recipe_id:
        recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        recipe = db.query(Recipe).first()

    if not recipe:
        return {"cost_per_kg": 0, "recipe": None, "breakdown": []}

    batch = float(recipe.batch_size_kg or 100)

    cost = 0.0
    breakdown = []
    for ing in recipe.ingredients:
        kg = float(ing.quantity_kg or 0)
        if kg <= 0 or not ing.inventory:
            continue
        inv = ing.inventory
        if inv.price_per_unit:
            per_kg = (kg / batch) * float(inv.price_per_unit)
            cost += per_kg
            breakdown.append({
                "name": inv.item_name,
                "kg_per_batch": kg,
                "price": float(inv.price_per_unit),
                "cost_per_kg": round(per_kg, 2)
            })

    recipe_name = recipe.name.value if hasattr(recipe.name, 'value') else str(recipe.name)
    return {
        "cost_per_kg": round(cost, 2),
        "recipe": recipe_name,
        "recipe_id": recipe.id,
        "batch_size": batch,
        "breakdown": breakdown
    }


# ============================================================
# USTA KPI VA HODIM TO'LOVI — Oylik hisobga qo'shish
# ============================================================

def calculate_monthly_master_kpi(db: Session, year: int, month: int) -> dict:
    """Shu oy SOF FOYDASIDAN usta KPI xarajatini hisoblaydi (yillik jamlanadi,
    lekin har oy tegishli ulushi xarajat sifatida yoziladi)."""
    from models import Order, OrderStatus, Master
    from sqlalchemy import extract

    masters = db.query(Master).filter(Master.is_active == True, Master.kpi_percent > 0).all()
    breakdown = []
    total = 0.0

    for m in masters:
        orders = db.query(Order).filter(
            Order.master_id == m.id,
            Order.status == OrderStatus.READY,
            extract('year', Order.completed_at) == year,
            extract('month', Order.completed_at) == month,
            Order.is_deleted.isnot(True)
        ).all()
        if not orders:
            continue

        monthly_profit = 0.0
        for o in orders:
            try:
                profit_data = calculate_order_profit(db, o.id)
                monthly_profit += float(profit_data.get("foyda", 0))
            except Exception:
                pass

        if monthly_profit <= 0:
            continue

        kpi_amount = monthly_profit * m.kpi_percent / 100
        total += kpi_amount
        breakdown.append({
            "master_name": m.name,
            "kpi_percent": m.kpi_percent,
            "monthly_profit": round(monthly_profit),
            "kpi_amount": round(kpi_amount)
        })

    return {"total": round(total), "breakdown": breakdown}


def calculate_monthly_employee_pay(db: Session, year: int, month: int,
                                   daromad: float, sof_foyda_before: float,
                                   jami_metr: float, jami_dona: float,
                                   jami_blok: float, jami_qoplama_birlik: float = 0.0) -> dict:
    """Moslashuvchan hodimlar uchun oylik to'lovni hisoblaydi.
    daromad, sof_foyda_before — shu oy uchun (hodim xarajatlarigacha).
    jami_metr/dona/blok — shu oy ishlab chiqarilgan miqdorlar (hammasi).
    jami_qoplama_birlik — shu oy QOPLANGAN detallar: metr + dona (profil/panel metrda,
    donali dona bilan, bittalashtirib qo'shilgan) — qoplamachi bonusi uchun."""
    from models import Employee, PayType

    employees = db.query(Employee).filter(Employee.is_active == True).all()
    breakdown = []
    total = 0.0

    unit_map = {"metr": jami_metr, "dona": jami_dona, "blok": jami_blok}

    for e in employees:
        amount = 0.0
        detail = ""

        if e.pay_type == PayType.FIXED:
            amount = float(e.fixed_amount or 0)
            detail = f"Doimiy oylik"

        elif e.pay_type == PayType.PERCENT_SALES:
            amount = daromad * float(e.percent_value or 0) / 100
            detail = f"Sotuv {fmt_num(daromad)} × {e.percent_value}%"

        elif e.pay_type == PayType.PERCENT_PROFIT:
            amount = max(0, sof_foyda_before) * float(e.percent_value or 0) / 100
            detail = f"Foyda {fmt_num(sof_foyda_before)} × {e.percent_value}%"

        elif e.pay_type == PayType.PER_UNIT:
            qty = unit_map.get(e.per_unit_type, 0)
            amount = qty * float(e.per_unit_rate or 0)
            detail = f"{qty:g} {e.per_unit_type} × {fmt_num(e.per_unit_rate)}"

        elif e.pay_type == PayType.FIXED_PLUS_COATING:
            base = float(e.fixed_amount or 0)
            rate = float(e.per_unit_rate or 1000)
            bonus = jami_qoplama_birlik * rate
            amount = base + bonus
            detail = f"Oylik {fmt_num(base)} + {jami_qoplama_birlik:g} metr/dona × {fmt_num(rate)} = {fmt_num(bonus)}"

        if amount > 0:
            total += amount
            avans = get_employee_advances_total(db, e.id, year, month)
            breakdown.append({
                "employee_id": e.id,
                "name": e.name,
                "position": e.position,
                "pay_type": e.pay_type.value,
                "detail": detail,
                "amount": round(amount),
                "avans": round(avans),
                "qolgan": round(amount - avans)
            })

    return {"total": round(total), "breakdown": breakdown}


def get_employee_advances_total(db: Session, employee_id: int, year: int, month: int) -> float:
    """Hodimga shu OYda berilgan barcha avanslar yig'indisi."""
    from models import EmployeeAdvance
    from sqlalchemy import extract as _extract, func as _func

    total = db.query(_func.sum(EmployeeAdvance.amount)).filter(
        EmployeeAdvance.employee_id == employee_id,
        _extract('year', EmployeeAdvance.date) == year,
        _extract('month', EmployeeAdvance.date) == month
    ).scalar()
    return float(total or 0)


def get_employee_advances_list(db: Session, employee_id: int, year: int, month: int) -> list:
    """Hodimga shu OYda berilgan barcha avanslar ro'yxati (sana, summa, izoh bilan)."""
    from models import EmployeeAdvance
    from sqlalchemy import extract as _extract

    rows = db.query(EmployeeAdvance).filter(
        EmployeeAdvance.employee_id == employee_id,
        _extract('year', EmployeeAdvance.date) == year,
        _extract('month', EmployeeAdvance.date) == month
    ).order_by(EmployeeAdvance.date.desc()).all()
    return [{
        "id": r.id,
        "amount": float(r.amount or 0),
        "date": r.date.isoformat() if r.date else None,
        "notes": r.notes,
        "given_by": r.given_by
    } for r in rows]


def fmt_num(n):
    try:
        return f"{n:,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def get_order_item_unit_cost(db: Session, order, item) -> float:
    """Bitta detalning 1 birlik (metr/dona) TAN NARXI — penoplast + loy (qoplamali bo'lsa).
    Brak qiymatini hisoblash uchun — sotuv narxi emas, xomashyo qiymati."""
    from models import Inventory

    if getattr(item, 'finished_product_id', None):
        return 0.0  # Tayyor mahsulotdan olingan — o'z tan narxi bor

    default_p = get_default_penoplast(db)
    volume = _item_volume_m3(db, item, default_p)
    pid = item.penoplast_id or (default_p.id if default_p else None)

    peno_cost_total = 0.0
    if volume > 0 and pid:
        p = db.query(Inventory).filter(Inventory.id == pid).first()
        if p and p.volume_per_unit:
            blocks = volume / float(p.volume_per_unit)
            peno_cost_total = blocks * float(p.price_per_unit or 0)

    qty_units = item.order_qty_normalized
    peno_cost_per_unit = (peno_cost_total / qty_units) if qty_units > 0 else 0.0

    loy_cost_per_unit = 0.0
    if item.is_coated and order:
        loy_kg = 0.0
        if order.notes:
            for part in str(order.notes).split(','):
                p2 = part.strip()
                if p2.startswith('loy_kg='):
                    try:
                        loy_kg = float(p2.split('=')[1])
                    except (ValueError, IndexError):
                        pass
                    break
        if loy_kg <= 0:
            loy_kg = _get_planned_loy(order)

        total_coated_units = 0.0
        recipe_id = None
        for oi in order.items:
            if not oi.is_coated:
                continue
            total_coated_units += oi.order_qty_normalized
            if not recipe_id and oi.recipe_id:
                recipe_id = oi.recipe_id

        if loy_kg > 0 and total_coated_units > 0:
            loy_kg_per_unit = loy_kg / total_coated_units
            loy_info = get_loy_cost_per_kg(db, recipe_id)
            loy_cost_per_unit = loy_kg_per_unit * float(loy_info.get("cost_per_kg", 0))

    return round(peno_cost_per_unit + loy_cost_per_unit)
