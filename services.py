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

    # === AVVAL TEKSHIRUV ===
    shortages = []

    # 1. Penoplast hajmi tekshirish
    # Formula:
    # PROFIL: (h × w / 2) sm² × length(m) × 100 / 1,000,000 = m³
    # PANEL:  h × w × t sm³ × quantity / 1,000,000 = m³
    total_volume_m3 = 0
    for item in order.items:
        if item.category == "panel":
            if item.width and item.thickness:
                w2 = item.width
                if item.notes and "width2=" in str(item.notes):
                    try:
                        for part in item.notes.split(","):
                            if "width2=" in part:
                                w2 = float(part.split("=")[1].strip())
                                break
                    except:
                        pass
                len_sm = (item.length * 100) if item.length and item.length > 0 else 1
                volume = (item.width * w2 * item.thickness * len_sm * item.quantity) / 1_000_000
                total_volume_m3 += volume
        elif item.category == "profil":
            if item.width and item.thickness and item.length:
                volume = (item.width/100) * (item.thickness/100) / 2 * item.length * float(item.quantity or 1)
                total_volume_m3 += volume
        elif item.category == "dona":
            # Donali detal: 1 dona narxi / 1 kub narxi = 1 dona uchun kub
            # Misol: 25,000 / 1,100,000 = 0.0227 m³ × miqdor
            if item.unit_price and float(item.unit_price) > 0:
                penoplast_check = db.query(Inventory).filter(
                    Inventory.item_name.ilike("%penoplast%")
                ).first()
                if penoplast_check and penoplast_check.price_per_unit and float(penoplast_check.price_per_unit) > 0:
                    volume_per_dona = float(item.unit_price) / float(penoplast_check.price_per_unit)
                    total_volume_m3 += volume_per_dona * float(item.quantity)
        else:
            if item.width and item.thickness and item.length:
                volume = (item.width * item.thickness * item.length * 100 * item.quantity) / 1_000_000
                total_volume_m3 += volume

    if total_volume_m3 > 0:
        calc = calculate_blocks_needed(total_volume_m3)
        blocks_needed = calc["blocks_needed"]
        penoplast = db.query(Inventory).filter(
            Inventory.item_name.ilike("%penoplast%")
        ).first()
        if not penoplast:
            shortages.append(f"⚠️ Omborda 'Penoplast' yo'q (kerak: {blocks_needed} dona)")
        elif penoplast.stock_quantity < blocks_needed:
            shortages.append(
                f"⚠️ Penoplast yetarli emas: kerak {blocks_needed}, omborda {penoplast.stock_quantity:.0f} {penoplast.unit}"
            )

    # 2. Qoplama xomashyolarini tekshirish
    if loy_kg and loy_kg > 0:
        recipe_id = None
        for item in order.items:
            if item.recipe_id:
                recipe_id = item.recipe_id
                break
        if recipe_id:
            recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
            if recipe:
                area_m2 = loy_kg / KG_PER_SQUARE_METER
                calc = calculate_coating_materials(area_m2, recipe)
                for comp_name, qty_needed in calc["materials"].items():
                    inv_item = db.query(Inventory).filter(
                        Inventory.item_name.ilike(f"%{comp_name}%")
                    ).first()
                    if not inv_item:
                        shortages.append(f"⚠️ '{comp_name}' omborda yo'q (kerak: {qty_needed:.2f})")
                    elif inv_item.stock_quantity < qty_needed:
                        shortages.append(
                            f"⚠️ {inv_item.item_name}: kerak {qty_needed:.2f}, bor {inv_item.stock_quantity:.2f} {inv_item.unit}"
                        )

    # Agar yetarli emas — buyurtmani tasdiqlamaymiz!
    if shortages:
        return {
            "success": False,
            "message": "❌ Buyurtmani tasdiqlash mumkin emas — xomashyo yetarli emas!",
            "shortages": shortages
        }

    # === HAMMA NARSA TAYYOR — BAJARAMIZ ===
    result = {
        "success": True,
        "message": "✓ Buyurtma yakunlandi!",
        "inventory_changes": [],
        "master_kpi": None
    }

    # LOY INGREDIENTLARINI AYIRISH (tayyor bosilganda haqiqiy miqdor)
    if loy_kg and loy_kg > 0:
        loy_log = deduct_loy_ingredients(db, order, loy_kg)
        result["inventory_changes"].extend(loy_log)

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
        if 'loy_kg=' not in existing_notes:
            order.notes = (existing_notes + f',loy_kg={loy_kg}').strip(',')
        else:
            # Yangilaymiz
            parts = [p for p in existing_notes.split(',') if 'loy_kg=' not in p]
            parts.append(f'loy_kg={loy_kg}')
            order.notes = ','.join(parts)
    db.commit()
    db.refresh(order)

    return result


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
        cnt = db.query(Order).filter(Order.status == status).count()
        statuses[status.value] = cnt

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
        if order.notes and 'loy_kg=' in order.notes:
            try:
                for part in order.notes.split(','):
                    if 'loy_kg=' in part:
                        loy_kg = float(part.split('=')[1].strip())
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
                "kroshka": recipe.kroshka_kg,
                "mel": recipe.shtukaturka_kg,
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

    # ── 3. XARAJATLAR (bazadan) ──────────────────────────────
    expense = db.query(MonthlyExpense).filter(
        MonthlyExpense.year  == year,
        MonthlyExpense.month == month
    ).first()

    if not expense:
        # Bo'sh xarajat
        xarajatlar = {
            "arenda": 0, "elektr": 0, "tushlik": 0,
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

    # Jami xarajat
    jami_xarajat = (
        xarajatlar["arenda"] +
        xarajatlar["elektr"] +
        xarajatlar["tushlik"] +
        xarajatlar["hodim1_oylik"] +
        xarajatlar["hodim2_oylik"] +
        xarajatlar["hodim3_oylik"] +
        xarajatlar["qoplamachi_oylik"] +
        xarajatlar["qoplamachi_bonus"]
    )

    sof_foyda = sof_daromad - jami_xarajat
    foyda_foiz = (sof_foyda / daromad * 100) if daromad > 0 else 0

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
        "expense_id": expense.id if expense else None
    }


