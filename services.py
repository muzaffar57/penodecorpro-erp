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
    ).first()

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

    materials = {
        "Akril": recipe.akril_kg * coefficient,
        "PVA": recipe.pva_kg * coefficient,
        "Qum": recipe.qum_kg * coefficient,
        "Kroshka": recipe.kroshka_kg * coefficient,
        "Penogasitel": recipe.penogasitel_kg * coefficient,
        "Shtukaturka": recipe.shtukaturka_kg * coefficient,
        "Suv": recipe.suv_kg * coefficient,
        "Biotsid": recipe.biotsid_ml * coefficient,  # ml da
    }

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
        ).first()

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
    empty_items = db.query(Inventory).filter(Inventory.stock_quantity <= 0).all()
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
    items = db.query(Inventory).filter(Inventory.stock_quantity > 0).all()
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
        Order.completed_at >= today_start, Order.completed_at < today_end
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
        Order.status.notin_([OrderStatus.READY, OrderStatus.DELIVERED, OrderStatus.CANCELLED])
    ).count()

    in_production = db.query(Order).filter(
        Order.status.in_([OrderStatus.IN_PROGRESS, OrderStatus.COATING])
    ).count()

    due_today = db.query(Order).filter(
        Order.deadline >= today_start, Order.deadline < today_end,
        Order.status.notin_([OrderStatus.DELIVERED, OrderStatus.CANCELLED])
    ).count()

    active_masters = db.query(Order.master_id).filter(
        Order.master_id.isnot(None),
        Order.status.in_([OrderStatus.NEW, OrderStatus.IN_PROGRESS, OrderStatus.COATING])
    ).distinct().count()

    completed_today = db.query(Order).filter(
        Order.completed_at >= today_start, Order.completed_at < today_end,
        Order.status == OrderStatus.READY
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
    total_orders = db.query(Order).count()
    active_orders = db.query(Order).filter(Order.status != OrderStatus.READY).count()
    ready_orders = db.query(Order).filter(Order.status == OrderStatus.READY).count()
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
    planned_loy = _get_planned_loy(order)
    actual_loy = float(loy_kg or 0)

    if actual_loy > 0:
        recipe = _get_order_recipe(db, order)
        diff = actual_loy - planned_loy

        if diff > 0.01:
            # Ko'proq ketdi — farq uchun xomashyo ayiramiz
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
            # Kam ketdi — ortgani omborga
            extra = abs(diff)
            msg = add_loy_to_stock(db, recipe, extra)
            if msg:
                result["inventory_changes"].append(msg)
            result["loy_info"] = {
                "planned": planned_loy,
                "actual": actual_loy,
                "diff": round(diff, 1),
                "action": "ortdi",
                "message": f"{extra:.1f} kg loy ortdi — omborga qo'shildi"
            }
        else:
            result["loy_info"] = {
                "planned": planned_loy,
                "actual": actual_loy,
                "diff": 0,
                "action": "teng",
                "message": "Reja bo'yicha ketdi"
            }
    elif planned_loy > 0:
        # Haqiqiy miqdor kiritilmadi — reja bo'yicha deb hisoblaymiz
        result["loy_info"] = {
            "planned": planned_loy,
            "actual": planned_loy,
            "diff": 0,
            "action": "teng",
            "message": "Reja bo'yicha hisoblandi"
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
            Order.created_at < month_end
        ).count()

        revenue = db.query(func.sum(Order.total_amount)).filter(
            Order.created_at >= month_start,
            Order.created_at < month_end,
            Order.status == OrderStatus.READY
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
            cnt = db.query(Order).filter(Order.status == status).count()
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
            Order.status == OrderStatus.READY
        ).scalar() or 0
        order_count = db.query(Order).filter(
            Order.master_id == m.id
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

    sotuv_narxi = float(order.total_amount or 0)
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
            material_map = {
                "akril": recipe.akril_kg,
                "pva": recipe.pva_kg,
                "kvars qum": recipe.qum_kg,
                "travertin qum": getattr(recipe, "travertin_qum_kg", 0) or 0,
                "kroshka": recipe.kroshka_kg,
                "mel": recipe.shtukaturka_kg,
                "zagustitel": getattr(recipe, "zagustitel_kg", 0) or 0,
                "suv": recipe.suv_kg,
            }
            narx_per_kg = 0.0
            for inv_key, mat_kg in material_map.items():
                if float(mat_kg or 0) <= 0:
                    continue
                inv = db.query(Inventory).filter(
                    Inventory.item_name.ilike(f"%{inv_key}%")
                ).first()
                if inv and inv.price_per_unit:
                    narx_per_kg += (float(mat_kg) / batch) * float(inv.price_per_unit)

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
        extract('month', Order.completed_at) == month
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
        extract('month', Order.completed_at) == month
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

    # Jami xarajat (arenda/elektr/tushlik/soliq — hodim to'lovi endi
    # "Ustalar KPI / Hodimlar" bo'limida alohida hisoblanadi)
    jami_xarajat_eski = (
        xarajatlar["arenda"] +
        xarajatlar["elektr"] +
        xarajatlar["tushlik"] +
        xarajatlar["soliqlar"]
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

def get_penoplast_list(db: Session):
    """Barcha penoplast (plotnost) turlari."""
    from models import Inventory
    from sqlalchemy import or_
    try:
        items = db.query(Inventory).filter(
            or_(
                Inventory.is_penoplast == True,
                Inventory.item_name.ilike("%penoplast%")
            )
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
        Inventory.is_default_penoplast == True
    ).first()
    if p:
        return p
    p = db.query(Inventory).filter(Inventory.is_penoplast == True).first()
    if p:
        return p
    return db.query(Inventory).filter(
        Inventory.item_name.ilike("%penoplast%")
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
        p = db.query(Inventory).filter(Inventory.id == pid).first()
        if not p:
            continue
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks_needed = vol / vol_per_unit
        p.stock_quantity = max(0, float(p.stock_quantity) - blocks_needed)
        log.append(f"{p.item_name}: -{blocks_needed:.2f} blok")

    if volumes:
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
        p = db.query(Inventory).filter(Inventory.id == pid).first()
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

    stock = db.query(Inventory).filter(Inventory.item_name == item_name).first()
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


def take_loy_from_stock(db: Session, recipe, kg_needed: float):
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
    db.commit()
    msg = f"{stock.item_name}: -{taken:.1f} kg (zaxiradan)"
    print(f"✓ {msg}")
    return taken, kg_needed - taken, msg


def deduct_loy_ingredients(db: Session, order, loy_kg: float, use_stock: bool = True) -> list:
    """
    Loy (qoplama) uchun ingredientlarni ombordan ayiradi.
    use_stock=True bo'lsa — avval tayyor loy zaxirasidan oladi.
    """
    from models import Inventory, Recipe

    if loy_kg <= 0:
        return []

    log = []

    recipe = _get_order_recipe(db, order)

    if not recipe:
        print("⚠ Retsept topilmadi — loy ingredientlari ayirilmadi")
        return []

    # 1) Avval tayyor loy zaxirasidan olamiz
    if use_stock:
        taken, loy_kg, msg = take_loy_from_stock(db, recipe, loy_kg)
        if msg:
            log.append(msg)
        if loy_kg <= 0:
            return log  # Zaxira yetdi, xomashyo kerak emas

    batch = float(recipe.batch_size_kg or 100)

    ingredient_map = [
        ("akril", recipe.akril_kg),
        ("pva", recipe.pva_kg),
        ("kvars qum", recipe.qum_kg),
        ("travertin qum", recipe.travertin_qum_kg),
        ("kroshka", recipe.kroshka_kg),
        ("mel", recipe.shtukaturka_kg),
        ("zagustitel", recipe.zagustitel_kg),
        ("suv", recipe.suv_kg),
        ("penogasitel", recipe.penogasitel_kg),
    ]

    for inv_name, recipe_kg in ingredient_map:
        if float(recipe_kg or 0) <= 0:
            continue
        needed_kg = loy_kg * (float(recipe_kg) / batch)
        inv_item = db.query(Inventory).filter(
            Inventory.item_name.ilike(f"%{inv_name}%")
        ).first()
        if inv_item:
            inv_item.stock_quantity = max(0, float(inv_item.stock_quantity) - needed_kg)
            log.append(f"{inv_item.item_name}: -{needed_kg:.2f} {inv_item.unit}")
            print(f"✓ {inv_item.item_name}: -{needed_kg:.2f} ayirildi")
            import crud as _crud
            _crud.log_movement(
                db, inv_item.id, inv_item.item_name, movement_type="out",
                quantity=needed_kg, unit=inv_item.unit,
                reason=f"Buyurtma {getattr(order, 'order_number', order.id)} (loy)",
                order_id=order.id
            )

    db.commit()
    return log


def return_loy_ingredients(db: Session, order, loy_kg: float) -> list:
    """
    Loy ingredientlarini omborga qaytaradi (buyurtma o'chirilganda).
    """
    from models import Inventory, Recipe

    if loy_kg <= 0:
        return []

    log = []

    recipe = None
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

    ingredient_map = [
        ("akril", recipe.akril_kg),
        ("pva", recipe.pva_kg),
        ("kvars qum", recipe.qum_kg),
        ("travertin qum", recipe.travertin_qum_kg),
        ("kroshka", recipe.kroshka_kg),
        ("mel", recipe.shtukaturka_kg),
        ("zagustitel", recipe.zagustitel_kg),
        ("suv", recipe.suv_kg),
        ("penogasitel", recipe.penogasitel_kg),
    ]

    for inv_name, recipe_kg in ingredient_map:
        if float(recipe_kg or 0) <= 0:
            continue
        needed_kg = loy_kg * (float(recipe_kg) / batch)
        inv_item = db.query(Inventory).filter(
            Inventory.item_name.ilike(f"%{inv_name}%")
        ).first()
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

        p = db.query(Inventory).filter(Inventory.id == pid).first()
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
    material_map = {
        "akril": recipe.akril_kg,
        "pva": recipe.pva_kg,
        "kvars qum": recipe.qum_kg,
        "travertin qum": getattr(recipe, "travertin_qum_kg", 0) or 0,
        "kroshka": recipe.kroshka_kg,
        "mel": recipe.shtukaturka_kg,
        "zagustitel": getattr(recipe, "zagustitel_kg", 0) or 0,
        "suv": recipe.suv_kg,
        "penogasitel": getattr(recipe, "penogasitel_kg", 0) or 0,
    }

    cost = 0.0
    breakdown = []
    for key, kg in material_map.items():
        if float(kg or 0) <= 0:
            continue
        inv = db.query(Inventory).filter(Inventory.item_name.ilike(f"%{key}%")).first()
        if inv and inv.price_per_unit:
            per_kg = (float(kg) / batch) * float(inv.price_per_unit)
            cost += per_kg
            breakdown.append({
                "name": inv.item_name,
                "kg_per_batch": float(kg),
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
            extract('month', Order.completed_at) == month
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
            breakdown.append({
                "name": e.name,
                "position": e.position,
                "pay_type": e.pay_type.value,
                "detail": detail,
                "amount": round(amount)
            })

    return {"total": round(total), "breakdown": breakdown}


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