def save_monthly_expense(db: Session, year: int, month: int, data: dict):
    """Oylik xarajatlarni saqlaydi yoki yangilaydi."""
    from models import MonthlyExpense

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
    return expense


# ============================================================
# BUYURTMA SAQLASHDA OMBOR TEKSHIRUVI VA AYIRISH
# ============================================================

def check_inventory_for_order(db: Session, order_data) -> dict:
    """
    Buyurtma uchun xomashyo yetishini tekshiradi.
    Qaytaradi: {"enough": True/False, "shortages": [...]}
    """
    from models import Inventory

    shortages = []
    total_volume_m3 = 0.0

    for item in order_data.items:
        cat = (item.category or '').lower()
        qty = float(item.quantity or 1)

        if cat == 'profil':
            if item.width and item.thickness and item.length:
                vol = (item.width/100) * (item.thickness/100) / 2 * item.length
                total_volume_m3 += vol
        elif cat == 'panel':
            if item.width and item.thickness:
                vol = (item.width/100) * (item.thickness/100) * qty
                total_volume_m3 += vol
        elif cat == 'dona':
            if item.unit_price and float(item.unit_price) > 0:
                penoplast = db.query(Inventory).filter(
                    Inventory.item_name.ilike("%penoplast%")
                ).first()
                if penoplast and penoplast.price_per_unit:
                    vol = float(item.unit_price) / float(penoplast.price_per_unit) * qty
                    total_volume_m3 += vol

    # Penoplast tekshiruvi
    if total_volume_m3 > 0:
        penoplast = db.query(Inventory).filter(
            Inventory.item_name.ilike("%penoplast%")
        ).first()
        if penoplast:
            vol_per_unit = float(penoplast.volume_per_unit or 1.0)
            blocks_needed = total_volume_m3 / vol_per_unit
            if float(penoplast.stock_quantity) < blocks_needed:
                shortages.append(
                    f"Penoplast: kerak {blocks_needed:.1f} blok, "
                    f"qoldi {float(penoplast.stock_quantity):.1f} blok"
                )

    return {
        "enough": len(shortages) == 0,
        "shortages": shortages,
        "total_volume_m3": round(total_volume_m3, 3)
    }


def deduct_inventory_for_order(db: Session, order) -> list:
    """
    Buyurtma saqlangandan keyin ombordan xomashyo ayiradi.
    Qaytaradi: ayirilgan xomashyolar ro'yxati.
    """
    from models import Inventory

    log = []
    total_volume_m3 = 0.0

    for item in order.items:
        cat = (item.category or '').lower()
        qty = float(item.quantity or 1)

        if cat == 'profil':
            if item.width and item.thickness and item.length:
                vol = (item.width/100) * (item.thickness/100) / 2 * item.length
                total_volume_m3 += vol
        elif cat == 'panel':
            if item.width and item.thickness:
                vol = (item.width/100) * (item.thickness/100) * qty
                total_volume_m3 += vol
        elif cat == 'dona':
            if item.unit_price and float(item.unit_price) > 0:
                penoplast = db.query(Inventory).filter(
                    Inventory.item_name.ilike("%penoplast%")
                ).first()
                if penoplast and penoplast.price_per_unit:
                    vol = float(item.unit_price) / float(penoplast.price_per_unit) * qty
                    total_volume_m3 += vol

    # Penoplast ayirish
    if total_volume_m3 > 0:
        penoplast = db.query(Inventory).filter(
            Inventory.item_name.ilike("%penoplast%")
        ).first()
        if penoplast:
            vol_per_unit = float(penoplast.volume_per_unit or 1.0)
            blocks_needed = total_volume_m3 / vol_per_unit
            penoplast.stock_quantity = max(0, float(penoplast.stock_quantity) - blocks_needed)
            db.commit()
            log.append(f"Penoplast: -{blocks_needed:.2f} blok")

    return log


def return_inventory_for_order(db: Session, order) -> list:
    """
    Buyurtma o'chirilganda omborga xomashyo qaytaradi.
    deduct_inventory_for_order ning teskarisi.
    """
    from models import Inventory

    log = []
    total_volume_m3 = 0.0

    for item in order.items:
        cat = (item.category or '').lower()
        qty = float(item.quantity or 1)

        if cat == 'profil':
            if item.width and item.thickness and item.length:
                vol = (item.width/100) * (item.thickness/100) / 2 * float(item.length)
                total_volume_m3 += vol
        elif cat == 'panel':
            if item.width and item.thickness:
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

    # Penoplast qaytarish
    if total_volume_m3 > 0:
        penoplast = db.query(Inventory).filter(
            Inventory.item_name.ilike("%penoplast%")
        ).first()
        if penoplast:
            vol_per_unit = float(penoplast.volume_per_unit or 1.0)
            blocks_to_return = total_volume_m3 / vol_per_unit
            penoplast.stock_quantity = float(penoplast.stock_quantity) + blocks_to_return
            db.commit()
            log.append(f"Penoplast: +{blocks_to_return:.2f} blok qaytarildi")

    return log


def deduct_loy_ingredients(db: Session, order, loy_kg: float) -> list:
    """
    Loy (qoplama) uchun ingredientlarni ombordan ayiradi.
    Retsept bo'yicha hisoblanadi.
    """
    from models import Inventory, Recipe

    if loy_kg <= 0:
        return []

    log = []

    # Retseptni order.items dan topamiz
    recipe = None
    for item in order.items:
        if hasattr(item, 'recipe_id') and item.recipe_id:
            recipe = db.query(Recipe).filter(Recipe.id == item.recipe_id).first()
            if recipe:
                break

    # Topilmasa — birinchi retseptni olamiz
    if not recipe:
        recipe = db.query(Recipe).first()

    if not recipe:
        print("⚠ Retsept topilmadi — loy ingredientlari ayirilmadi")
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
            inv_item.stock_quantity = max(0, float(inv_item.stock_quantity) - needed_kg)
            log.append(f"{inv_item.item_name}: -{needed_kg:.2f} {inv_item.unit}")
            print(f"✓ {inv_item.item_name}: -{needed_kg:.2f} ayirildi")

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

    db.commit()
    return log
