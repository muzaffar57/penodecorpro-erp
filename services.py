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



# ============================================================
# 2. AVTOMATIK KESISH (Penoplast bloklari)
# ============================================================

# Standart penoplast blok hajmi (m³)
PENOPLAST_BLOCK_VOLUME_M3 = 1.0  # 1 m × 1 m × 1 m = 1 m³
# Yo'qotish foizi (kesish vaqtida)
CUTTING_LOSS_PERCENT = 5.0  # 5% yo'qotish



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

def get_top_products_report(db: Session, days: int = 90, limit: int = 15,
                            company_id: int = None) -> list:
    """Eng ko'p daromad keltirgan mahsulotlar — nomi bo'yicha guruhlangan,
    tayyor (READY/DELIVERED) buyurtmalardagi OrderItem'lardan. Faqat o'qish.

    ⚠ 2026-09-21: `company_id` YO'Q edi — B korxona admini `/api/reports/
    top-products` orqali A korxonaning mahsulot nomlari va daromadini
    ko'rardi (HTTP da o'lchangan). Yonidagi `get_top_materials_report`
    da filtr bor edi, bu yerda tushib qolgan."""
    from models import OrderItem, Order, OrderStatus
    from sqlalchemy import func
    from datetime import datetime, timedelta

    period_start = datetime.utcnow() - timedelta(days=days)
    _q = db.query(
        OrderItem.name,
        func.sum(OrderItem.total_price).label("revenue"),
        func.sum(OrderItem.quantity).label("qty"),
        func.count(OrderItem.id).label("times_ordered")
    ).join(Order, OrderItem.order_id == Order.id)
    if company_id is not None:
        _q = _q.filter(Order.company_id == company_id)
    rows = _q.filter(
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


def get_top_materials_report(db: Session, days: int = 90, limit: int = 15,
                             company_id: int = None) -> list:
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
        *([InventoryMovement.company_id == company_id] if company_id is not None else []),
        InventoryMovement.movement_type == "out",
        InventoryMovement.created_at >= period_start
    ).group_by(InventoryMovement.item_name, InventoryMovement.unit).order_by(func.sum(InventoryMovement.quantity).desc()).limit(limit).all()

    return [{
        "item_name": r.item_name,
        "unit": r.unit,
        "total_qty": round(float(r.total_qty or 0), 2),
        "movement_count": r.movement_count,
    } for r in rows]


def get_top_customers_report(db: Session, days: int = 90, limit: int = 10, company_id: int = None) -> list:
    """Eng ko'p daromad keltirgan mijozlar (loyihalar) — tayyor buyurtmalar
    bo'yicha, mijoz nomi bo'yicha guruhlangan. Faqat o'qish."""
    from models import Order, Project, OrderStatus
    from sqlalchemy import func
    from datetime import datetime, timedelta

    period_start = datetime.utcnow() - timedelta(days=days)
    rows = db.query(
        Project.client_name,
        func.sum(func.coalesce(Order.agreed_amount, Order.total_amount, 0)).label("revenue"),
        func.count(Order.id).label("orders_count")
    ).join(Project, Order.project_id == Project.id).filter(
        Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED]),
        Order.completed_at >= period_start,
        *( [Order.company_id == company_id] if company_id is not None else [] )   # M6
    ).group_by(Project.client_name).order_by(func.sum(func.coalesce(Order.agreed_amount, Order.total_amount, 0)).desc()).limit(limit).all()

    return [{
        "client_name": r.client_name,
        "revenue": round(float(r.revenue or 0)),
        "orders_count": r.orders_count,
    } for r in rows]


def get_top_suppliers_report(db: Session, days: int = 90, limit: int = 10, company_id: int = None) -> list:
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
        InventoryPurchase.purchased_at >= period_start,
        *( [Supplier.company_id == company_id] if company_id is not None else [] )  # M6
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


def get_business_alerts(db: Session, company_id: int = None) -> list:
    """Muhim ogohlantirishlar ro'yxati — oddiy, aniq belgilangan
    chegaralar asosida. Faqat o'qish, hech narsani o'zgartirmaydi."""
    from models import Inventory, Order, OrderStatus
    from datetime import datetime
    from database import tashkent_date

    alerts = []

    # 1) Kam qolgan xomashyo (min_stock dan kam)
    # kech37 (21-band, foydalanuvchi qarori: "Ortgan loy uchun chegara shart
    # emas"): "Tayyor loy (...)" zaxirasi (`TAYYOR_LOY_PREFIKS` izohi) hech
    # qachon "kamaymoqda" deb chiqmaydi — hatto unga min > 0 qo'yilgan bo'lsa ham.
    _lsq = db.query(Inventory).filter(
        Inventory.is_deleted.isnot(True),
        Inventory.stock_quantity <= Inventory.min_stock,
        Inventory.min_stock > 0,
        ~Inventory.item_name.like(TAYYOR_LOY_PREFIKS + '%')
    )
    if company_id is not None:      # M6
        _lsq = _lsq.filter(Inventory.company_id == company_id)
    low_stock = _lsq.all()
    for item in low_stock[:5]:
        alerts.append({
            "level": "red",
            "text": f"Omborda {item.item_name} kamaymoqda ({item.stock_quantity:g} {item.unit} qoldi)"
        })

    # 2) Muddati o'tgan qarzdorlar (30+ kun oldin yaratilgan, hali qarzi bor)
    _odq = db.query(Order).filter(
        Order.is_deleted.isnot(True),
        Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED, OrderStatus.IN_PROGRESS])
    )
    if company_id is not None:      # M6
        _odq = _odq.filter(Order.company_id == company_id)
    old_debt_orders = _odq.all()
    overdue_count = 0
    for o in old_debt_orders:
        if float(o.debt_amount or 0) > 0 and o.created_at and (datetime.utcnow() - o.created_at).days > 30:
            overdue_count += 1
    if overdue_count > 0:
        alerts.append({"level": "red", "text": f"{overdue_count} ta qarzdorning muddati 30 kundan oshgan"})

    # 3) Bugungi savdo rekord (oxirgi 30 kunning eng yuqorisi)
    today_summary = get_daily_finance_summary(db, tashkent_date(), company_id=company_id)
    if today_summary["sales"]["total"] > 0:
        alerts.append({"level": "green", "text": f"Bugun {today_summary['sales']['orders_count']} ta buyurtma yakunlandi"})

    priority = {"red": 0, "orange": 1, "green": 2}
    alerts.sort(key=lambda a: priority.get(a["level"], 3))
    return alerts


def get_business_health(db: Session, company_id: int = None) -> dict:
    """6 ta asosiy ko'rsatkich bo'yicha oddiy holat (yashil/sariq/qizil).
    Chegaralar oddiy, tushunarli qoidalarga asoslangan. Faqat o'qish."""
    from datetime import datetime
    from models import Order

    now = datetime.utcnow()
    report = get_monthly_report(db, now.year, now.month, company_id=company_id)

    foyda_foiz = float(report.get("foyda_foiz", 0) or 0)
    rentabellik_status = "green" if foyda_foiz >= 15 else ("orange" if foyda_foiz >= 5 else "red")

    _bhq = db.query(Order).filter(Order.is_deleted.isnot(True))
    if company_id is not None:      # M6
        _bhq = _bhq.filter(Order.company_id == company_id)
    orders = _bhq.all()
    total_debt = sum(float(o.debt_amount or 0) for o in orders)
    total_revenue = sum(o.kelishilgan_summa for o in orders) or 1
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


def get_recurring_obligations(db: Session, company_id: int = None) -> list:
    """Barcha sozlangan doimiy majburiyatlar (Arenda, Soliq, Transport va
    ISTALGAN boshqa kategoriya) ro'yxati — sozlash sahifasi uchun."""
    from models import RecurringObligation
    _rq = db.query(RecurringObligation)
    if company_id is not None:      # M6
        _rq = _rq.filter(RecurringObligation.company_id == company_id)
    rows = _rq.order_by(RecurringObligation.label).all()
    return [{
        "id": r.id, "category": r.category, "label": r.label, "icon": r.icon or "📦",
        "monthly_target": float(r.monthly_target or 0), "due_day": r.due_day or 5,
        "is_active": r.is_active
    } for r in rows]


def set_recurring_obligation(db: Session, category: str, label: str, monthly_target: float,
                              icon: str = "📦", due_day: int = 5, company_id: int = None) -> dict:
    """Doimiy majburiyat kategoriyasini yaratadi yoki yangilaydi. Admin
    ISTALGAN yangi kategoriya nomini kiritishi mumkin."""
    from models import RecurringObligation
    import crud as _crud_obl
    # 17d (2026-09-21): qiymatlar QAT'IY (`crud._clean_majburiyat`) — xato
    # bo'lsa `ValueError`, hech narsa yozilmaydi. O'LCHANGAN: `inf` summa
    # "Qarzdorlar" sahifasini buzardi (500), `nan` → NULL, manfiy / 1e20
    # qabul; kun 0 / −3 / 99999; PostgreSQL da 30 belgidan uzun kod → 500.
    _toza = _crud_obl._clean_majburiyat(category, label, monthly_target,
                                        icon=icon, due_day=due_day)
    category, label = _toza["category"], _toza["label"]
    monthly_target, icon, due_day = (_toza["monthly_target"], _toza["icon"],
                                     _toza["due_day"])
    # M6 — TENANT: qidiruv ham, yangi yozuv ham korxona bilan. Ilgari
    # faqat `category` bo'yicha qidirilardi — A B ning majburiyatini
    # qayta yozib yuborishi mumkin edi.
    _oq = db.query(RecurringObligation).filter(RecurringObligation.category == category)
    if company_id is not None:
        _oq = _oq.filter(RecurringObligation.company_id == company_id)
    obl = _oq.first()
    if obl:
        obl.label = label
        obl.monthly_target = monthly_target
        obl.icon = icon
        obl.due_day = due_day
    else:
        obl = RecurringObligation(company_id=company_id, category=category, label=label,
                                   monthly_target=monthly_target,
                                   icon=icon, due_day=due_day, is_active=True)
        db.add(obl)
    db.commit()
    db.refresh(obl)
    return {"id": obl.id, "category": obl.category, "label": obl.label, "monthly_target": float(obl.monthly_target)}


def delete_recurring_obligation(db: Session, obligation_id: int, company_id: int = None) -> bool:
    """Doimiy majburiyat kategoriyasini o'chiradi (xarajat tarixi saqlanib qoladi)."""
    from models import RecurringObligation
    _dq = db.query(RecurringObligation).filter(RecurringObligation.id == obligation_id)
    if company_id is not None:      # M6: faqat shu korxonadan
        _dq = _dq.filter(RecurringObligation.company_id == company_id)
    obl = _dq.first()
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


def get_company_obligations_status(db: Session, year: int, month: int,
                                  company_id: int = None) -> dict:
    """Kompaniyaning O'ZI kimlarga qarzdorligini — bitta joyda yig'ib beradi:
    1) Hodimlarga (oylik hisob-kitobdagi 'qolgan')
    2) Doimiy majburiyatlar (Arenda, Soliq, Transport va h.k.)
    Ikkalasi ham — FAQAT o'qish, mavjud, sinalgan hisob-kitoblardan foydalanadi.

    MUHIM (2026-09): Hodimlar qarzi — FAQAT "hozirgi oy"ni emas, balki
    OXIRGI 3 OYni (hozirgi + oldingi 2 ta) tekshiradi. Sabab: agar oylik,
    masalan, 3-4 kun kechikib, yangi oyga o'tib to'lansa — eski (masalan
    o'tgan oy) qarzi, avvalgi versiyada, "hozirgi oy" bo'lib qolgani uchun,
    ko'rinishdan BUTUNLAY yo'qolib qolar edi (garchi hali to'lanmagan
    bo'lsa ham). Endi, har bir yozuv, aynan QAYSI oyga tegishli ekanini
    ("year"/"month" maydonlari orqali) aniq bildiradi — shu orqali,
    "To'landi" tugmasi bosilganda, to'lov TO'G'RI oyga yozilishi ta'minlanadi."""
    from models import RecurringObligation, ExpenseTransaction
    from sqlalchemy import func
    from datetime import datetime

    today = datetime.utcnow()
    OY_NOMLARI = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
                  "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]

    # Oxirgi 3 oyni (hozirgi + oldingi 2 ta) tekshiramiz
    months_to_check = []
    y, m = year, month
    for _ in range(3):
        months_to_check.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1

    employees_with_debt = []
    for (chk_year, chk_month) in months_to_check:
        # MUHIM: to'g'ridan-to'g'ri calculate_monthly_employee_pay(...,0,0,0,0,0)
        # chaqirilsa — "necha metr/blok ishlatilgan" kabi HAQIQIY miqdorlar
        # o'rniga "0" yuborilgan bo'lardi, va shu sabab "har birlik uchun"
        # turidagi (Blok, Metr) xodimlar SUMMASI har doim "0" chiqib qolar edi.
        # Shuning uchun, o'sha haqiqiy miqdorlarni ALLAQACHON to'g'ri hisoblab
        # bergan get_monthly_report()dan foydalanamiz.
        monthly = get_monthly_report(db, chk_year, chk_month, company_id=company_id)
        emp_result = {"breakdown": monthly.get("hodimlar_moslashuvchan_breakdown", [])}
        is_current = (chk_year, chk_month) == (year, month)
        for e in emp_result["breakdown"]:
            if e["qolgan"] <= 0.5:
                continue
            employees_with_debt.append({
                "employee_id": e["employee_id"], "name": e["name"], "detail": e["detail"],
                "amount": e["amount"], "avans": e["avans"], "qolgan": e["qolgan"],
                "year": chk_year, "month": chk_month,
                "month_label": OY_NOMLARI[chk_month] if not is_current else f"{OY_NOMLARI[chk_month]} (joriy)",
                "status": "overdue" if (not is_current or today.day > 5) else "partial",
            })
    # Eng eski oy, birinchi (eng "shoshilinch") bo'lib ko'rinsin
    employees_with_debt.sort(key=lambda e: (e["year"], e["month"]))
    total_employee_debt = sum(e["qolgan"] for e in employees_with_debt)

    recurring = []
    _obq = db.query(RecurringObligation).filter(RecurringObligation.is_active == True)
    if company_id is not None:      # M6
        _obq = _obq.filter(RecurringObligation.company_id == company_id)
    obligations = _obq.all()
    for obl in obligations:
        target = float(obl.monthly_target or 0)
        if target <= 0:
            continue
        # MUHIM (2026-09): xuddi hodimlar kabi — faqat "hozirgi oy"ni emas,
        # OXIRGI 3 OYni ham tekshiramiz. Aks holda, masalan Arenda,
        # o'tgan oyda to'lanmay, yangi oyga o'tib ketsa — bu yerdan
        # butunlay yo'qolib qolar edi (garchi hali to'lanmagan bo'lsa ham).
        for (chk_year, chk_month) in months_to_check:
            # Bu majburiyat, hali YARATILMAGAN oy uchun — tekshirmaymiz
            # (aynan hodim ishga kirish sanasi bilan bir xil mantiq).
            if obl.created_at:
                _last_day_chk = __import__('calendar').monthrange(chk_year, chk_month)[1]
                _chk_month_end = datetime(chk_year, chk_month, _last_day_chk, 23, 59, 59)
                if obl.created_at > _chk_month_end:
                    continue
            is_current = (chk_year, chk_month) == (year, month)
            _txq = db.query(ExpenseTransaction).filter(
                ExpenseTransaction.category == obl.category,
                func.extract('year', ExpenseTransaction.date) == chk_year,
                func.extract('month', ExpenseTransaction.date) == chk_month
            )
            if company_id is not None:      # M6
                _txq = _txq.filter(ExpenseTransaction.company_id == company_id)
            txs = _txq.order_by(ExpenseTransaction.date.desc()).all()
            paid = sum(float(t.amount or 0) for t in txs)
            debt = max(0, target - paid)
            if debt <= 0.5:
                continue
            last_payment = txs[0].date.isoformat() if txs else None
            recurring.append({
                "category": obl.category, "label": obl.label, "icon": obl.icon or "📦",
                "target": round(target), "paid": round(paid), "debt": round(debt),
                "due_day": obl.due_day or 5, "last_payment": last_payment,
                "year": chk_year, "month": chk_month,
                "month_label": OY_NOMLARI[chk_month] if not is_current else f"{OY_NOMLARI[chk_month]} (joriy)",
                "status": "overdue" if (not is_current or _obligation_status(debt, obl.due_day or 5, today) == "overdue") else _obligation_status(debt, obl.due_day or 5, today)
            })
    recurring_with_debt = sorted(recurring, key=lambda r: (r["year"], r["month"]))
    total_recurring_debt = sum(r["debt"] for r in recurring_with_debt)

    return {
        "employees": employees_with_debt,
        "total_employee_debt": round(total_employee_debt),
        "recurring": recurring_with_debt,
        "recurring_all": recurring,
        "total_recurring_debt": round(total_recurring_debt),
        "total_company_debt": round(total_employee_debt + total_recurring_debt),
    }


def get_full_debt_summary(db: Session, year: int, month: int,
                         company_id: int = None) -> dict:
    """"Moliya" sahifasi (va uning PDF hisoboti) uchun — TO'RTALA qarz
    yo'nalishini, BITTA joyga jamlab beradi:
    1) Bizga qarzdorlar — mijozlar (loyihalar)
    2) Yetkazib beruvchiga qarzimiz
    3) Hodimlarga qarzimiz (oxirgi 3 oy)
    4) Doimiy majburiyatlar (Arenda/Soliq/Kommunal)

    MUHIM: bu funksiya, hech qanday YANGI hisoblash qilmaydi — faqat,
    ALLAQACHON mavjud, boshqa joylarda (Qarzdorlar sahifasida) sinalgan
    funksiyalarni chaqirib, natijalarini bitta joyga yig'ib beradi."""
    from models import Order, OrderStatus

    # M6 (2026-09-18) — TENANT: mijoz qarzi, ta'minotchi qarzi va
    # kompaniyaning o'z majburiyatlari — hammasi joriy korxona bo'yicha.
    _oq = db.query(Order).filter(
        Order.is_deleted.isnot(True),
        Order.status != OrderStatus.DRAFT
    )
    if company_id is not None:
        _oq = _oq.filter(Order.company_id == company_id)
    orders = _oq.all()
    order_debts = [o for o in orders if float(o.debt_amount or 0) > 0.5]
    total_customer_debt = round(sum(float(o.debt_amount or 0) for o in order_debts))

    import crud as _crud_debt
    suppliers_all = _crud_debt.get_suppliers_with_debt(db, company_id=company_id)
    supplier_debts = [s for s in suppliers_all if s['debt'] > 0]
    total_supplier_debt = round(sum(s['debt'] for s in supplier_debts))

    company = get_company_obligations_status(db, year, month, company_id=company_id)

    return {
        "customer_debt": total_customer_debt,
        "customer_debt_count": len(order_debts),
        "supplier_debt": total_supplier_debt,
        "supplier_debt_count": len(supplier_debts),
        "employee_debt": company["total_employee_debt"],
        "employee_debt_count": len(company["employees"]),
        "recurring_debt": company["total_recurring_debt"],
        "recurring_debt_count": len(company["recurring"]),
        "net_position": total_customer_debt - total_supplier_debt - company["total_employee_debt"] - company["total_recurring_debt"],
    }


def get_obligation_timeline(db: Session, category: str, year: int, month: int,
                           company_id: int = None) -> list:
    """Bitta kategoriya uchun, shu oydagi barcha to'lovlar tarixi (timeline)."""
    from models import ExpenseTransaction
    from sqlalchemy import func
    _tq = db.query(ExpenseTransaction).filter(
        ExpenseTransaction.category == category,
        func.extract('year', ExpenseTransaction.date) == year,
        func.extract('month', ExpenseTransaction.date) == month
    )
    if company_id is not None:      # M6
        _tq = _tq.filter(ExpenseTransaction.company_id == company_id)
    txs = _tq.order_by(ExpenseTransaction.date.desc()).all()
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


def get_production_period_stats(db: Session, company_id: int = None) -> dict:
    """Ishlab chiqarish — bugun/hafta/oy bo'yicha nechta mahsulot chiqqani.
    Faqat o'qish, FinishedProduct.created_at (source=produced) asosida.

    2026-09-18 — TENANT (M7 validatsiyasida topilgan TO'RTINCHI sizish):
    funksiyada `company_id` parametri UMUMAN yo'q edi va `FinishedProduct`
    butun tizim bo'yicha sanalardi — ya'ni har qanday korxonaning
    boshqaruv paneli boshqa korxonalarning ishlab chiqarish miqdorini
    ham ko'rsatardi.

    `company_id` FAQAT autentifikatsiya kontekstidan keladi
    (`main.py` → `auth.company_id_of(current_user)`); mijoz so'rovidan
    olinmaydi va hech qanday standart 1-korxonaga tushmaydi.
    Hisoblash formulasi (bugun/hafta/oy chegaralari, miqdorlar yig'indisi)
    O'ZGARTIRILMADI."""
    from models import FinishedProduct, StockSource
    from datetime import datetime, timedelta
    from database import tashkent_today_start_utc

    today_start = tashkent_today_start_utc()
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    def _count_since(since):
        q = db.query(FinishedProduct).filter(
            FinishedProduct.source == StockSource.PRODUCED,
            FinishedProduct.created_at >= since
        )
        if company_id is not None:
            q = q.filter(FinishedProduct.company_id == company_id)
        items = q.all()
        return round(sum(float(i.quantity or 0) for i in items))

    return {
        "today": _count_since(today_start),
        "week": _count_since(week_start),
        "month": _count_since(month_start),
    }


# kech36 (K35-1): "Tayyor loy" zaxirasini TANIYDIGAN YAGONA qoida — nom
# `get_or_create_loy_stock` yasaydigan shakl (`f"Tayyor loy ({retsept})"`) bilan
# boshlanadi. Bunday pozitsiya sotib olinadigan xomashyo EMAS, balki
# buyurtmalardan ORTGAN loy; u odatda 0 / 0 turadi va bu me'yor — "kam qoldi" /
# "qolmadi" ogohlantirishlariga va Omborxona "Kam qolganlar" soniga kirmaydi.
# Ishlatiladi: `get_notifications` (qo'ng'iroqcha), `get_inventory_kpi`
# (Omborxona KPI); `crud.get_low_stock_items` (Telegram) — o'sha shakl
# (`'Tayyor loy (%'`); `inventory.html` — `startswith('Tayyor loy (')`.
# kech37 (21-band) — FOYDALANUVCHI QARORI: "Ortgan loy uchun chegara shart
# emas." Ya'ni Tayyor loy ga min > 0 qo'yilgan bo'lsa ham u HECH QAYERDA "kam"
# deb chiqmaydi: `check_low_stock` (bosh sahifa, dashboard, buyurtmalar sahifasi
# ogohlantirishi, bugungi vazifalar, grafik), `get_business_alerts` (hisobotlar),
# `main.api_full_stock_report` (Telegram "Ombor hisoboti"), `reports.html`
# `stockDot`; Omborxona qatorida chegara ustuni "—" (tahrirlash tugmasi yo'q).
# Ilgari qo'ng'iroqcha `'Tayyor loy%'` (qavssiz) ishlatardi: foydalanuvchi o'zi
# yaratgan "Tayyor loy" nomli oddiy material tugasa ham ogohlantirilmasdi,
# Telegram esa ogohlantirardi — endi ikkalasi bir xil.
TAYYOR_LOY_PREFIKS = "Tayyor loy ("


def get_notifications(db: Session, company_id: int = None) -> list:
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
    from database import tashkent_today_start_utc

    notifications = []
    now = datetime.utcnow()

    # ── 🔴 Butunlay tugagan ──────────────────────────────────
    # "Tayyor loy (...)" — bular oddiy xomashyo emas, balki ISHLAB
    # CHIQARISHDAN ORTIB QOLGAN qoldiq (keyingi buyurtmaga ishlatish
    # uchun). Ular ODATDA 0 bo'lib turadi — bu me'yor, muammo emas,
    # shuning uchun bu ogohlantirishlarga kiritilmaydi.
    # 20-band (2026-09-21): o'chirilgan (yashirilgan, `is_deleted`) materiallar
    # ogohlantirishga KIRMAYDI — ular ombor ro'yxatida (`crud.get_inventory`)
    # ko'rinmaydi, lekin ilgari bu yerda "qolmadi" deb chiqib turardi.
    empty_items = db.query(Inventory).filter(
        *( [Inventory.company_id == company_id] if company_id is not None else [] ),
        Inventory.is_deleted.isnot(True),
        Inventory.stock_quantity <= 0,
        ~Inventory.item_name.like(TAYYOR_LOY_PREFIKS + '%')
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
        *( [Inventory.company_id == company_id] if company_id is not None else [] ),
        Inventory.is_deleted.isnot(True),       # 20-band — yuqoridagi bilan bir xil
        Inventory.stock_quantity > 0,
        ~Inventory.item_name.like(TAYYOR_LOY_PREFIKS + '%')
    ).all()
    for item in items:
        total_out = db.query(func.sum(InventoryMovement.quantity)).filter(
            *( [InventoryMovement.company_id == company_id] if company_id is not None else [] ),
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
    today_start = tashkent_today_start_utc()
    today_end = today_start + timedelta(days=1)
    today_count = db.query(Order).filter(
        *( [Order.company_id == company_id] if company_id is not None else [] ),
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


def check_low_stock(db: Session, company_id: int = None) -> List[Dict]:
    """Min qoldiqdan kam bo'lgan xomashyolar ro'yxati.

    Admin dashboardida ko'rsatish uchun.
    """
    # 2026-09-21: QAT'IY korxona filtri — None bo'lsa bo'sh (ilgari
    # filtr umuman yo'q edi: B dashboardida A ning xomashyo nomlari).
    # 2026-09-22 (kech34, K34-1 — jonli O'LCHANGAN): o'chirilgan (tarixi bor,
    # shuning uchun YASHIRILGAN — `crud.delete_item` soft) material Omborxona
    # ro'yxatida yo'q, lekin bosh sahifa "Kam qolgan xomashyo", dashboard,
    # buyurtmalar sahifasi ogohlantirishi va "Bugungi vazifalar" da ko'rinishda
    # davom etardi — foydalanuvchi uni ko'ra ham, to'ldira ham olmaydi.
    # `get_business_alerts` / `get_notifications` dagidek yashirinlar chiqariladi
    # (`isnot(True)` — eski NULL qatorlar ko'rinadigan bo'lib qoladi).
    # kech37 (21-band, foydalanuvchi qarori: "Ortgan loy uchun chegara shart
    # emas"): "Tayyor loy (...)" zaxirasiga min > 0 qo'yilgan bo'lsa ham u bosh
    # sahifa "Kam qolgan xomashyo", dashboard, buyurtmalar ogohlantirishi,
    # bugungi vazifalar va grafikka TUSHMAYDI (ilgari tushardi — Omborxona KPI,
    # qo'ng'iroqcha va Telegram esa uni chiqarib tashlardi). `TAYYOR_LOY_PREFIKS`.
    low_items = db.query(Inventory).filter(
        Inventory.company_id == company_id,
        Inventory.is_deleted.isnot(True),
        Inventory.stock_quantity <= Inventory.min_stock,
        Inventory.min_stock > 0,
        ~Inventory.item_name.like(TAYYOR_LOY_PREFIKS + '%')
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


def get_today_tasks(db: Session, company_id: int = None) -> List[Dict]:
    """Dashboard 'Bugungi vazifalar' vidjeti uchun — bugun e'tibor talab
    qiladigan narsalar ro'yxati: bugun topshirilishi kerak bo'lgan
    buyurtmalar, muddati o'tgan buyurtmalar, va kam qolgan xomashyo.
    Har biri {icon, text} shaklida qaytariladi."""
    from models import Order, OrderStatus
    from datetime import datetime, timedelta
    from database import tashkent_today_start_utc

    tasks = []
    today_start = tashkent_today_start_utc()
    today_end = today_start + timedelta(days=1)

    # 1) Bugun topshirilishi kerak bo'lgan buyurtmalar
    # 2026-09-21: QAT'IY korxona filtri (ilgari yo'q edi — B "bugungi
    # vazifalar"da A ning buyurtma raqamlarini ko'rardi).
    due_today = db.query(Order).filter(
        Order.company_id == company_id,
        Order.deadline >= today_start, Order.deadline < today_end,
        Order.status.notin_([OrderStatus.DELIVERED, OrderStatus.CANCELLED]),
        Order.is_deleted.isnot(True)
    ).all()
    for o in due_today:
        tasks.append({"icon": "🚚", "text": f"{o.order_number} — bugun topshirilishi kerak"})

    # 2) Muddati o'tgan (kechikkan) buyurtmalar
    overdue = db.query(Order).filter(
        Order.company_id == company_id,
        Order.deadline < today_start,
        Order.status.notin_([OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.READY]),
        Order.is_deleted.isnot(True)
    ).count()
    if overdue > 0:
        tasks.append({"icon": "⏰", "text": f"{overdue} ta buyurtma muddati o'tgan"})

    # 3) Kam qolgan xomashyo
    low_stock = check_low_stock(db, company_id)
    for item in low_stock[:5]:
        tasks.append({"icon": "⚠️", "text": f"{item['item_name']} kam qolgan ({item['stock_quantity']:g} {item['unit']})"})

    if not tasks:
        tasks.append({"icon": "✅", "text": "Bugun uchun alohida vazifa yo'q"})

    return tasks


def get_today_stats(db: Session, company_id: int = None) -> Dict:
    """Dashboard yuqori qatori uchun 'bugungi kun' statistikasi.

    Barchasi bazadagi haqiqiy yozuvlardan hisoblanadi:
    - Bugungi tushum: bugun qabul qilingan to'lovlar summasi (Payment.paid_at)
    - Ishlab chiqarishda: status = in_progress yoki coating bo'lgan buyurtmalar
    - Bugun topshiriladi: deadline bugunga to'g'ri keladigan, hali yopilmagan buyurtmalar
    - Ishlayotgan ustalar: hozir faol buyurtmasi bor noyob ustalar soni
    - Sof foyda (bugun): bugun yakunlangan (completed_at) buyurtmalar bo'yicha calculate_order_profit yig'indisi
    """
    from models import Order, OrderStatus, Master, Payment, FinishedProductSale, FinishedProduct
    from sqlalchemy import func
    from datetime import datetime, timedelta
    from database import tashkent_today_start_utc

    today_start = tashkent_today_start_utc()
    today_end = today_start + timedelta(days=1)

    # M6 (2026-09-18) — TENANT: bugungi ko'rsatkichlar joriy korxona bo'yicha.
    from models import Order as _Ord_td
    _trq = db.query(func.sum(Payment.amount)).join(
        _Ord_td, _Ord_td.id == Payment.order_id) if company_id is not None else db.query(func.sum(Payment.amount))
    today_revenue = float(_trq.filter(
        *( [_Ord_td.company_id == company_id] if company_id is not None else [] ),
        Payment.paid_at >= today_start, Payment.paid_at < today_end
    ).scalar() or 0)

    active_orders = db.query(Order).filter(
        *( [Order.company_id == company_id] if company_id is not None else [] ),
        Order.status.notin_([OrderStatus.READY, OrderStatus.DELIVERED, OrderStatus.CANCELLED]),
        Order.is_deleted.isnot(True)
    ).count()

    in_production = db.query(Order).filter(
        *( [Order.company_id == company_id] if company_id is not None else [] ),
        Order.status.in_([OrderStatus.IN_PROGRESS, OrderStatus.COATING]),
        Order.is_deleted.isnot(True)
    ).count()

    due_today = db.query(Order).filter(
        *( [Order.company_id == company_id] if company_id is not None else [] ),
        Order.deadline >= today_start, Order.deadline < today_end,
        Order.status.notin_([OrderStatus.DELIVERED, OrderStatus.CANCELLED]),
        Order.is_deleted.isnot(True)
    ).count()

    active_masters = db.query(Order.master_id).filter(
        *( [Order.company_id == company_id] if company_id is not None else [] ),
        Order.master_id.isnot(None),
        Order.status.in_([OrderStatus.NEW, OrderStatus.IN_PROGRESS, OrderStatus.COATING]),
        Order.is_deleted.isnot(True)
    ).distinct().count()

    # MUHIM: o'chirilgan buyurtmalar ham hisobga olinadi — "bugungi foyda"
    # ko'rsatkichi ham, moliyaviy tarix sifatida, o'zgarmasligi kerak.
    completed_today = db.query(Order).filter(
        *( [Order.company_id == company_id] if company_id is not None else [] ),
        Order.completed_at >= today_start, Order.completed_at < today_end,
        Order.status == OrderStatus.READY
    ).all()
    today_profit = 0.0
    today_gips_revenue = 0.0
    today_penoplast_revenue = 0.0
    for o in completed_today:
        try:
            p = calculate_order_profit(db, o.id, company_id=company_id)
            if p.get("success"):
                today_profit += p.get("foyda", 0)
        except Exception:
            db.rollback()
        o_total = float(o.total_amount or 0)
        o_agreed = o.kelishilgan_summa
        if o_total > 0:
            for it in o.items:
                share = (float(it.total_price or 0) / o_total) * o_agreed
                if (it.category or '').lower() == 'gips':
                    today_gips_revenue += share
                else:
                    today_penoplast_revenue += share

    # ── Tayyor mahsulotlar bo'limidan to'g'ridan-to'g'ri (buyurtmasiz)
    # sotilganlar — avval bu "Bugungi" statistikada hisobga olinmasdi. ──
    fp_sales_today = db.query(FinishedProductSale).filter(
        *( [FinishedProductSale.company_id == company_id] if company_id is not None else [] )
    ).outerjoin(
        FinishedProduct, FinishedProductSale.finished_product_id == FinishedProduct.id
    ).filter(
        FinishedProductSale.sold_at >= today_start,
        FinishedProductSale.sold_at < today_end
    ).all()
    for s in fp_sales_today:
        s_total = float(s.total_amount or 0)
        s_cost = float(s.cost_amount or 0)
        today_revenue += s_total
        today_profit += (s_total - s_cost)
        cat = (s.finished_product.category if s.finished_product else '') or ''
        if cat.lower() == 'gips':
            today_gips_revenue += s_total
        else:
            today_penoplast_revenue += s_total

    return {
        "today_revenue": float(today_revenue),
        "active_orders": active_orders,
        "in_production": in_production,
        "due_today": due_today,
        "active_masters": active_masters,
        "today_profit": today_profit,
        "today_gips_revenue": round(today_gips_revenue),
        "today_penoplast_revenue": round(today_penoplast_revenue),
    }


def get_dashboard_stats(db: Session, company_id: int = None) -> Dict:
    """Admin dashboard uchun umumiy statistika.

    M5 — TENANT: ustalar sanog'i joriy korxona bo'yicha. (Qolgan
    sanoqlar M2/M3/M6 doirasida alohida ko'riladi.)"""
    from models import Project, Master

    # 2026-09-21: sanoqlar QAT'IY korxona bo'yicha (ilgari butun baza).
    total_projects = db.query(Project).filter(Project.company_id == company_id, Project.is_deleted.isnot(True)).count()
    total_orders = db.query(Order).filter(Order.company_id == company_id, Order.is_deleted.isnot(True)).count()
    active_orders = db.query(Order).filter(Order.company_id == company_id, Order.status != OrderStatus.READY, Order.is_deleted.isnot(True)).count()
    ready_orders = db.query(Order).filter(Order.company_id == company_id, Order.status == OrderStatus.READY, Order.is_deleted.isnot(True)).count()
    _tmq = db.query(Master).filter(Master.is_active == True)
    if company_id is not None:      # M5
        _tmq = _tmq.filter(Master.company_id == company_id)
    total_masters = _tmq.count()
    # kech34 (K34-1): yashirilgan (o'chirilgan) materiallar sanalmaydi.
    total_inventory_items = db.query(Inventory).filter(
        Inventory.company_id == company_id,
        Inventory.is_deleted.isnot(True)).count()
    low_stock = check_low_stock(db, company_id)

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

    # 17d (2026-09-21): haqiqiy loy miqdori HECH NARSA o'zgarishidan oldin
    # tekshiriladi. O'LCHANGAN: `inf` → buyurtma "Tayyor" bo'lib, loy
    # xomashyosi qoldig'i −∞ saqlanardi va buyurtma kartasi, "Qarzdorlar",
    # biznes-salomatlik 500; `1e20` → qoldiq −5×10¹⁹; `nan` / manfiy JIMGINA
    # "kiritilmagan" deb qabul qilinardi. Bo'sh / `None` — "kiritilmagan"
    # (reja bo'yicha), bu SAQLANADI.
    import crud as _crud_loy
    try:
        loy_kg = _crud_loy._query_loy("loy_kg", loy_kg, bosh_mumkin=True)
    except ValueError as e:
        return {"success": False, "message": str(e)}

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    # kech41 (5-bo'lim 14-band, K41-1) — QULF (101, buyurtma), yetkazish /
    # to'lov / detal tahriri bilan BIR fazo; qulf ostida bazadan QAYTA
    # o'qiladi. HAQIQIY PostgreSQL da O'LCHANGAN (asl kod, `work/probe41.py`,
    # 3 / 3): "Tayyor" bosilayotganda boshqa xodim 5 / 10 topshirsa, buyurtma
    # READY bo'lib qolardi — qolgan 5 topshirilmagan, summa yakunlanmagan
    # ("hech narsa topshirilmagan" deb eskirgan holatdan qaror qilinardi,
    # avtomatik yuk esa qulf ostida "Qoldiqdan ko'p" bilan jim rad etilardi).
    import crud as _crud_qulf
    _cid_q = order.company_id
    db.flush()
    _crud_qulf._pul_qulfi(db, 101, order.id)
    db.expire_all()
    order = db.query(Order).filter(Order.id == order_id, Order.company_id == _cid_q).first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    if order.status == OrderStatus.READY:
        return {"success": False, "message": "Bu buyurtma allaqachon tayyor"}

    # 17d (2026-09-21): QORALAMA buyurtma "Tayyor" qilinmaydi. Qoralamada
    # ombordan HECH NARSA yechilmagan (`deduct_inventory_for_order` faqat
    # "Jarayonga olish" da ishlaydi) — uni "Tayyor" qilish xomashyosiz
    # tayyor buyurtma, usta KPI va avtomatik yuk xati yaratardi (O'LCHANGAN:
    # `POST /ready` qoralamaga 200 "yakunlandi"). UI qoralamaga "Tayyor"
    # tugmasini ko'rsatmaydi (`orders.html`: `btn-ready` yashirin).
    if order.status == OrderStatus.DRAFT:
        return {"success": False,
                "message": "Qoralama buyurtmani avval jarayonga oling — keyin \"Tayyor\" qilish mumkin"}

    # === HAMMA NARSA TAYYOR — BAJARAMIZ ===
    # kech41 (14-band): holat DARHOL READY — quyidagi oraliq `commit` lar
    # qulfni bo'shatadi; parallel ikkinchi "Tayyor" qulfdan keyin READY ni
    # ko'rib rad etiladi (O'LCHANGAN: asl kodda ikkalasi ham "yakunlandi" —
    # loy / qaytishlar ikki marta ishlanardi). Oxiridagi `order.status =
    # READY` o'z joyida qoladi (avtomatik yuk DELIVERED qo'yishi mumkin).
    order.status = OrderStatus.READY
    result = {
        "success": True,
        "message": "✓ Buyurtma yakunlandi!",
        "inventory_changes": [],
        "master_kpi": None
    }

    # === LOY HISOB-KITOBI ===
    # Buyurtma yaratilganda rejalashtirilgan loy allaqachon ayirilgan.
    # Endi haqiqiy miqdor bilan solishtiramiz.
    import crud as _crud
    order_planned = _get_planned_loy(order)
    planned_loy = order_planned
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

        # MUHIM: haqiqiy kiritilgan umumiy loy miqdorini (Termopanel VA
        # oddiy qismni QO'SHIB, ULUSHGA BO'LMASDAN) order.notes'ga yozamiz —
        # foyda hisoblashda BITTA umumiy "Qoplama" xarajati sifatida
        # ko'rsatiladi. Formula/taxmin EMAS — aynan hodim "Tayyor"
        # bosganda kiritgan haqiqiy son.
        if actual_loy > 0:
            import re as _re_loy
            base_notes = _re_loy.sub(r',?\s*loy_kg=[\d.]+', '', order.notes or '').strip().strip(',').strip()
            order.notes = (base_notes + f", loy_kg={actual_loy:.4f}").strip(', ')
            order.actual_loy_kg = actual_loy
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

    db.commit()

    # kech41 (14-band): `commit` qulfni bo'shatdi — qisman / to'liq qarori
    # oldidan qulf QAYTA olinadi va holat bazadan qayta o'qiladi (oraliqda
    # yozilgan yuk xati hisobga olinsin).
    _crud_qulf._pul_qulfi(db, 101, order.id)
    db.expire_all()
    order = db.query(Order).filter(Order.id == order_id, Order.company_id == _cid_q).first()
    is_partial_completion = bool(order.deliveries) and not order.is_fully_delivered

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
            # MUHIM: kelishilgan summa (agreed_amount) bo'lsa — shundan 3%
            # olinadi, aks holda umumiy summadan. Bu — daromad/foyda hisobi
            # bilan (masalan yuqoridagi "daromad" yig'indisida) BIR XIL
            # qoidaga mos: chegirma qilingan buyurtmada usta cashbacki ham
            # chegirmadan OLDINGI (shishirilgan) summadan emas, HAQIQIY
            # kelishilgan summadan hisoblanishi kerak.
            cashback = order.kelishilgan_summa * 0.03
            total_meters = sum(
                (item.length or 0) * item.quantity for item in order.items if item.is_coated
            )
            # MUHIM: Ichki qo'shimcha detallar (sub_details) — bularning
            # qoplama holati ASOSIY detalning is_coated'idan MUSTAQIL,
            # xuddi qoplamachi bonusi hisoblanadigan get_monthly_report()
            # dagi kabi (o'sha yerda ham xuddi shu sabab bilan alohida
            # tekshiriladi). Bu yerda ham xuddi shunday — asosiy qoplamasiz
            # bo'lsa ham ichki qoplamali bo'lishi, yoki aksincha, mumkin.
            for item in order.items:
                for sub in (item.sub_details or []):
                    if not getattr(sub, 'is_coated', False):
                        continue
                    sub_cat = (getattr(sub, 'category', None) or '').lower()
                    if sub_cat == 'panel':
                        total_meters += float(getattr(sub, 'quantity', 0) or 0)
                    else:  # 'profil' (standart)
                        total_meters += float(getattr(sub, 'length', 0) or 0) * float(getattr(sub, 'quantity', 1) or 1)
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
        import re as _re_loykg_w
        existing_notes = order.notes or ''
        base_notes = _re_loykg_w.sub(r',?\s*loy_kg=[\d.]+', '', existing_notes).strip().strip(',').strip()
        order.notes = (base_notes + f", loy_kg={loy_kg}").strip(', ')
        order.actual_loy_kg = float(loy_kg)
    db.commit()
    db.refresh(order)

    return result


def get_inventory_kpi(db: Session, company_id: int = None) -> Dict:
    """Omborxona sahifasi uchun KPI ko'rsatkichlari — faqat o'qish, hech narsani o'zgartirmaydi."""
    from models import Inventory, InventoryMovement
    from sqlalchemy import func
    from datetime import datetime, timedelta
    from database import tashkent_today_start_utc

    _iq = db.query(Inventory).filter(Inventory.is_deleted.isnot(True))
    if company_id is not None:
        _iq = _iq.filter(Inventory.company_id == company_id)
    items = _iq.all()
    total_items = len(items)
    # kech36 (K35-1, jonli O'LCHANGAN kech35): "Tayyor loy (...)" zaxirasi
    # (`TAYYOR_LOY_PREFIKS` izohi) "Kam qolganlar" ga SANALMAYDI. Ilgari
    # Omborxona "Kam qolganlar 1 ta" deb `Tayyor loy (Oq marmar)` 0 / 0 ni
    # sanardi, holbuki qo'ng'iroqcha, bosh sahifa va Telegram uni ko'rsatmasdi.
    # Endi `low_count` == `len(crud.get_low_stock_items(...))` (Telegram
    # "kam qoldi" ro'yxati) — oddiy material 0 / 0 esa avvalgidek sanaladi.
    low_count = sum(1 for i in items
                    if not str(i.item_name or "").startswith(TAYYOR_LOY_PREFIKS)
                    and float(i.stock_quantity or 0) <= float(i.min_stock or 0))
    total_value = sum(float(i.stock_quantity or 0) * float(i.price_per_unit or 0) for i in items)

    today_start = tashkent_today_start_utc()
    today_end = today_start + timedelta(days=1)

    _mv_cid = ([InventoryMovement.company_id == company_id]
               if company_id is not None else [])
    today_in = db.query(func.count(InventoryMovement.id)).filter(
        *_mv_cid,
        InventoryMovement.movement_type == "in",
        InventoryMovement.created_at >= today_start, InventoryMovement.created_at < today_end
    ).scalar() or 0
    today_out = db.query(func.count(InventoryMovement.id)).filter(
        *_mv_cid,
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


def get_low_stock_warnings(db: Session, company_id: int = None) -> List[Dict]:
    """check_low_stock ning alias — eski kodlarga moslik uchun."""
    return check_low_stock(db, company_id)


# ============================================================
# DASHBOARD UCHUN KENGAYTIRILGAN STATISTIKA
# ============================================================

def get_chart_data(db: Session, company_id: int = None) -> Dict:
    """Dashboard grafiklari uchun ma'lumotlar.

    2026-09-18 — TENANT (M7 validatsiyasida B sessiyasidan topilgan
    UCHINCHI haqiqiy sizish): bu funksiyadagi 9 ta so'rov korxona
    filtrisiz edi. Natijada B korxonaning boshqaruv panelida A ning
    moliyaviy ko'rsatkichlari ko'rinardi — `total_revenue 53 757 000`,
    `total_budget`/`total_debt 120 417 000`, oylik daromad 54 569 000 —
    holbuki B da buyurtma summasi ham, sotuv ham 0 edi.

    `company_id` FAQAT autentifikatsiya kontekstidan keladi
    (`main.py` → `auth.company_id_of(current_user)`); mijoz so'rovidan
    olinmaydi va hech qanday standart 1-korxonaga tushmaydi."""
    from models import Project, Master, Order, OrderItem, OrderStatus, FinishedProductSale, FinishedProduct
    from sqlalchemy import func
    from datetime import datetime, timedelta

    def _oc(q):
        """Order bo'yicha so'rovni joriy korxona bilan cheklaydi."""
        return q.filter(Order.company_id == company_id) if company_id is not None else q

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

        count = _oc(db.query(Order).filter(
            Order.created_at >= month_start,
            Order.created_at < month_end,
            Order.is_deleted.isnot(True)
        )).count()

        # MUHIM: daromad (revenue) — moliyaviy tarix, o'chirilgan
        # buyurtmalar ham hisobga olinishi kerak (faqat "count" — necha ta
        # buyurtma yaratilgani — o'zgarishsiz qoladi, chunki bu shunchaki son).
        revenue = float(_oc(db.query(func.sum(func.coalesce(Order.agreed_amount, Order.total_amount, 0))).filter(
            Order.created_at >= month_start,
            Order.created_at < month_end,
            Order.status == OrderStatus.READY
        )).scalar() or 0)

        # Gips va Penoplast (va boshqa) — detal darajasida, ulush bo'yicha
        # ajratilgan holda (har bir detalning umumiy summadagi ulushi ×
        # kelishilgan summa — chegirma/qo'shimchani ham to'g'ri hisobga oladi)
        month_orders = _oc(db.query(Order).filter(
            Order.created_at >= month_start,
            Order.created_at < month_end,
            Order.status == OrderStatus.READY
        )).all()
        gips_rev = 0.0
        peno_rev = 0.0
        for o in month_orders:
            o_total = float(o.total_amount or 0)
            o_agreed = o.kelishilgan_summa
            if o_total <= 0:
                continue
            for it in o.items:
                share = (float(it.total_price or 0) / o_total) * o_agreed
                if (it.category or '').lower() == 'gips':
                    gips_rev += share
                else:
                    peno_rev += share

        # Tayyor mahsulotlar bo'limidan to'g'ridan-to'g'ri (buyurtmasiz)
        # sotilganlar — avval bu grafikda hisobga olinmasdi.
        _mfsq = db.query(FinishedProductSale).outerjoin(
            FinishedProduct, FinishedProductSale.finished_product_id == FinishedProduct.id
        ).filter(
            FinishedProductSale.sold_at >= month_start,
            FinishedProductSale.sold_at < month_end
        )
        if company_id is not None:
            # OUTER JOIN bo'lgani uchun cheklash SOTUVNING O'ZIDAGI
            # company_id ustuni bo'yicha qo'yiladi — mahsuloti o'chirilgan
            # (finished_product_id = NULL) sotuvlar ham to'g'ri qoladi.
            _mfsq = _mfsq.filter(FinishedProductSale.company_id == company_id)
        month_fp_sales = _mfsq.all()
        for s in month_fp_sales:
            s_total = float(s.total_amount or 0)
            revenue += s_total
            cat = (s.finished_product.category if s.finished_product else '') or ''
            if cat.lower() == 'gips':
                gips_rev += s_total
            else:
                peno_rev += s_total

        months_data.append({
            "label": month_start.strftime("%b %Y"),
            "gips_revenue": round(gips_rev),
            "penoplast_revenue": round(peno_rev),
            "orders": count,
            "revenue": float(revenue)
        })

    # --- 2. Buyurtma holatlari (donut chart) ---
    statuses = {}
    for status in OrderStatus:
        try:
            cnt = _oc(db.query(Order).filter(Order.status == status, Order.is_deleted.isnot(True))).count()
            statuses[status.value] = cnt
        except Exception:
            # Enum bazada hali yo'q bo'lsa
            db.rollback()
            statuses[status.value] = 0

    # --- 3. Ustalar KPI (top 5) ---
    _cmq = db.query(Master).filter(Master.is_active == True)
    if company_id is not None:      # M5
        _cmq = _cmq.filter(Master.company_id == company_id)
    masters = _cmq.all()
    master_kpi = []
    for m in masters:
        # MUHIM: bu ham daromad (moliyaviy) hisob-kitobi — o'chirilgan
        # buyurtmalar ham hisobga olinadi.
        total = _oc(db.query(func.sum(func.coalesce(Order.agreed_amount, Order.total_amount, 0))).filter(
            Order.master_id == m.id,
            Order.status == OrderStatus.READY
        )).scalar() or 0
        order_count = _oc(db.query(Order).filter(
            Order.master_id == m.id,
            Order.is_deleted.isnot(True)
        )).count()
        master_kpi.append({
            "name": m.name,
            "total": float(total),
            "orders": order_count
        })
    # Eng ko'p ishlagani birinchi
    master_kpi.sort(key=lambda x: x["total"], reverse=True)
    master_kpi = master_kpi[:5]

    # --- 4. Umumiy moliyaviy ko'rsatkichlar ────────────────
    # MUHIM: barchasi BITTA manbadan — Order/Payment jadvallaridan —
    # hisoblanadi, xuddi Moliya va Hisobotlar sahifalari kabi. Avval
    # "To'langan"/"Jami byudjet" Project.total_paid/total_budget kabi
    # alohida (keshlangan) maydonlardan olinar edi — bu ular haqiqiy
    # to'lovlardan (Payment) sekin-asta uzoqlashib ketishiga sabab
    # bo'lishi mumkin edi. Endi hammasi bir xil, izchil manbadan.
    from models import Payment

    total_revenue = _oc(db.query(func.sum(func.coalesce(Order.agreed_amount, Order.total_amount, 0))).filter(
        Order.status == OrderStatus.READY
    )).scalar() or 0

    from sqlalchemy import or_
    total_budget = _oc(db.query(func.sum(func.coalesce(Order.agreed_amount, Order.total_amount, 0))).filter(
        Order.status != OrderStatus.DRAFT,
        or_(
            Order.is_deleted.isnot(True),  # faol buyurtmalar — doim hisoblanadi
            Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED])  # o'chirilgan, lekin YAKUNLANGAN edi — moliyaviy tarix sifatida saqlanadi
        )
    )).scalar() or 0

    # M6 — TENANT: to'lovlar ota (buyurtma) orqali cheklanadi.
    _tpq = db.query(func.sum(Payment.amount))
    if company_id is not None:
        from models import Order as _Ord_ch
        _tpq = _tpq.join(_Ord_ch, _Ord_ch.id == Payment.order_id).filter(
            _Ord_ch.company_id == company_id)
    total_paid = _tpq.scalar() or 0
    total_debt = float(total_budget) - float(total_paid)

    # --- 5. Omborxona holati (top yetishmayotganlar) ---
    low_stock = check_low_stock(db, company_id)

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

def _buyurtma_sarf_narxlari(db: Session, order) -> Dict:
    """kech48 (K47-1, 5-bo'lim 32-band) — FOYDALANUVCHI QARORI (kech47, tugma):
    "Ishlatilgan paytdagi narxda muzlatilsin".

    Buyurtma tan narxi (`calculate_order_profit`) xomashyoni JORIY narx bilan
    baholardi: penoplast yoki kley narxi o'zgarsa, O'TGAN buyurtmalar foydasi
    va o'tgan oylarning sof foydasi orqaga qarab o'zgarardi (JONLI O'LCHANGAN,
    kech47: penoplast 276 narxi x2 bo'lganda 2026-09 sof foydasi −11.38 mln
    so'mga siljidi; lokal `work/probe47.py`: narxlar x3 → tan narx x3).

    Qaytaradi: {inventory_id: shu buyurtmada 1 birlik narxi} — faqat shu
    buyurtmaning ombor harakatlarida uchragan materiallar uchun.

    Manba — shu buyurtmaning (`order_id`, korxona) harakatlari, `id` (vaqt)
    tartibida, O'RTACHA TANNARX usulida:
      * chiqim ("out") — miqdor × `unit_cost` (chiqim paytidagi narx, zip 47
        dan beri `crud.log_movement` yozadi); `unit_cost` i yo'q ESKI harakat —
        joriy narx (brak hisobotidagi `_harakat_narxi` qoidasi bilan bir xil);
      * kirim ("in" — tahrirda kamaytirish, loy xomashyosining qaytishi) —
        o'sha paytdagi o'rtacha narxda ayiriladi (qolgan qism narxi o'zgarmaydi);
        chiqimdan oldingi kirim (jurnal yozilmagan eski chiqim) — e'tiborsiz.
    BRAK harakatlari (kech52: `crud.brak_harakati_sharti` — `is_brak` belgisi,
    belgisiz eski harakat — `return_item_id` bor YOKI sabab "Brak%"; brak
    xarajati `crud.get_brak_material_summary` da AYNAN shu shart bilan alohida
    hisoblanadi) kirmaydi — aks holda brak narxi buyurtma narxiga aralashardi.
    Harakati yo'q material (jurnal yozilmagan eski buyurtma, to'liq tayyor loy
    zaxirasidan olingan qoplama) lug'atda YO'Q — chaqiruvchi JORIY narxni
    oladi (avvalgi xulq, eski narx noma'lum — taxmin qilinmaydi).
    """
    from models import InventoryMovement as _IMv
    from sqlalchemy import not_ as _not_sn
    import crud as _crud_sn
    _oid_sn = getattr(order, "id", None)
    if _oid_sn is None:
        return {}
    _hq = db.query(_IMv).filter(
        _IMv.order_id == _oid_sn,
        _not_sn(_crud_sn.brak_harakati_sharti(_IMv)),
    )
    _cid_sn = getattr(order, "company_id", None)
    if _cid_sn is not None:
        _hq = _hq.filter(_IMv.company_id == _cid_sn)
    harakatlar = _hq.order_by(_IMv.id).all()
    if not harakatlar:
        return {}
    _inv_ids = {h.inventory_id for h in harakatlar if h.inventory_id}
    joriy = {}
    if _inv_ids:
        _jq = db.query(Inventory).filter(Inventory.id.in_(_inv_ids))
        if _cid_sn is not None:
            _jq = _jq.filter(Inventory.company_id == _cid_sn)
        for _inv_sn in _jq.all():
            joriy[_inv_sn.id] = float(_inv_sn.price_per_unit or 0)
    hisob = {}   # inventory_id -> [miqdor, qiymat, oxirgi o'rtacha narx]
    for h in harakatlar:
        if not h.inventory_id:
            continue
        miqdor = float(h.quantity or 0)
        if miqdor <= 0:
            continue
        x = hisob.setdefault(h.inventory_id, [0.0, 0.0, None])
        if h.movement_type == "out":
            narx = float(h.unit_cost) if h.unit_cost is not None else joriy.get(h.inventory_id, 0.0)
            x[0] += miqdor
            x[1] += miqdor * narx
            x[2] = x[1] / x[0]
        elif h.movement_type == "in":
            if x[0] <= 1e-12:
                continue
            ortacha = x[1] / x[0]
            olindi = min(miqdor, x[0])
            x[0] -= olindi
            x[1] -= olindi * ortacha
            if x[0] <= 1e-12:
                x[0], x[1] = 0.0, 0.0
    natija = {}
    for _iid_sn, (m, v, oxirgi) in hisob.items():
        if m > 1e-12:
            natija[_iid_sn] = v / m
        elif oxirgi is not None:
            # Hammasi qaytgan (jurnal bo'yicha) — oxirgi ma'lum narx.
            natija[_iid_sn] = oxirgi
    return natija


def calculate_order_profit(db: Session, order_id: int, company_id: int = None) -> Dict:
    """
    Buyurtma uchun tan narxi va foyda hisoblaydi.

    Tan narxi = Penoplast xarajati + Qoplama xomashyosi xarajati
    Foyda = Sotuv narxi - Tan narxi

    M6 — TENANT: company_id berilsa, buyurtma FAQAT shu korxonadan olinadi.

    kech48 (K47-1, 5-bo'lim 32-band): xomashyo (penoplast, qoplama va loy
    sotish ingredientlari) shu buyurtmada ISHLATILGAN paytdagi narxda
    baholanadi (`_buyurtma_sarf_narxlari`) — keyingi narx o'zgarishi o'tgan
    buyurtma foydasini o'zgartirmaydi. Hajm / miqdor mantig'i O'ZGARMAGAN.
    """
    _oq = db.query(Order).filter(Order.id == order_id)
    if company_id is not None:
        _oq = _oq.filter(Order.company_id == company_id)
    order = _oq.first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    # Kelishilgan (chegirmadan keyingi, haqiqatan mijoz to'laydigan) summadan
    # hisoblanadi — shunda har qanday chegirma (boshidagi ham, keyin
    # "kechirilgan" ham) foyda hisobotida to'g'ri, avtomatik hisobga olinadi.
    sotuv_narxi = order.kelishilgan_summa
    breakdown = []
    tan_narxi_jami = 0.0

    # ── 1. PENOPLAST XARAJATI ────────────────────────────────
    # MUHIM: har bir detal O'ZINING penoplast_id'siga (ya'ni aynan tanlangan
    # plotnost/narxga) qarab hisoblanadi — "birinchi topilgan Penoplast"
    # emas, chunki turli detallar turli plotnostdan bo'lishi mumkin
    # (buni biz alohida "1 m³ narxi" maydoni orqali qo'llab-quvvatlaymiz).
    default_penoplast = get_default_penoplast(db, company_id=getattr(order, "company_id", None))

    # kech48 (K47-1): shu buyurtmada ishlatilgan paytdagi narxlar.
    _sarf_narx = _buyurtma_sarf_narxlari(db, order)

    def _narx(inv):
        """1 birlik narxi: shu buyurtmada muzlatilgan, bo'lmasa — joriy."""
        if inv is None:
            return 0.0
        if inv.id in _sarf_narx:
            return float(_sarf_narx[inv.id])
        return float(inv.price_per_unit or 0)

    penoplast_xarajat = 0.0
    penoplast_breakdown_by_item = {}  # penoplast_id -> {"vol": ..., "narx_per_m3": ...}
    for item in order.items:
        # MUHIM: "Tayyor mahsulotdan" tanlangan detallar — xomashyosi
        # ALLAQACHON, mahsulot birinchi marta ishlab chiqarilganda
        # ayirilgan. Bu hisobotda ularni QAYTA qo'shib hisoblasak — real
        # ombordan ayirilgandan KO'PROQ ko'rsatib yuboramiz.
        if getattr(item, 'finished_product_id', None):
            continue
        cat = (item.category or '').lower()
        qty = float(item.quantity or 1)
        vol = 0.0

        if cat == 'profil':
            if item.width and item.thickness and item.length:
                vol = (item.width/100) * (item.thickness/100) / 2 * float(item.length)
            # MUHIM (2026-09 audit): ichki qo'shimcha detallar (sub_details)
            # — asosiy detal bilan BIR XIL xomashyodan hisoblanadi, shuning
            # uchun ombordan chiqim/hajm hisobida (_item_volume_m3) ham
            # qo'shiladi. Bu yerda (foyda/tan narxi hisobi) shu vaqtgacha
            # QO'SHILMAGAN edi — natijada ichki detalli buyurtmalarning
            # tan narxi kamroq, foydasi esa haqiqatdan ko'proq ko'rsatilib
            # kelingan. Endi xuddi shu formula bilan qo'shiladi.
            vol += _sub_details_volume_m3(item)
        elif cat == 'panel':
            if item.width and item.thickness:
                vol = (item.width/100) * (item.thickness/100) * qty
        elif cat == 'dona':
            # TUZATILDI 2026-09-20. Bu yerda avval ALOHIDA, qo'lda yozilgan
            # nusxa turardi va u ombordan HAQIQATDA yechiladigan hajmdan
            # ikki jihatdan farq qilardi:
            #   1) 1 m³ ning TAN narxiga bo'lardi, detalning O'Z 1 m³ SOTUV
            #      narxiga (price_per_m3) emas — natijada hajm sotuv/tan
            #      nisbatiga (odatda ~1.9 barobar) shishib ketardi va
            #      tan narx = sotuv narx bo'lib, foyda har doim AYNAN 0
            #      chiqardi (matematik jihatdan boshqacha bo'lishi mumkin
            #      emas edi);
            #   2) 2026-08-16 da qo'shilgan o'lchamli ("1 metrdan necha
            #      dona") usulni umuman bilmasdi.
            # Endi hajm manbasi BITTA: _item_volume_m3 — ya'ni ombordan
            # qancha yechilsa, foyda hisobida ham aynan shuncha.
            _pid_dona = item.penoplast_id or (default_penoplast.id if default_penoplast else None)
            vol = _item_volume_m3(db, item, default_penoplast,
                                  penoplast_narxi=_sarf_narx.get(_pid_dona))

        elif cat == 'blok':
            # Blokdan chiqadigan mahsulot uchun — "length" maydonida
            # ISHLATILGAN BLOK SONI saqlanadi (metr emas). Hajm = blok soni
            # × 1 blokning hajmi (m³) — xuddi ombordan yechishda ishlatilgan
            # xuddi shu mantiq (deduct_inventory_for_order bilan bir xil).
            blok_soni = float(item.length or 0)
            pid_for_blok = item.penoplast_id or (default_penoplast.id if default_penoplast else None)
            p_blok = db.query(Inventory).filter(Inventory.id == pid_for_blok).first() if pid_for_blok else None
            if p_blok and p_blok.volume_per_unit and blok_soni > 0:
                vol = blok_soni * float(p_blok.volume_per_unit)

        if vol <= 0:
            continue

        # Shu detal o'zining penoplast_id'si (yoki standart) bo'yicha narxlanadi
        pid = item.penoplast_id or (default_penoplast.id if default_penoplast else None)
        if not pid:
            continue
        key = pid
        if key not in penoplast_breakdown_by_item:
            inv_item = db.query(Inventory).filter(Inventory.id == pid).first()
            # kech48 (K47-1): blok narxi — shu buyurtmada ishlatilgan paytdagi.
            # Narx 0 / yo'q bo'lsa — avvalgidek o'tkaziladi.
            _blok_narxi = _narx(inv_item)
            if not inv_item or not _blok_narxi or not inv_item.volume_per_unit:
                continue
            narx_per_m3 = _blok_narxi / float(inv_item.volume_per_unit)
            penoplast_breakdown_by_item[key] = {"vol": 0.0, "narx_per_m3": narx_per_m3, "nomi": inv_item.item_name}
        penoplast_breakdown_by_item[key]["vol"] += vol

    for pid, data in penoplast_breakdown_by_item.items():
        summa = data["vol"] * data["narx_per_m3"]
        if summa <= 0:
            continue
        breakdown.append({
            "nomi": f"{data['nomi']} ({data['vol']:.2f} m³ × {data['narx_per_m3']:,.0f} so'm/m³)",
            "summa": summa
        })
        penoplast_xarajat += summa
    tan_narxi_jami += penoplast_xarajat

    # ── 1A. TAYYOR MAHSULOTDAN OLINGAN DETALLAR TAN NARXI ────
    # MUHIM: bu detallar uchun XOMASHYO (yuqoridagi Penoplast/Loy) ALOHIDA
    # HISOBLANMAYDI (chunki u — mahsulot birinchi marta ishlab
    # chiqarilganda, allaqachon ayirilgan). Lekin bu mahsulotning O'ZI —
    # BEPUL emas, uni ishlab chiqarish uchun xarajat ketgan. Shu xarajatni
    # shu yerda, alohida qatorda hisobga olamiz — aks holda "Sof foyda"
    # sun'iy oshirib ko'rsatilgan bo'lardi.
    from models import FinishedProduct as _FP_cost
    tayyor_mahsulot_xarajat = 0.0
    for item in order.items:
        fpid = getattr(item, 'finished_product_id', None)
        if not fpid:
            # QO'SHILDI 2026-09-20 — MRP ORQALI ishlab chiqarilgan mahsulot.
            #
            # Muammo: MRP tayyor mahsulotni buyurtma detaliga
            # `order_item.finished_product_id` orqali BOG'LAMAYDI (mahsulot
            # buyurtmadan keyin ishlab chiqariladi), shuning uchun quyidagi
            # tsikl uni ko'rmasdi va butun ishlab chiqarish xarajati
            # buyurtma foydasidan tushib qolardi — jonli sinovda 100 m²
            # travertin 8 144 736.86 so'm xarajat bilan 0 tan narx va
            # 100% marja ko'rsatdi.
            #
            # Manba sifatida ISHLAB CHIQARISH BUYURTMASI olinadi
            # (`production_orders.total_cost`), tayyor mahsulot emas.
            # Sabab: tayyor mahsulotning `cost_price` va `reserved_quantity`
            # qiymatlari mijozga topshirilgan sari KAMAYADI, ishlab
            # chiqarishga ketgan xarajat esa O'ZGARMAYDI. Buyurtmaning tan
            # narxi ham o'zgarmasligi kerak.
            #
            # Faqat YAKUNLANGAN ishlab chiqarish olinadi — bekor qilingani
            # yoki hali tugallanmagani xarajat hisoblanmaydi.
            try:
                from production_models import ProductionOrder as _PO_cost
                _pq = db.query(_PO_cost).filter(
                    _PO_cost.source_order_item_id == item.id,
                    _PO_cost.status == "completed",
                )
                _ord_cid0 = getattr(order, 'company_id', None)
                if _ord_cid0 is not None:
                    _pq = _pq.filter(_PO_cost.company_id == _ord_cid0)
                for _po_c in _pq.all():
                    tayyor_mahsulot_xarajat += float(_po_c.total_cost or 0)
            except Exception:
                pass
            continue
        # M4 (2026-09-18) — TENANT: mahsulot buyurtmaning O'Z korxonasidan
        # bo'lishi shart. Chaqiruvchi allaqachon tenant-safe bo'lsa ham,
        # funksiyaning o'zi endi mustaqil himoyalangan.
        _fpq = db.query(_FP_cost).filter(_FP_cost.id == fpid)
        _ord_cid = getattr(order, 'company_id', None)
        if _ord_cid is not None:
            _fpq = _fpq.filter(_FP_cost.company_id == _ord_cid)
        fp_c = _fpq.first()
        if not fp_c:
            continue
        base_qty = float(fp_c.produced_quantity if fp_c.produced_quantity is not None else (fp_c.quantity or 0))
        # kech59 (47-band, K59-1): `cost_price` buyurtmaga olingan / sotilgan sari KAMAYADI,
        # `produced_quantity` esa o'zgarmaydi — nisbat siljirdi (O'LCHANGAN: 10 m x 7 600 = 76 000
        # o'rniga 68 400, boshqa buyurtma olgach 53 200; TM butunlay olinsa — 0). Muzlagan birlik
        # tannarx — olish / qaytarish / sotuv bilan BITTA manba (`crud._fp_stable_unit_cost`);
        # bo'lmasa — eski formula.
        import crud as _crud_fp59
        _muz59 = _crud_fp59._fp_stable_unit_cost(db, fp_c)
        if _muz59 > 0:
            unit_cost = _muz59
        else:
            if base_qty <= 0 or not fp_c.cost_price:
                continue
            unit_cost = float(fp_c.cost_price) / base_qty
        used_qty = float(item.length if (item.category or '').lower() == 'profil' else item.quantity or 0)
        tayyor_mahsulot_xarajat += unit_cost * used_qty
    if tayyor_mahsulot_xarajat > 0:
        breakdown.append({
            "nomi": f"Tayyor mahsulotdan olingan detallar (tan narxi)",
            "summa": tayyor_mahsulot_xarajat
        })
        tan_narxi_jami += tayyor_mahsulot_xarajat


    # ── 1C. LOY SOTISH XARAJATI ──────────────────────────────
    # Har bir "Loy sotish" detali uchun — o'sha detalning O'ZIGA tegishli
    # retsept bo'yicha, sotilgan necha kg uchun tan narx hisoblanadi.
    for item in order.items:
        if (item.category or '').lower() != 'loy_sotish' or not item.recipe_id:
            continue
        qty_kg = float(item.quantity or 0)
        if qty_kg <= 0:
            continue
        recipe = db.query(Recipe).filter(Recipe.id == item.recipe_id).first()
        if not recipe:
            continue
        batch = float(recipe.batch_size_kg or 100)
        narx_per_kg = 0.0
        for ing in recipe.ingredients:
            mat_kg = float(ing.quantity_kg or 0)
            _ing_narx = _narx(ing.inventory)   # kech48 (K47-1)
            if mat_kg <= 0 or not ing.inventory or not _ing_narx:
                continue
            narx_per_kg += (mat_kg / batch) * _ing_narx
        loy_sotish_xarajat = qty_kg * narx_per_kg
        if loy_sotish_xarajat > 0:
            breakdown.append({
                "nomi": f"{item.name} — Loy sotish ({qty_kg:.1f} kg × {narx_per_kg:,.0f} so'm/kg)",
                "summa": loy_sotish_xarajat
            })
            tan_narxi_jami += loy_sotish_xarajat

    # ── 2. QOPLAMA XOMASHYOSI XARAJATI ──────────────────────
    # MUHIM: loy_kg — hech qanday formula/taxmin bilan hisoblanmaydi,
    # faqat buyurtma "Tayyor" qilinganda hodim kiritgan HAQIQIY miqdor
    # ishlatiladi (order.notes'dagi loy_kg= belgisi, complete_order
    # tomonidan yoziladi). Agar buyurtma hali yakunlanmagan bo'lsa —
    # bu xarajat hali "0" ko'rinadi, bu — to'g'ri (hali ishlatilmagan).
    # MUHIM: loy_kg — endi ALOHIDA, ISHONCHLI ustundan (order.actual_loy_kg)
    # o'qiladi — matn ichidan qidirish (notes) endi FAQAT eski, shu tuzatishdan
    # OLDIN yakunlangan buyurtmalar uchun zaxira (fallback) sifatida qoladi.
    loy_kg = float(order.actual_loy_kg) if order.actual_loy_kg is not None else 0.0
    if loy_kg <= 0 and order.notes:
        try:
            import re as _re_loykg
            m = _re_loykg.search(r'loy_kg=([\d.]+)', order.notes)
            if m:
                loy_kg = float(m.group(1))
        except Exception as e:
            try:
                import crud as _crud_log
                _crud_log.log_error(db, str(e), endpoint="calculate_order_profit:loy_kg_parse")
            except Exception:
                pass

    if loy_kg > 0:

        # Retsept bo'yicha 1 kg loy narxi
        # kech58 (K58-1 / K58-2): YAGONA manba. Yangi buyurtma — `qoplama_retsept_id` (retsept
        # tanlanmagan bo'lsa ham — loy yechilgan retsept); eski (NULL) — avvalgi qoida AYNAN
        # (birinchi `recipe_id` li detal, zaxirasiz) — foydalanuvchi qarori "faqat yangi".
        recipe = None
        _qcid = company_id if company_id is not None else getattr(order, 'company_id', None)
        for _qrid in buyurtma_qoplama_retsept_nomzodlari(order):
            _rq = db.query(Recipe).filter(Recipe.id == _qrid)
            if _qcid is not None:
                _rq = _rq.filter(Recipe.company_id == _qcid)
            recipe = _rq.first()
            break

        if recipe and loy_kg > 0:
            batch = float(recipe.batch_size_kg or 100)
            narx_per_kg = 0.0
            for ing in recipe.ingredients:
                mat_kg = float(ing.quantity_kg or 0)
                _ing_narx = _narx(ing.inventory)   # kech48 (K47-1)
                if mat_kg <= 0 or not ing.inventory or not _ing_narx:
                    continue
                narx_per_kg += (mat_kg / batch) * _ing_narx

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
        "volume_m3": round(sum(d["vol"] for d in penoplast_breakdown_by_item.values()), 3),
    }


# ============================================================
# OYLIK HISOBOT
# ============================================================

def get_daily_finance_summary(db: Session, target_date, company_id: int = None) -> Dict:
    """Bitta kun uchun to'liq moliyaviy ko'rinish:
    - Savdo (shu kun 'Tayyor' bo'lgan buyurtmalar): sotuv, tan narx, foyda
    - Xarajat: xomashyo xaridi (nimaga qancha) + boshqa xarajatlar (nimaga qancha)
    """
    from models import InventoryPurchase, ExpenseTransaction, FinishedProductSale
    from datetime import datetime as dt, timedelta

    start = dt.combine(target_date, dt.min.time())
    end = start + timedelta(days=1)

    # ── 1) SAVDO — shu kun yakunlangan buyurtmalar ──
    # MUHIM: o'chirilgan buyurtmalar ham hisobga olinadi — moliyaviy
    # tarix (shu kunning haqiqiy savdosi) o'zgarmasligi kerak.
    # M6 (2026-09-18) — TENANT: kunlik moliyaviy ko'rinishning HAR BIR
    # qismi joriy korxona bo'yicha.
    from models import Inventory as _Inv_day, Order as _Ord_day
    _otq = db.query(Order).filter(
        Order.completed_at >= start,
        Order.completed_at < end,
        Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED])
    )
    if company_id is not None:
        _otq = _otq.filter(Order.company_id == company_id)
    orders_today = _otq.all()

    total_sales = 0.0
    total_cost = 0.0
    for o in orders_today:
        p = calculate_order_profit(db, o.id, company_id=company_id)
        if p.get("success"):
            total_sales += p["sotuv_narxi"]
            total_cost += p["tan_narxi"]

    # ── 1b) SAVDO — shu kun to'g'ridan-to'g'ri sotilgan tayyor mahsulotlar ──
    # (Tayyor mahsulotlar bo'limidan, buyurtmasiz sotilganlar — avval bu
    # "Bugungi holat"da hisobga olinmasdi, garchi oylik hisobotda bor edi.)
    _fsq_day = db.query(FinishedProductSale).filter(
        FinishedProductSale.sold_at >= start,
        FinishedProductSale.sold_at < end
    )
    if company_id is not None:
        _fsq_day = _fsq_day.filter(FinishedProductSale.company_id == company_id)
    fp_sales_today = _fsq_day.all()
    for s in fp_sales_today:
        total_sales += float(s.total_amount or 0)
        total_cost += float(s.cost_amount or 0)

    total_profit = total_sales - total_cost

    # ── 2) XARAJAT — xomashyo xaridi (nimaga qancha) ──
    # MUHIM: "boshlang'ich ombor" kirimlar bu yerga kirmaydi (yuqoridagi
    # get_purchase_stats_for_period bilan bir xil sabab).
    _ptq = db.query(InventoryPurchase).filter(
        InventoryPurchase.purchased_at >= start,
        InventoryPurchase.purchased_at < end,
        InventoryPurchase.is_opening_stock.isnot(True)
    )
    if company_id is not None:      # ota (material) orqali
        _ptq = _ptq.join(_Inv_day, _Inv_day.id == InventoryPurchase.inventory_id).filter(
            _Inv_day.company_id == company_id)
    purchases_today = _ptq.all()
    material_total = sum(float(p.total_amount or 0) for p in purchases_today)
    material_breakdown = {}
    for p in purchases_today:
        material_breakdown[p.item_name] = material_breakdown.get(p.item_name, 0.0) + float(p.total_amount or 0)

    # ── 3) XARAJAT — boshqa (arenda, elektr va h.k.) ──
    _oeq = db.query(ExpenseTransaction).filter(
        ExpenseTransaction.date >= start,
        ExpenseTransaction.date < end
    )
    if company_id is not None:
        _oeq = _oeq.filter(ExpenseTransaction.company_id == company_id)
    other_today = _oeq.all()
    other_total = sum(float(e.amount or 0) for e in other_today)
    other_breakdown = {}
    for e in other_today:
        other_breakdown[e.category] = other_breakdown.get(e.category, 0.0) + float(e.amount or 0)

    # ── 4) XARAJAT — transport (kompaniya o'z zimmasiga olgan yetkazish xarajati) ──
    from models import Delivery
    _dtq = db.query(Delivery).filter(
        Delivery.delivered_at >= start,
        Delivery.delivered_at < end,
        Delivery.transport_cost > 0
    )
    if company_id is not None:      # ota (buyurtma) orqali
        _dtq = _dtq.join(_Ord_day, _Ord_day.id == Delivery.order_id).filter(
            _Ord_day.company_id == company_id)
    deliveries_today = _dtq.all()
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


def get_finance_history(db: Session, months_count: int = 12, company_id: int = None) -> list:
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
            rep = get_monthly_report(db, yy, mm, company_id=company_id)
            rep["year"] = yy
            rep["month"] = mm
            history.append(rep)
        except Exception:
            continue
    return list(reversed(history))  # eskisidan yangisiga


# ============================================================
# kech56 (13-band, 7-qadam) — BRAK TAHLILI
# ============================================================
# Foydalanuvchi qarorlari (kech56, tugma bilan): me'yor "5 %" (`crud.BRAK_MEYORI_FOIZ`),
# sabab ro'yxati (`crud.BRAK_SABABLARI`), javobgar hodim — ixtiyoriy.
# Texnik qaror (Claude): brak ULUSHI = oylik brak xarajati ÷ ishlab chiqarish tan
# narxi × 100 — ikkala son `get_monthly_report` dan (Moliya bilan BIR manba, narxlar
# muzlatilgan). Taqsimot (bosqich / sabab / javobgar / detal) — shu oyning brak
# YOZUVLARI qiymati bo'yicha (buyurtma detali braki `refund_amount`, tayyor mahsulot
# yo'qotishi `cost_amount`). Faqat O'QIYDI — hech narsa yozmaydi.

def _brak_oylari(year: int, month: int, oylar: int) -> list:
    """(yil, oy) juftlari — eskisidan yangisiga, oxirgisi (year, month)."""
    natija = []
    y, m = int(year), int(month)
    for _ in range(max(1, int(oylar))):
        natija.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(natija))


def _brak_foizi(brak: float, ishlab: float):
    """Brak ulushi foizda (2 xona). Ishlab chiqarish tan narxi 0 bo'lsa — None:
    bo'lib bo'lmaydi, taxmin qilinmaydi (UI "hisoblab bo'lmaydi" deydi)."""
    if ishlab is None or float(ishlab) <= 0:
        return None
    return round(float(brak or 0) / float(ishlab) * 100.0, 2)


def get_brak_tahlil(db: Session, year: int, month: int, company_id: int = None,
                    oylar: int = 6) -> dict:
    """Oylik brak tahlili: ulush va me'yor (ogohlantirish), bosqich / sabab /
    javobgar hodim / detal bo'yicha taqsimot, tayyor mahsulot yo'qotishlari
    ro'yxati va oxirgi `oylar` oy bo'yicha ulush."""
    import crud as _cr
    from models import ReturnItem, ReturnReason, FinishedProductLoss, Employee
    from sqlalchemy import extract

    meyor = float(_cr.BRAK_MEYORI_FOIZ)

    # 1) Ulush — Moliya bilan BIR manba.
    trend = []
    for (yy, mm) in _brak_oylari(year, month, oylar):
        rep = get_monthly_report(db, yy, mm, company_id=company_id)
        brak = float(rep.get("brak_xarajat") or 0)
        ishlab = float(rep.get("ishlab_chiqarish_xarajat") or 0)
        foiz = _brak_foizi(brak, ishlab)
        trend.append({
            "yil": yy, "oy": mm,
            "brak_xarajat": round(brak),
            "ishlab_chiqarish_xarajat": round(ishlab),
            "brak_foizi": foiz,
            "meyordan_oshdi": bool(foiz is not None and foiz > meyor),
        })
    joriy = trend[-1]

    # 2) Shu oyning yozuvlari (korxona filtri bilan).
    _rq = db.query(ReturnItem).filter(
        ReturnItem.reason == ReturnReason.DEFECT,
        extract('year', ReturnItem.returned_at) == year,
        extract('month', ReturnItem.returned_at) == month,
    )
    if company_id is not None:
        _rq = _rq.filter(ReturnItem.company_id == company_id)
    braklar = _rq.order_by(ReturnItem.id).all()

    _lq = db.query(FinishedProductLoss).filter(
        extract('year', FinishedProductLoss.lost_at) == year,
        extract('month', FinishedProductLoss.lost_at) == month,
    )
    if company_id is not None:
        _lq = _lq.filter(FinishedProductLoss.company_id == company_id)
    yoqotishlar = _lq.order_by(FinishedProductLoss.id).all()

    _hodim_idlari = {r.brak_javobgar_id for r in braklar if r.brak_javobgar_id} | \
                    {l.brak_javobgar_id for l in yoqotishlar if l.brak_javobgar_id}
    ismlar = {}
    if _hodim_idlari:
        _eq = db.query(Employee.id, Employee.name).filter(Employee.id.in_(sorted(_hodim_idlari)))
        if company_id is not None:
            _eq = _eq.filter(Employee.company_id == company_id)
        ismlar = {i: n for i, n in _eq.all()}

    def _javobgar_ismi(hid):
        if not hid:
            return None
        return ismlar.get(hid) or "O'chirilgan hodim"

    yozuvlar = []
    for r in braklar:
        yozuvlar.append({
            "nomi": r.item_name or "", "birlik": r.unit or "",
            "miqdor": float(r.quantity or 0), "qiymat": float(r.refund_amount or 0),
            "bosqich": r.brak_bosqich, "sabab": r.brak_sabab, "javobgar_id": r.brak_javobgar_id,
        })
    yoqotish_royxati = []
    for l in yoqotishlar:
        ish_braki = (l.reason or "").startswith(_cr._ISH_BRAK_BELGI)
        yozuvlar.append({
            "nomi": l.product_name or "", "birlik": l.unit or "",
            "miqdor": float(l.quantity or 0), "qiymat": float(l.cost_amount or 0),
            "bosqich": l.brak_bosqich, "sabab": l.brak_sabab, "javobgar_id": l.brak_javobgar_id,
        })
        yoqotish_royxati.append({
            "id": l.id,
            "sana": l.lost_at.isoformat() if l.lost_at else None,
            "nomi": l.product_name or "",
            "miqdor": float(l.quantity or 0),
            "birlik": l.unit or "",
            "qiymat": round(float(l.cost_amount or 0), 2),
            "turi": "Ishlab chiqarish braki" if ish_braki else "Yo'qotish (tayyor turgan)",
            "bosqich": _cr.BRAK_BOSQICHLARI.get(l.brak_bosqich, l.brak_bosqich) if l.brak_bosqich else None,
            "sabab": _cr.BRAK_SABABLARI.get(l.brak_sabab, l.brak_sabab) if l.brak_sabab else None,
            "javobgar": _javobgar_ismi(l.brak_javobgar_id),
            "izoh": l.reason or "",
            "yozgan": l.created_by or "",
        })

    jami_qiymat = sum(y["qiymat"] for y in yozuvlar)

    def _ulush(q):
        return round(q / jami_qiymat * 100.0, 1) if jami_qiymat > 0 else 0.0

    def _taqsimot(maydon, yorliq_fn):
        """Kod bo'yicha guruh — qiymat kamayishi tartibida, tanlanmaganlar OXIRIDA."""
        hisob = {}
        for y in yozuvlar:
            h = hisob.setdefault(y[maydon], {"soni": 0, "qiymat": 0.0})
            h["soni"] += 1
            h["qiymat"] += y["qiymat"]
        bor = sorted((k for k in hisob if k is not None),
                     key=lambda k: (-hisob[k]["qiymat"], str(k)))
        natija = []
        for k in bor + ([None] if None in hisob else []):
            natija.append({
                "kod": k,
                "nomi": yorliq_fn(k) if k is not None else "Belgilanmagan",
                "soni": hisob[k]["soni"],
                "qiymat": round(hisob[k]["qiymat"], 2),
                "ulush": _ulush(hisob[k]["qiymat"]),
            })
        return natija

    detal = {}
    for y in yozuvlar:
        d = detal.setdefault((y["nomi"], y["birlik"]), {"soni": 0, "miqdor": 0.0, "qiymat": 0.0})
        d["soni"] += 1
        d["miqdor"] += y["miqdor"]
        d["qiymat"] += y["qiymat"]
    top = sorted(detal.items(), key=lambda kv: (-kv[1]["qiymat"], kv[0][0], kv[0][1]))[:5]

    foiz = joriy["brak_foizi"]
    oshdi = joriy["meyordan_oshdi"]
    return {
        "yil": int(year), "oy": int(month),
        "meyor_foiz": meyor,
        "brak_xarajat": joriy["brak_xarajat"],
        "ishlab_chiqarish_xarajat": joriy["ishlab_chiqarish_xarajat"],
        "brak_foizi": foiz,
        "meyordan_oshdi": oshdi,
        "ogohlantirish": (f"Brak me'yordan oshdi: {foiz:g} % (me'yor {meyor:g} %)" if oshdi else None),
        "yozuvlar_soni": len(yozuvlar),
        "yozuvlar_qiymati": round(jami_qiymat, 2),
        "bosqichlar": _taqsimot("bosqich", lambda k: _cr.BRAK_BOSQICHLARI.get(k, k)),
        "sabablar": _taqsimot("sabab", lambda k: _cr.BRAK_SABABLARI.get(k, k)),
        "javobgarlar": _taqsimot("javobgar_id", _javobgar_ismi),
        "top_detallar": [
            {"nomi": k[0], "birlik": k[1], "soni": v["soni"],
             "miqdor": round(v["miqdor"], 3), "qiymat": round(v["qiymat"], 2),
             "ulush": _ulush(v["qiymat"])}
            for k, v in top
        ],
        "yoqotishlar": yoqotish_royxati,
        "trend": trend,
    }


def _monthly_category_amount(db: Session, year: int, month: int, category: str, fallback: float,
                            company_id: int = None) -> float:
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
        _eq = db.query(ExpenseTransaction.id).filter(
            extract('year', ExpenseTransaction.date) == year,
            extract('month', ExpenseTransaction.date) == month,
            ExpenseTransaction.category == category
        )
        if company_id is not None:      # M6
            _eq = _eq.filter(ExpenseTransaction.company_id == company_id)
        exists = _eq.first()
        if not exists:
            return float(fallback or 0)
        _sq = db.query(func.sum(ExpenseTransaction.amount)).filter(
            extract('year', ExpenseTransaction.date) == year,
            extract('month', ExpenseTransaction.date) == month,
            ExpenseTransaction.category == category
        )
        if company_id is not None:
            _sq = _sq.filter(ExpenseTransaction.company_id == company_id)
        total = _sq.scalar()
        return float(total or 0)
    except Exception:
        return float(fallback or 0)


def get_monthly_report(db: Session, year: int, month: int, company_id: int = None) -> Dict:
    """
    Berilgan oy uchun to'liq moliyaviy hisobot:
    Daromad - Xarajatlar = Sof foyda
    """
    from models import Order, OrderStatus, MonthlyExpense, OrderItem, Inventory as _Inv_rep
    from sqlalchemy import func, extract
    from datetime import datetime

    def _inv_rep(inv_id):
        """M6 — TENANT: hisobot ichidagi material qidiruvlari joriy korxonadan."""
        if not inv_id:
            return None
        _q = db.query(_Inv_rep).filter(_Inv_rep.id == inv_id)
        if company_id is not None:
            _q = _q.filter(_Inv_rep.company_id == company_id)
        return _q.first()

    # ── 1. DAROMAD va SOF FOYDA (tayyor buyurtmalar) ────────
    # MUHIM: bu yerda Order.is_deleted ATAYLAB tekshirilmaydi — o'chirilgan
    # (lekin avval haqiqatan yakunlangan, daromad keltirgan) buyurtmalar ham,
    # moliyaviy hisobotda (tarixiy haqiqat sifatida) hisobga olinishi kerak.
    # "O'chirish" — faqat ro'yxatlardan (Buyurtmalar, KPI) yashirish uchun,
    # moliyaviy tarixni o'chirmasligi kerak.
    # M6 (2026-09-18) — TENANT: hisobotning BARCHA qismlari joriy korxona
    # bo'yicha (ilgari faqat tayyor mahsulot qismi filtrlangan edi).
    _roq = db.query(Order).filter(
        Order.status == OrderStatus.READY,
        extract('year',  Order.completed_at) == year,
        extract('month', Order.completed_at) == month
    )
    if company_id is not None:
        _roq = _roq.filter(Order.company_id == company_id)
    ready_orders = _roq.all()

    # MUHIM: "Kelishilgan summa" (agreed_amount) bo'lsa — shuni, aks holda
    # "Umumiy jami"ni olamiz. Bu — Buyurtmalar ro'yxati va har bir
    # buyurtmaning foyda hisobi (calculate_order_profit) bilan BIR XIL
    # manba — aks holda "Jami daromad" bu ikkisidan farq qilib qolar edi.
    daromad = sum(o.kelishilgan_summa for o in ready_orders)
    buyurtmalar_soni = len(ready_orders)

    # ── TAYYOR MAHSULOT TO'G'RIDAN-TO'G'RI SOTUVI ──
    # Bu — buyurtmasiz sotuv, alohida daromad manbai. MUHIM: bu summa
    # Usta KPI, Ehson, hodim foiz-asosidagi to'lovlariga TA'SIR QILMAYDI
    # (ular faqat haqiqiy ISHLAB CHIQARISH buyurtmalariga tegishli) —
    # faqat umumiy "Jami daromad" va "Sof foyda"ga qo'shiladi.
    from models import FinishedProductSale as _FPS
    # 2026-09-18 — TENANT (M7 validatsiyasida B sessiyasidan topilgan
    # HAQIQIY sizish): bu so'rov korxona filtrisiz edi. B ning oylik
    # hisobotida A ning tayyor mahsulot sotuvi (812 000 so'm) daromad
    # sifatida ko'rinardi, holbuki B da birorta sotuv yo'q.
    _fpsq = db.query(_FPS).filter(
        extract('year', _FPS.sold_at) == year,
        extract('month', _FPS.sold_at) == month
    )
    if company_id is not None:
        _fpsq = _fpsq.filter(_FPS.company_id == company_id)
    fp_sales = _fpsq.all()
    fp_sales_daromad = sum(float(s.total_amount or 0) for s in fp_sales)
    fp_sales_tannarx = sum(float(s.cost_amount or 0) for s in fp_sales)
    fp_sales_foyda = fp_sales_daromad - fp_sales_tannarx

    # Har buyurtma uchun foyda hisoblaymiz
    ishlab_chiqarish_xarajat = 0.0
    for order in ready_orders:
        try:
            profit_data = calculate_order_profit(db, order.id, company_id=company_id)
            ishlab_chiqarish_xarajat += float(profit_data.get("tan_narxi", 0))
        except Exception as e:
            try:
                import crud as _crud_log
                _crud_log.log_error(db, str(e), endpoint=f"get_monthly_report:calculate_order_profit order#{order.id}")
            except Exception:
                pass

    sof_daromad = daromad - ishlab_chiqarish_xarajat

    # ── 2. QOPLAMACHI BONUS hisoblash ───────────────────────
    # Profil/karniz → uzunlik (metr) × miqdor × 1000 so'm
    # Panel/boshqa  → miqdor × 1000 so'm
    # Xuddi yuqoridagidek — o'chirilgan buyurtmalar ham hisobga olinadi
    # (moliyaviy tarix saqlanishi uchun, "O'chirilganlar" xodim bonusini
    # ham noto'g'ri kamaytirib yubormasligi kerak).
    _otmq = db.query(Order).filter(
        Order.status == OrderStatus.READY,
        extract('year',  Order.completed_at) == year,
        extract('month', Order.completed_at) == month
    )
    if company_id is not None:      # M6
        _otmq = _otmq.filter(Order.company_id == company_id)
    orders_this_month = _otmq.all()

    jami_metr = 0.0   # Profil uchun (metr)
    jami_panel_metr = 0.0  # Panel uchun (metr)
    jami_dona = 0.0   # Donali uchun (dona)

    for order in orders_this_month:
        for item in order.items:
            if (item.category or "").lower() == "gips":
                # MUHIM: Gips — bu yerga MUTLAQO kira olmaydi (is_coated
                # holatidan qat'iy nazar). Gips o'z, alohida bo'limida
                # (pastda) hisoblanadi.
                continue
            if item.finished_product_id:
                # MUHIM: bu detal "Tayyor mahsulotdan" tanlangan (ombordagi
                # mavjud zaxiradan olingan) — uning ishlab chiqarilishi
                # ALLAQACHON, o'sha mahsulot birinchi marta ishlab
                # chiqarilib "Sotuvga tayyor" bo'lganda hisoblangan edi.
                # Shu buyurtmada YANA hisoblasak — IKKI MARTA to'lagan
                # bo'lardik, shuning uchun BU YERDA o'tkazib yuboriladi.
                continue

            # MUHIM: Ichki qo'shimcha detallar (sub_details) — bularning
            # qoplama holati ASOSIY detalning is_coated'idan TO'LIQ
            # MUSTAQIL (xodim har bir ichki detalni alohida belgilaydi).
            # Shuning uchun bu tekshiruv "if not item.is_coated: continue"
            # dan OLDIN, alohida turadi — aks holda: (a) asosiy qoplamasiz
            # bo'lgan holatda uning qoplamali ichki detali umuman
            # hisoblanmay qolardi, (b) asosiy qoplamali bo'lgan holatda esa
            # ichki detal HAM qoplamali bo'lsa, o'sha ichki ishning o'zi
            # hech qachon qo'shilmas edi (qoplamachi kam to'lov olardi).
            # Aksincha — ichki detal qoplamasiz bo'lsa, asosiy qoplamali
            # bo'lishidan qat'iy nazar, HECH QACHON qo'shilmaydi (mijozdan
            # olinmagan pul uchun xodimga ortiqcha to'lanmasligi kerak).
            for sub in (item.sub_details or []):
                if not getattr(sub, 'is_coated', False):
                    continue
                sub_cat = (getattr(sub, 'category', None) or '').lower()
                if sub_cat == 'panel':
                    jami_panel_metr += float(getattr(sub, 'quantity', 0) or 0)
                else:  # 'profil' (standart)
                    _sub_len = float(getattr(sub, 'length', 0) or 0)
                    _sub_qty = float(getattr(sub, 'quantity', 1) or 1)
                    jami_metr += _sub_len * _sub_qty

            if not item.is_coated:
                continue

            category = (item.category or "").lower()
            if category in ["profil", "karniz"]:
                # Profil: uzunlik (m) × miqdor
                uzunlik_m = float(item.length or 0)
                jami_metr += uzunlik_m * float(item.quantity or 1)

            elif category == "blok":
                # Blok — "necha metr kerak" item.quantity'da saqlanadi
                # (Profilga o'xshab, lekin uzunlik emas, to'g'ridan-to'g'ri
                # miqdor maydonida)
                jami_metr += float(item.quantity or 0)

            elif category == "panel":
                # MUHIM: Panelda "Miqdor" maydonining o'zi — METR ma'nosini
                # bildiradi (masalan "100 metr panel"), "Uzunlik" maydoni esa
                # panel uchun ATAYLAB ishlatilmaydi (frontendda har doim 0
                # qilib qo'yiladi). Shuning uchun panel metri —
                # item.quantity'dan olinadi, item.length'dan EMAS.
                jami_panel_metr += float(item.quantity or 0)

            elif category == "dona":
                jami_dona += float(item.quantity or 1)

            # MUHIM: "loy_sotish", "gips" — bu yerga UMUMAN qo'shilmaydi.
            # Gips — butunlay alohida, pastdagi bo'limda hisoblanadi.

    # TAYYOR MAHSULOTLAR sahifasidan ISHLAB CHIQARILIB, "SOTUVGA TAYYOR"
    # deb belgilangan mahsulotlar (buyurtmasiz) — hodim shu ishni ham
    # qilgani uchun, bu ham hodim oyligiga qo'shiladi.
    # 11.2b (2026-09-20): avval bu yerda "G'isht" nomli mahsulot YAGONA
    # istisno sifatida chiqarib tashlanardi (BYPRODUCT deb). G'isht
    # butunlay olib tashlangani uchun istisno ham olib tashlandi — endi
    # ishlab chiqarilgan BARCHA mahsulot hodim oyligiga kiradi.
    from models import FinishedProduct, StockSource, ProductionStatus
    from datetime import datetime as _dt2
    _dp_start = _dt2(year, month, 1)
    _dp_end = _dt2(year + 1, 1, 1) if month == 12 else _dt2(year, month + 1, 1)
    # 2026-09-18 — TENANT (o'sha validatsiyada topilgan ikkinchi so'rov):
    # ishlab chiqarilgan miqdorlar ham korxona filtrisiz o'qilardi.
    #
    # 22-band (2026-09-21, FOYDALANUVCHI QARORI "2") — O'LCHANGAN
    # (`work/probe22.py`). Ilgari bu so'rov mahsulot holatini UMUMAN
    # ko'rmasdi va oyni `created_at` (ishlab chiqarishga QO'YILGAN sana)
    # bo'yicha ajratardi. Natijada ikki xato bor edi:
    #   (a) hali JARAYONDAGI (IN_PROGRESS), ya'ni qoplanmagan mahsulot ham
    #       darhol qoplamachi bonusiga kirardi (10 metr → +10 000 so'm,
    #       "Tayyor" bosilganda esa bonus BOSHQA o'zgarmasdi — demak haq
    #       ish bitgani uchun emas, ish BOSHLANGANI uchun to'lanardi);
    #   (b) avgustda boshlanib sentyabrda tayyor bo'lgan mahsulot
    #       AVGUST oyiga tushardi (o'lchandi: avgust bonusi 7 000) —
    #       ya'ni yopilgan oyning hisoboti keyin o'zgarib ketardi.
    # Endi: FAQAT "Sotuvga tayyor" (READY) mahsulot hisoblanadi va u
    # TAYYOR BO'LGAN oyga tushadi (`finished_production_at`). Eski
    # yozuvlarda bu ustun bo'sh bo'lishi mumkin (u 2026-09 da qo'shilgan)
    # — o'shalar uchun `created_at` ga qaytiladi, shunda tarix buzilmaydi.
    #
    # Bu — buyurtmalar bilan ham SIMMETRIK: yuqoridagi tsikl buyurtma
    # detallarini faqat buyurtma "Tayyor" (READY) bo'lgan va shu oyda
    # yakunlangan (`completed_at`) holatda qo'shadi.
    _tayyor_sana = func.coalesce(FinishedProduct.finished_production_at,
                                 FinishedProduct.created_at)
    _dpq = db.query(FinishedProduct).filter(
        FinishedProduct.source == StockSource.PRODUCED,
        FinishedProduct.production_status == ProductionStatus.READY,
        _tayyor_sana >= _dp_start,
        _tayyor_sana < _dp_end
    )
    if company_id is not None:
        _dpq = _dpq.filter(FinishedProduct.company_id == company_id)
    direct_produced = _dpq.all()
    for fp in direct_produced:
        cat = (fp.category or "").lower()
        # MUHIM: `quantity` — SOTISH/BRAK orqali KAMAYADI (joriy qoldiq).
        # Hodim oyligi esa — mahsulot ASLIDA qancha ishlab chiqarilgani
        # bo'yicha hisoblanishi kerak, keyinchalik sotilgan-sotilmaganidan
        # QAT'IY NAZAR. Shuning uchun `produced_quantity` (muzlatilgan,
        # "Sotuvga tayyor" bo'lgan paytdagi son) ishlatiladi. Eski
        # yozuvlarda bu maydon bo'sh bo'lishi mumkin — fallback sifatida
        # joriy `quantity` ishlatiladi.
        qty = float(fp.produced_quantity if fp.produced_quantity is not None else (fp.quantity or 0))
        if cat == "gips":
            # 11.2b (5-qadam): gipsga bog'liq hodim to'lovining OXIRGISI
            # (qoliplik gul / gul_rate) ham olib tashlandi. Eski
            # ma'lumotda category='gips' mahsulot uchrashi mumkin —
            # u hodim oyligiga HECH QANDAY yo'l bilan kirmasligi SHART,
            # shuning uchun bu yerda ATAYLAB o'tkazib yuboriladi.
            # (Pastdagi qoplamachi bonusiga ham tushmaydi — gipsda
            # "qoplama" tushunchasi yo'q, u o'zi tayyor mahsulot.)
            continue
        # MUHIM: Gipsdan boshqa barchasi uchun — faqat HAQIQATAN qoplamali
        # (is_coated=True) bo'lsa, Qoplamachi bonusiga qo'shiladi. Qoplamasiz
        # ishlab chiqarilgan mahsulot — bu bonusga aloqasi yo'q.
        if not fp.is_coated:
            continue
        if cat in ["profil", "karniz"]:
            jami_metr += qty
        elif cat == "panel":
            jami_panel_metr += qty
        else:
            jami_dona += qty

    # MUHIM: Tayyor mahsulotlar bo'limida ("Ishlab chiqarish" tugmasi
    # orqali, mijoz buyurtmasiga bog'lanmasdan) tayyorlangan qoplamali
    # mahsulotlar — YUQORIDA, "direct_produced" tsiklida ALLAQACHON
    # hisoblangan (is_coated tekshiruvi bilan birga). Bu yerda AVVAL
    # yana bir marta hisoblovchi, DUBLIKAT tsikl bor edi — u xuddi shu
    # mahsulotlarni IKKI MARTA qo'shib yuborardi (masalan 200 dona o'rniga
    # 400 dona bo'lib chiqishi kabi). Endi bu yerda hech narsa qilinmaydi.

    qoplamachi_bonus_avtomatik = (jami_metr + jami_panel_metr + jami_dona) * 1000
    jami_m2 = jami_metr + jami_panel_metr

    # Jami ishlatilgan blok (hodim to'lovi "per_unit: blok" uchun)
    jami_blok = 0.0
    default_p = get_default_penoplast(db, company_id=company_id)
    for order in orders_this_month:
        for item in order.items:
            if getattr(item, 'finished_product_id', None):
                continue
            vol = _item_volume_m3(db, item, default_p)
            pid = item.penoplast_id or (default_p.id if default_p else None)
            p = _inv_rep(pid)
            if p and p.volume_per_unit:
                jami_blok += vol / float(p.volume_per_unit)

    from models import FinishedProduct, StockSource
    from datetime import datetime as _dt
    fp_start = _dt(year, month, 1)
    fp_end = _dt(year + 1, 1, 1) if month == 12 else _dt(year, month + 1, 1)
    # M4 (2026-09-18) — TENANT: hisobotning TAYYOR MAHSULOT qismi.
    # ESLATMA: bu funksiyaning qolgan so'rovlari hali tenant bilan
    # cheklanmagan — ular M6 (moliya/hisobotlar) bosqichida ko'riladi.
    _fpm = db.query(FinishedProduct).filter(
        FinishedProduct.source == StockSource.PRODUCED,
        FinishedProduct.created_at >= fp_start,
        FinishedProduct.created_at < fp_end
    )
    if company_id is not None:
        _fpm = _fpm.filter(FinishedProduct.company_id == company_id)
    finished_this_month = _fpm.all()
    for fp in finished_this_month:
        if fp.penoplast_id and fp.volume_m3:
            p = _inv_rep(fp.penoplast_id)
            if p and p.volume_per_unit:
                jami_blok += float(fp.volume_m3) / float(p.volume_per_unit)

    # ── 3. XARAJATLAR (bazadan) ──────────────────────────────
    _mexq = db.query(MonthlyExpense).filter(
        MonthlyExpense.year  == year,
        MonthlyExpense.month == month
    )
    if company_id is not None:      # M6
        _mexq = _mexq.filter(MonthlyExpense.company_id == company_id)
    expense = _mexq.first()

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
    xarajatlar["arenda"]   = _monthly_category_amount(db, year, month, "arenda",   xarajatlar["arenda"], company_id=company_id)
    xarajatlar["elektr"]   = _monthly_category_amount(db, year, month, "elektr",   xarajatlar["elektr"], company_id=company_id)
    xarajatlar["tushlik"]  = _monthly_category_amount(db, year, month, "tushlik",  xarajatlar["tushlik"], company_id=company_id)
    xarajatlar["soliqlar"] = _monthly_category_amount(db, year, month, "soliqlar", xarajatlar["soliqlar"], company_id=company_id)

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
        ~ExpenseTransaction.category.in_(KNOWN_FIXED_CATEGORIES),
        *( [ExpenseTransaction.company_id == company_id] if company_id is not None else [] )  # M6
    ).group_by(ExpenseTransaction.category).all()
    qoshimcha_xarajatlar = {cat: float(total or 0) for cat, total in extra_rows}
    qoshimcha_xarajat_jami = sum(qoshimcha_xarajatlar.values())

    # ── 3b. BRAK (yaroqsiz) SABABLI ISROF BO'LGAN XOMASHYO ─────
    # Bu — haqiqiy zarar (xomashyo ishlatildi, lekin sotilmadi), shuning
    # uchun boshqa xarajatlar kabi Sof foydadan ayirilishi kerak.
    import crud as _crud_brak
    from datetime import datetime as _dt_brak
    _brak_start = _dt_brak(year, month, 1)
    _brak_end = _dt_brak(year + 1, 1, 1) if month == 12 else _dt_brak(year, month + 1, 1)
    try:
        brak_summary = _crud_brak.get_brak_material_summary(db, start_date=_brak_start, end_date=_brak_end, company_id=company_id)
        brak_xarajat = float(brak_summary.get("total_value", 0) or 0)
    except Exception:
        brak_xarajat = 0.0

    # Tayyor mahsulot brak/yo'qotishi (masalan sinib qolgan Gips mahsulot) —
    # bu ham Brak xarajatiga qo'shiladi, xuddi xomashyo brak'i kabi.
    # MUHIM (2026-09 chuqur audit — ikkinchi bosqich): "Ishlab chiqarish
    # jarayonidagi brak" (record_finished_product_production_brak, Tayyor
    # mahsulotlar sahifasi) uchun QO'SHIMCHA sarflangan xomashyo (Penoplast/
    # Loy) IKKI YO'LDA ham qayd etiladi — (1) shu FinishedProductLoss
    # yozuvining cost_amount'ida VA (2) InventoryMovement'da ("Brak
    # (ishlab chiqarish) — ..." sababi bilan, get_brak_material_summary()
    # buni "Brak%" naqshi orqali yig'ib, yuqorida brak_xarajat'ga
    # allaqachon qo'shib bo'lgan). Shuning uchun bu yerda FAQAT haqiqiy
    # "zaxiradan kamaytirish" (record_finished_product_loss, xomashyoga
    # umuman tegmaydi) yozuvlari hisoblanadi — "ishlab chiqarish braki"
    # yozuvlari BU YERDA hisobga OLINMAYDI, aks holda IKKI MARTA
    # ayirilib, "Sof foyda" haqiqatdan kamroq ko'rsatilardi.
    from models import FinishedProductLoss as _FPL
    # kech57 (40-band): belgi — YAGONA manba `crud._ISH_BRAK_BELGI` (ilgari shu
    # yerda literal nusxa edi; biri o'zgarsa ishlab chiqarish braki ikki marta
    # ayirilardi yoki bekor qilish ruxsat etilardi).
    import crud as _crud_belgi
    _PROD_BRAK_MARKER = _crud_belgi._ISH_BRAK_BELGI
    _fplq = db.query(_FPL).filter(
        extract('year', _FPL.lost_at) == year,
        extract('month', _FPL.lost_at) == month
    )
    if company_id is not None:      # M6
        _fplq = _fplq.filter(_FPL.company_id == company_id)
    fp_losses = _fplq.all()
    fp_loss_xarajat = sum(
        float(l.cost_amount or 0) for l in fp_losses
        if not (l.reason or '').startswith(_PROD_BRAK_MARKER)
    )
    brak_xarajat += fp_loss_xarajat

    # Jami xarajat (arenda/elektr/tushlik/soliq/reklama/kutilmagan va h.k. — hodim
    # to'lovi endi "Ustalar KPI / Hodimlar" bo'limida alohida hisoblanadi)
    jami_xarajat_eski = (
        xarajatlar["arenda"] +
        xarajatlar["elektr"] +
        xarajatlar["tushlik"] +
        xarajatlar["soliqlar"] +
        qoshimcha_xarajat_jami +
        brak_xarajat
    )

    # ── 4b. USTA YILLIK KPI (oylik ulush) ─────────────────────
    kpi_result = calculate_monthly_master_kpi(db, year, month, company_id=company_id)
    usta_kpi_xarajat = kpi_result["total"]

    # ── 4b2. EHSON (admin belgilagan foiz, sof foydadan) ──────
    ehson_result = calculate_monthly_ehson(db, year, month, company_id=company_id)
    ehson_xarajat = ehson_result["ehson_amount"]

    # ── 4c. MOSLASHUVCHAN HODIMLAR ─────────────────────────────
    # Foyda (hodim xarajatigacha) — sotuvdan% / foydadan% hisoblash uchun.
    # MUHIM: Tayyor mahsulot to'g'ridan-to'g'ri sotuvi —
    # bu ham korxona sotuvi/foydasi, shuning uchun "sotuvdan %"/"foydadan %"
    # asosida to'lanadigan hodimlar uchun HAM hisobga olinadi (Ehson bilan
    # bir xil mantiq). Lekin ISHLAB CHIQARISH MIQDORIGA (metr/dona/qop)
    # bog'liq to'lov turlariga — ta'sir qilmaydi (chunki sotish — yangi
    # jismoniy ishlab chiqarish emas, faqat ombordagi tayyor narsani sotish).
    sof_foyda_before_emp = sof_daromad - jami_xarajat_eski - usta_kpi_xarajat - ehson_xarajat + fp_sales_foyda
    emp_result = calculate_monthly_employee_pay(
        db, year, month, daromad + fp_sales_daromad, sof_foyda_before_emp,
        jami_metr + jami_panel_metr, jami_dona, jami_blok,
        jami_qoplama_birlik=jami_metr + jami_panel_metr + jami_dona,
        company_id=company_id
    )
    hodimlar_moslashuvchan_xarajat = emp_result["total"]
    jami_xarajat = jami_xarajat_eski + usta_kpi_xarajat + ehson_xarajat + hodimlar_moslashuvchan_xarajat

    sof_foyda = sof_daromad - jami_xarajat + fp_sales_foyda
    foyda_foiz = (sof_foyda / (daromad + fp_sales_daromad) * 100) if (daromad + fp_sales_daromad) > 0 else 0

    # ── 5. NAQD XARAJATLAR (xomashyo xaridi + transport) ─────
    # Diqqat: bu "ishlab_chiqarish_xarajat" dan FARQ QILADI —
    # u shu oy TUGAGAN buyurtmalarga sarflangan xomashyo tan narxi,
    # bu esa shu oy SOTIB OLINGAN xomashyo puli (hali ishlatilmagan bo'lishi mumkin).
    purchase_stats = get_purchase_stats_for_period(db, year, month, company_id=company_id)
    transport_stats = get_transport_stats_for_period(db, year, month, company_id=company_id)

    xomashyo_xaridi = purchase_stats["total_amount"]
    transport_kirish = transport_stats["inbound_total"]
    transport_chiqish = transport_stats["outbound_company"]
    naqd_xarajat_jami = xomashyo_xaridi + transport_kirish + transport_chiqish

    # ── 6. TURLAR BO'YICHA TAQSIMOT (informatsion, faqat ko'rsatish uchun) ──
    # Daromad — har bir detalning ulushi bo'yicha (kelishilgan summaga mos
    # proporsiyada), Gips va qolgan (Penoplast va h.k.) ga bo'linadi.
    gips_daromad = 0.0
    penoplast_daromad = 0.0
    for order in ready_orders:
        order_total = float(order.total_amount or 0)
        order_agreed = order.kelishilgan_summa
        if order_total <= 0:
            continue
        for item in order.items:
            share = (float(item.total_price or 0) / order_total) * order_agreed
            if (item.category or '').lower() == 'gips':
                gips_daromad += share
            else:
                penoplast_daromad += share

    # Tayyor mahsulotlar bo'limidan to'g'ridan-to'g'ri (buyurtmasiz)
    # sotilganlar — shu yuqoridagi fp_sales ro'yxatidan, kategoriyasi
    # bo'yicha taqsimlanadi (avval bu grafikda hisobga olinmasdi).
    for s in fp_sales:
        s_total = float(s.total_amount or 0)
        cat = (s.finished_product.category if s.finished_product else '') or ''
        if cat.lower() == 'gips':
            gips_daromad += s_total
        else:
            penoplast_daromad += s_total

    # Xarajat — "Xarajat qo'shish"da yo'nalish belgilangan tranzaksiyalar
    # (Umumiy/Penoplast/Gips), shu oy uchun.
    from models import ExpenseTransaction as _ET, TransportExpense as _TE
    from sqlalchemy import extract as _extract_pt, func as _func_pt
    # M6 — TENANT: gips/penoplast bo'linishidagi 4 ta agregat.
    def _pt_scope(q, model):
        return q.filter(model.company_id == company_id) if company_id is not None else q

    gips_qoshimcha_xarajat = float(_pt_scope(db.query(_func_pt.sum(_ET.amount)).filter(
        _ET.production_type == 'gips',
        _extract_pt('year', _ET.date) == year, _extract_pt('month', _ET.date) == month
    ), _ET).scalar() or 0) + float(_pt_scope(db.query(_func_pt.sum(_TE.amount)).filter(
        _TE.production_type == 'gips',
        _extract_pt('year', _TE.expense_date) == year, _extract_pt('month', _TE.expense_date) == month
    ), _TE).scalar() or 0)
    penoplast_qoshimcha_xarajat = float(_pt_scope(db.query(_func_pt.sum(_ET.amount)).filter(
        _ET.production_type == 'penoplast',
        _extract_pt('year', _ET.date) == year, _extract_pt('month', _ET.date) == month
    ), _ET).scalar() or 0) + float(_pt_scope(db.query(_func_pt.sum(_TE.amount)).filter(
        _TE.production_type == 'penoplast',
        _extract_pt('year', _TE.expense_date) == year, _extract_pt('month', _TE.expense_date) == month
    ), _TE).scalar() or 0)

    turlar_boyicha = {
        "gips": {"daromad": round(gips_daromad), "qoshimcha_xarajat": round(gips_qoshimcha_xarajat)},
        "penoplast": {"daromad": round(penoplast_daromad), "qoshimcha_xarajat": round(penoplast_qoshimcha_xarajat)},
    }

    return {
        "year": year,
        "month": month,
        "month_name": [
            "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
            "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"
        ][month],
        "daromad": round(daromad + fp_sales_daromad),
        "daromad_buyurtmalardan": round(daromad),
        "fp_sales_daromad": round(fp_sales_daromad),
        "fp_sales_foyda": round(fp_sales_foyda),
        "fp_sales_soni": len(fp_sales),
        "fp_loss_xarajat": round(fp_loss_xarajat),
        "fp_loss_soni": len(fp_losses),
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
        # Ehson (admin belgilagan foiz)
        "ehson_percent": ehson_result["percent"],
        "ehson_xarajat": ehson_xarajat,
        "brak_xarajat": round(brak_xarajat),
        # Faqat yakunlangan BUYURTMALARNING sof foydasi (oylik xarajatlarsiz) —
        # "Sof foyda"dan FARQLI, qo'shimcha ko'rsatkich. Allaqachon ehson_result
        # ichida hisoblangan qiymatning o'zi — yangi hisob-kitob emas.
        "buyurtmalar_foydasi": ehson_result["monthly_profit"],
        # Moslashuvchan hodimlar
        "hodimlar_moslashuvchan_xarajat": hodimlar_moslashuvchan_xarajat,
        "hodimlar_moslashuvchan_breakdown": emp_result["breakdown"],
        "turlar_boyicha": turlar_boyicha,
        "jami_blok": round(jami_blok, 2),
        # Naqd xarajatlar (alohida ko'rsatkich — foyda hisobiga kirmaydi)
        "xomashyo_xaridi": xomashyo_xaridi,
        "xomashyo_by_material": purchase_stats["by_material"],
        "transport_kirish": transport_kirish,
        "transport_chiqish_company": transport_chiqish,
        "naqd_xarajat_jami": naqd_xarajat_jami,
    }


def calculate_split_profit_report(db: Session, year: int, month: int, company_id: int = None) -> dict:
    """Gips va Penoplast uchun MUSTAQIL, to'liq ajratilgan sof foyda hisoboti.

    Taqsimlash mantiqi:
    - To'g'ridan-to'g'ri xarajatlar (xomashyo, brak) — aniq, buyurtma
      detali darajasida ajratiladi.
    - Hodim to'lovi — har bir hodimning belgilangan Yo'nalishiga (Employee.
      production_type) 100% yoziladi. Yo'nalish belgilanmagan hodimlar —
      daromad nisbatiga qarab bo'linadi.
    - Umumiy xarajatlar (arenda, svet, soliq, tushlik, Ehson, Yo'nalish
      belgilanmagan qo'shimcha xarajatlar) — daromad nisbatiga qarab
      bo'linadi (bitta joyda ikkalasi ham faoliyat yuritgani uchun).
    """
    from models import Employee
    from sqlalchemy import func, extract

    # M6 (2026-09-18) — TENANT: bo'lingan foyda hisobotining barcha qismlari.
    full = get_monthly_report(db, year, month, company_id=company_id)
    tb = full.get("turlar_boyicha", {})
    gips_daromad = float(tb.get("gips", {}).get("daromad", 0))
    peno_daromad = float(tb.get("penoplast", {}).get("daromad", 0))
    total_daromad = gips_daromad + peno_daromad
    gips_share = (gips_daromad / total_daromad) if total_daromad > 0 else 0.5
    peno_share = 1 - gips_share

    # ── 1. TO'G'RIDAN-TO'G'RI XARAJAT (xomashyo tan narxi) — buyurtma
    # detali darajasida, calculate_order_profit()ning breakdown'idan,
    # "🧱 Gips" bilan boshlanuvchi qatorlarni ajratib olamiz.
    _spq = db.query(Order).filter(
        Order.status == OrderStatus.READY,
        extract('year', Order.completed_at) == year,
        extract('month', Order.completed_at) == month
    )
    if company_id is not None:
        _spq = _spq.filter(Order.company_id == company_id)
    ready_orders = _spq.all()
    gips_direct_cost = 0.0
    peno_direct_cost = 0.0
    for o in ready_orders:
        try:
            profit_data = calculate_order_profit(db, o.id, company_id=company_id)
        except Exception:
            continue
        for line in profit_data.get("breakdown", []):
            amt = float(line.get("summa", 0))
            if str(line.get("nomi", "")).startswith("🧱 Gips"):
                gips_direct_cost += amt
            else:
                peno_direct_cost += amt

    # ── 2. HODIM TO'LOVI — Yo'nalish bo'yicha aniq, belgilanmaganlar ulush bo'yicha
    gips_emp = 0.0
    peno_emp = 0.0
    umumiy_emp = 0.0
    emp_ids = {b["employee_id"] for b in full.get("hodimlar_breakdown", [])}
    emp_map = {e.id: e for e in db.query(Employee).filter(Employee.id.in_(emp_ids)).all()} if emp_ids else {}
    for b in full.get("hodimlar_breakdown", []):
        emp = emp_map.get(b["employee_id"])
        pt = (emp.production_type if emp else None) or None
        amt = float(b.get("amount", 0))
        if pt == "gips":
            gips_emp += amt
        elif pt == "penoplast":
            peno_emp += amt
        else:
            umumiy_emp += amt
    gips_emp += umumiy_emp * gips_share
    peno_emp += umumiy_emp * peno_share

    # ── 3. UMUMIY XARAJATLAR (arenda/svet/tushlik/soliq/qo'shimcha/Ehson/
    # brak) — bitta joyda faoliyat yuritilgani uchun, daromad nisbatida
    xarajatlar = full.get("xarajatlar", {})
    umumiy_overhead = (
        float(xarajatlar.get("arenda", 0)) + float(xarajatlar.get("elektr", 0)) +
        float(xarajatlar.get("tushlik", 0)) + float(xarajatlar.get("soliqlar", 0))
    )
    # Yo'nalish BELGILANMAGAN qo'shimcha xarajatlar (production_type=None bo'lganlar)
    from models import ExpenseTransaction as _ET2
    from datetime import datetime as _dt2
    _s = _dt2(year, month, 1)
    _e = _dt2(year + 1, 1, 1) if month == 12 else _dt2(year, month + 1, 1)
    # Yo'nalish BELGILANMAGAN qo'shimcha xarajatlar (production_type=None) —
    # bular taxminiy (nisbat bo'yicha) taqsimlanadi
    def _sp_scope(q, model):
        """M6 — TENANT."""
        return q.filter(model.company_id == company_id) if company_id is not None else q

    untagged_expenses = float(_sp_scope(db.query(func.sum(_ET2.amount)).filter(
        _ET2.date >= _s, _ET2.date < _e,
        _ET2.production_type.is_(None),
        _ET2.category.notin_(["arenda", "elektr", "tushlik", "soliqlar"])
    ), _ET2).scalar() or 0)

    # Yo'nalish ANIQ belgilangan xarajatlar (masalan "Kutilmagan xarajat —
    # Gips" deb belgilangan) — bular TAXMIN qilinmaydi, to'g'ridan-to'g'ri
    # o'sha turga qo'shiladi (Transport ham shu jumladan)
    from models import TransportExpense as _TE2
    gips_tagged_expense = float(_sp_scope(db.query(func.sum(_ET2.amount)).filter(
        _ET2.date >= _s, _ET2.date < _e, _ET2.production_type == 'gips'
    ), _ET2).scalar() or 0) + float(_sp_scope(db.query(func.sum(_TE2.amount)).filter(
        _TE2.expense_date >= _s, _TE2.expense_date < _e, _TE2.production_type == 'gips'
    ), _TE2).scalar() or 0)
    peno_tagged_expense = float(_sp_scope(db.query(func.sum(_ET2.amount)).filter(
        _ET2.date >= _s, _ET2.date < _e, _ET2.production_type == 'penoplast'
    ), _ET2).scalar() or 0) + float(_sp_scope(db.query(func.sum(_TE2.amount)).filter(
        _TE2.expense_date >= _s, _TE2.expense_date < _e, _TE2.production_type == 'penoplast'
    ), _TE2).scalar() or 0)
    umumiy_overhead += untagged_expenses

    ehson_xarajat = float(full.get("ehson_xarajat", 0) or 0)

    # BRAK — endi TAXMINIY emas, ANIQ ajratiladi:
    # 1) Xomashyo braki — get_brak_material_summary() ombordagi materialning
    #    o'z kategoriyasidan (Gips yoki boshqa) aniq bilinadi.
    from datetime import datetime as _dt3
    import crud as _crud_brak2
    _bs = _dt3(year, month, 1)
    _be = _dt3(year + 1, 1, 1) if month == 12 else _dt3(year, month + 1, 1)
    _brak_mat = _crud_brak2.get_brak_material_summary(db, start_date=_bs, end_date=_be,
                                                      company_id=company_id)
    gips_brak = float(_brak_mat.get("gips_brak_value", 0))
    peno_brak = float(_brak_mat.get("penoplast_brak_value", 0))

    # 2) Tayyor mahsulot braki (finished.html'dagi "Kamaytirish") — bu
    #    jadvalning o'zida category maydoni bor, to'g'ridan-to'g'ri ajratamiz.
    #    MUHIM: "ishlab chiqarish braki" yozuvlari bu yerga KIRMAYDI — ularning
    #    xomashyo tan narxi yuqorida _brak_mat (get_brak_material_summary,
    #    InventoryMovement asosida) orqali ALLAQACHON hisoblangan; bu yerda
    #    ham qo'shilsa, IKKI MARTA hisoblangan bo'lardi (get_monthly_report
    #    dagi bir xil tuzatishga qarang).
    from models import FinishedProductLoss as _FPL2
    # kech57 (40-band): belgi — YAGONA manba `crud._ISH_BRAK_BELGI`.
    import crud as _crud_belgi2
    _PROD_BRAK_MARKER2 = _crud_belgi2._ISH_BRAK_BELGI
    _fplq2 = db.query(_FPL2).filter(
        extract('year', _FPL2.lost_at) == year,
        extract('month', _FPL2.lost_at) == month
    )
    if company_id is not None:      # M6
        _fplq2 = _fplq2.filter(_FPL2.company_id == company_id)
    _fp_losses = _fplq2.all()
    for l in _fp_losses:
        if (l.reason or '').startswith(_PROD_BRAK_MARKER2):
            continue
        amt = float(l.cost_amount or 0)
        if (l.category or '').lower() == 'gips':
            gips_brak += amt
        else:
            peno_brak += amt

    gips_direct_cost += gips_tagged_expense
    peno_direct_cost += peno_tagged_expense

    umumiy_split_base = umumiy_overhead + ehson_xarajat
    gips_overhead_only = umumiy_split_base * gips_share
    peno_overhead_only = umumiy_split_base * peno_share
    gips_overhead = gips_overhead_only + gips_brak
    peno_overhead = peno_overhead_only + peno_brak

    # ── 4. YAKUNIY HISOB ──
    gips_xarajat_jami = gips_direct_cost + gips_emp + gips_overhead
    peno_xarajat_jami = peno_direct_cost + peno_emp + peno_overhead
    gips_foyda = gips_daromad - gips_xarajat_jami
    peno_foyda = peno_daromad - peno_xarajat_jami

    return {
        "year": year, "month": month,
        "gips": {
            "daromad": round(gips_daromad),
            "xomashyo_xarajati": round(gips_direct_cost),
            "hodim_xarajati": round(gips_emp),
            "brak_xarajati": round(gips_brak),
            "umumiy_xarajat_ulushi": round(gips_overhead_only),
            "jami_xarajat": round(gips_xarajat_jami),
            "sof_foyda": round(gips_foyda),
            "foyda_foiz": round((gips_foyda / gips_daromad * 100) if gips_daromad > 0 else 0, 1),
        },
        "penoplast": {
            "daromad": round(peno_daromad),
            "xomashyo_xarajati": round(peno_direct_cost),
            "hodim_xarajati": round(peno_emp),
            "brak_xarajati": round(peno_brak),
            "umumiy_xarajat_ulushi": round(peno_overhead_only),
            "jami_xarajat": round(peno_xarajat_jami),
            "sof_foyda": round(peno_foyda),
            "foyda_foiz": round((peno_foyda / peno_daromad * 100) if peno_daromad > 0 else 0, 1),
        },
        "daromad_ulushi": {"gips_foiz": round(gips_share * 100, 1), "penoplast_foiz": round(peno_share * 100, 1)},
        "umumiy_taqsimlangan": round(umumiy_split_base),
    }


def get_cash_balance(db: Session, company_id: int = None) -> dict:
    """Kassa balansi — kompaniyada HOZIR haqiqatda qancha naqd pul bor.

    ➕ Kirim: mijozlardan kelgan barcha to'lovlar
    ➖ Chiqim: naqd to'langan xomashyo xaridi, yetkazib beruvchiga to'lovlar,
       oylik xarajatlar, transport, xodim avanslari
    ➕/➖ Qo'lda: boshlang'ich balans, "Usta KPI to'landi", "Ehson to'landi"
       (bular — FAQAT admin aniq belgilaganda hisoblanadi, oy oxirida
       o'zi avtomatik chiqib ketmaydi)."""
    from models import (Payment, InventoryPurchase, SupplierPayment, MonthlyExpense,
                         ExpenseTransaction, TransportExpense, EmployeeAdvance, CashTransaction,
                         FinishedProductSale)
    from sqlalchemy import func

    # M6 (2026-09-18) — TENANT: kassaning HAR BIR yig'indisi joriy korxona
    # bilan cheklanadi. `Payment`/`SupplierPayment`/`InventoryPurchase`da
    # company_id ustuni yo'q — ular ota (Order/Supplier/Inventory) orqali
    # cheklanadi; qolganlarida ustunning o'zi bor.
    from models import Order as _Ord_cash, Supplier as _Sup_cash, Inventory as _Inv_cash

    _pq = db.query(func.sum(Payment.amount))
    if company_id is not None:
        _pq = _pq.join(_Ord_cash, _Ord_cash.id == Payment.order_id).filter(
            _Ord_cash.company_id == company_id)
    kirim_tolov = float(_pq.scalar() or 0)

    # MUHIM: Tayyor mahsulotni to'g'ridan-to'g'ri (buyurtmasiz) sotishdan
    # kelgan pul ham kassa KIRIMI — avval bu umuman hisobga olinmasdi,
    # shuning uchun sotuvdan tushgan pul Moliyada ko'rinmasdi.
    _fsq = db.query(func.sum(FinishedProductSale.total_amount))
    if company_id is not None:
        _fsq = _fsq.filter(FinishedProductSale.company_id == company_id)
    kirim_tayyor_sotuv = float(_fsq.scalar() or 0)

    _ipq = db.query(func.sum(InventoryPurchase.total_amount)).filter(
        InventoryPurchase.is_credit == False,
        InventoryPurchase.is_opening_stock.isnot(True)
    )
    if company_id is not None:
        _ipq = _ipq.join(_Inv_cash, _Inv_cash.id == InventoryPurchase.inventory_id).filter(
            _Inv_cash.company_id == company_id)
    chiqim_xomashyo_naqd = float(_ipq.scalar() or 0)

    _spq = db.query(func.sum(SupplierPayment.amount))
    if company_id is not None:
        _spq = _spq.join(_Sup_cash, _Sup_cash.id == SupplierPayment.supplier_id).filter(
            _Sup_cash.company_id == company_id)
    chiqim_yetkazib_beruvchi = float(_spq.scalar() or 0)

    _meq = db.query(MonthlyExpense)
    if company_id is not None:
        _meq = _meq.filter(MonthlyExpense.company_id == company_id)
    me_rows = _meq.all()
    chiqim_oylik = sum(
        float(m.arenda or 0) + float(m.elektr or 0) + float(m.tushlik or 0) + float(m.soliqlar or 0)
        for m in me_rows
    )
    _etq = db.query(func.sum(ExpenseTransaction.amount))
    if company_id is not None:
        _etq = _etq.filter(ExpenseTransaction.company_id == company_id)
    chiqim_qoshimcha = float(_etq.scalar() or 0)

    _teq = db.query(func.sum(TransportExpense.amount))
    if company_id is not None:
        _teq = _teq.filter(TransportExpense.company_id == company_id)
    chiqim_transport = float(_teq.scalar() or 0)
    # M5 — avans yig'indisi: `EmployeeAdvance`da company_id ustuni yo'q,
    # tenant otasi (Employee) orqali cheklanadi.
    _avq = db.query(func.sum(EmployeeAdvance.amount))
    if company_id is not None:
        from models import Employee as _Emp_cash
        _avq = _avq.join(_Emp_cash, _Emp_cash.id == EmployeeAdvance.employee_id
                         ).filter(_Emp_cash.company_id == company_id)
    chiqim_avans = float(_avq.scalar() or 0)

    _ctq = db.query(func.sum(CashTransaction.amount))
    if company_id is not None:
        _ctq = _ctq.filter(CashTransaction.company_id == company_id)
    qolda_jami = float(_ctq.scalar() or 0)

    jami_kirim = kirim_tolov + kirim_tayyor_sotuv
    jami_chiqim = (chiqim_xomashyo_naqd + chiqim_yetkazib_beruvchi + chiqim_oylik +
                   chiqim_qoshimcha + chiqim_transport + chiqim_avans)

    balance = jami_kirim - jami_chiqim + qolda_jami

    return {
        "balance": round(balance),
        "kirim_tolov": round(kirim_tolov),
        "kirim_tayyor_sotuv": round(kirim_tayyor_sotuv),
        "chiqim_xomashyo_naqd": round(chiqim_xomashyo_naqd),
        "chiqim_yetkazib_beruvchi": round(chiqim_yetkazib_beruvchi),
        "chiqim_oylik": round(chiqim_oylik),
        "chiqim_qoshimcha": round(chiqim_qoshimcha),
        "chiqim_transport": round(chiqim_transport),
        "chiqim_avans": round(chiqim_avans),
        "qolda_jami": round(qolda_jami),
    }


def get_purchase_stats_for_period(db: Session, year: int, month: int,
                                 company_id: int = None) -> dict:
    """Berilgan oy uchun xomashyo xaridi statistikasi.
    MUHIM: "boshlang'ich (mavjud) ombor" sifatida belgilangan kirimlar
    bu yerga KIRMAYDI — chunki ular yangi xarid emas, tizimni ishlata
    boshlaganda mavjud xomashyoni hisobga olish uchun (bir martalik
    kiritish). Aks holda, "shu oy xarajati" noto'g'ri, shishirilgan
    chiqib qolar edi."""
    from models import InventoryPurchase, Inventory as _Inv_ps
    from datetime import datetime as dt

    start = dt(year, month, 1)
    end = dt(year + 1, 1, 1) if month == 12 else dt(year, month + 1, 1)

    # M6 — TENANT: `InventoryPurchase`da company_id yo'q, ota (material) orqali.
    _pq = db.query(InventoryPurchase).filter(
        InventoryPurchase.purchased_at >= start,
        InventoryPurchase.purchased_at < end,
        InventoryPurchase.is_opening_stock.isnot(True)
    )
    if company_id is not None:
        _pq = _pq.join(_Inv_ps, _Inv_ps.id == InventoryPurchase.inventory_id).filter(
            _Inv_ps.company_id == company_id)
    purchases = _pq.all()

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


def get_transport_stats_for_period(db: Session, year: int, month: int,
                                  company_id: int = None) -> dict:
    """Berilgan oy uchun transport xarajatlari."""
    from models import TransportExpense, Delivery, Order as _Ord_tp
    from datetime import datetime as dt

    start = dt(year, month, 1)
    end = dt(year + 1, 1, 1) if month == 12 else dt(year, month + 1, 1)

    _iq = db.query(TransportExpense).filter(
        TransportExpense.expense_date >= start,
        TransportExpense.expense_date < end
    )
    if company_id is not None:      # M6
        _iq = _iq.filter(TransportExpense.company_id == company_id)
    inbound = _iq.all()
    inbound_total = sum(float(e.amount) for e in inbound)

    _dq = db.query(Delivery).filter(
        Delivery.delivered_at >= start,
        Delivery.delivered_at < end,
        Delivery.transport_cost > 0
    )
    if company_id is not None:      # M6: ota (buyurtma) orqali
        _dq = _dq.join(_Ord_tp, _Ord_tp.id == Delivery.order_id).filter(
            _Ord_tp.company_id == company_id)
    deliveries = _dq.all()
    outbound_company = sum(d.company_transport_cost for d in deliveries)

    return {
        "inbound_total": round(inbound_total),
        "outbound_company": round(outbound_company),
    }


def save_monthly_expense(db: Session, year: int, month: int, data: dict,
                        performed_by: Optional[str] = None, company_id: int = None):
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

    # M6 (2026-09-18) — TENANT: qator (year, month) bo'yicha GLOBAL
    # qidirilardi. Ikki korxonali bazada bu — o'qish sizishi emas,
    # MA'LUMOT BUZILISHI edi: A "Saqlash" bosganda B korxonaning
    # arenda/elektr/soliq qatorini o'chirib yozib yuborardi (lokal
    # sinovda aniq ko'rsatilgan). Endi qidiruv ham, yangi qator ham
    # korxona bilan bog'langan.
    _meq = db.query(MonthlyExpense).filter(
        MonthlyExpense.year  == year,
        MonthlyExpense.month == month
    )
    if company_id is not None:
        _meq = _meq.filter(MonthlyExpense.company_id == company_id)
    expense = _meq.first()

    if not expense:
        expense = MonthlyExpense(company_id=company_id, year=year, month=month)
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
            # M6 — TENANT: bu yerdagi O'CHIRISH ham, YARATISH ham korxona
            # bilan bog'lanadi. Aks holda A "Saqlash" bosganda B ning
            # 'monthly_form' tranzaksiyalari o'chib ketardi, yangisi esa
            # DEFAULT 1 ga yozilardi.
            _delq = db.query(ExpenseTransaction).filter(
                extract('year', ExpenseTransaction.date) == year,
                extract('month', ExpenseTransaction.date) == month,
                ExpenseTransaction.category == cat,
                ExpenseTransaction.source == "monthly_form"
            )
            if company_id is not None:
                _delq = _delq.filter(ExpenseTransaction.company_id == company_id)
            _delq.delete(synchronize_session=False)
            if amount > 0:
                db.add(ExpenseTransaction(
                    company_id=company_id,
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
def get_penoplast_list(db: Session, company_id: int = None):
    """Korxonaning penoplast (plotnost) turlari.

    2026-09-21 — TENANT (O'LCHANGAN): filtr umuman yo'q edi — B korxona
    `/api/penoplasts`, `/orders`, `/finished` da A ning penoplastlarini
    (nomi, qoldig'i, narxi) ko'rardi. Korxona noma'lum bo'lsa — bo'sh
    ro'yxat (begona ro'yxatdan xavfsizroq)."""
    from models import Inventory
    from sqlalchemy import or_
    if company_id is None:
        return []
    try:
        items = db.query(Inventory).filter(
            Inventory.company_id == company_id,
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
            Inventory.company_id == company_id,
            Inventory.item_name.ilike("%penoplast%")
        ).all()


def get_default_penoplast(db: Session, company_id: int = None):
    """Asosiy plotnost.

    M6 — TENANT: company_id berilsa, standart penoplast FAQAT shu
    korxona omboridan tanlanadi (aks holda A ning hisobida B ning
    materiali ishlatilib qolishi mumkin edi)."""
    from models import Inventory

    # 2026-09-21 — O'LCHANGAN: 6 ta chaqiruvchi `company_id` bermasdi va
    # bu yerda butun bazadagi BIRINCHI asosiy penoplast qaytardi — ya'ni
    # odatda A niki. B ning penoplast tanlanmagan buyurtmasi A ning
    # penoplastiga bog'lanib, 409 bilan rad etilardi (filtr o'chiq). Endi
    # (loy retsepti bilan bir xil qoida) korxona noma'lum bo'lsa zaxira yo'li
    # UMUMAN ishlamaydi: penoplastsiz qolish begona penoplastdan xavfsizroq.
    if company_id is None:
        return None

    def _scoped(q):
        return q.filter(Inventory.company_id == company_id)

    p = _scoped(db.query(Inventory).filter(
        Inventory.is_penoplast == True,
        Inventory.is_default_penoplast == True,
        Inventory.is_deleted.isnot(True)
    )).first()
    if p:
        return p
    # kech37 (18-band): zaxira tanlovi BARQAROR — eng kichik id (15-band saboqi:
    # PG da tartibsiz `.first()` UPDATE dan keyin boshqa qatorni qaytarishi mumkin)
    p = _scoped(db.query(Inventory).filter(
        Inventory.is_penoplast == True, Inventory.is_deleted.isnot(True))).order_by(Inventory.id).first()
    if p:
        return p
    return _scoped(db.query(Inventory).filter(
        Inventory.item_name.ilike("%penoplast%"), Inventory.is_deleted.isnot(True)
    )).first()


def _sub_detail_field(sub, name, default=None):
    """OrderItemSubDetail ORM obyekti yoki dict — ikkalasidan ham bir xil
    tarzda maydon o'qish uchun kichik yordamchi."""
    if isinstance(sub, dict):
        return sub.get(name, default)
    return getattr(sub, name, default)


def _calc_dim_volume_price(category, width, thickness, length, quantity, base_price, is_coated=False):
    """Profil/Panel formulasi bilan hajm (m³) va narxni hisoblaydi.
    Frontend (orders.html calculateItem()) dagi FORMULA BILAN AYNAN BIR
    XIL bo'lishi SHART — aks holda hajm/narx serverda boshqacha chiqadi.
    Asosiy detal ham, ICHKI QO'SHIMCHA detal ham shu bitta formuladan
    foydalanadi (ikkalasi ham bir xil xomashyodan)."""
    cat = (category or '').lower()
    w = float(width or 0)
    t = float(thickness or 0)
    l = float(length or 0)
    q = float(quantity or 1)
    bp = float(base_price or 0)

    if cat == 'profil':
        eni_m, keng_m = w / 100, t / 100
        volume = (eni_m * keng_m * l) / 2
        per_meter = (eni_m * keng_m * bp) / 2
        price = per_meter * l
    elif cat == 'panel':
        eni_m, qalin_m = w / 100, t / 100
        volume = eni_m * qalin_m * q
        per_dona = eni_m * qalin_m * bp
        price = per_dona * q
    else:
        return 0.0, 0.0

    if is_coated:
        price *= 2

    return volume, price


def _sub_details_volume_m3(item) -> float:
    """Bitta OrderItemning ICHKI QO'SHIMCHA detallari (bor bo'lsa) —
    jami hajmini (m³) qaytaradi. Har biri O'Z turi (profil/panel)
    formulasi bilan, lekin PARENT bilan bir xil xomashyo hisobiga."""
    total = 0.0
    for sub in (getattr(item, 'sub_details', None) or []):
        vol, _ = _calc_dim_volume_price(
            _sub_detail_field(sub, 'category', 'profil'),
            _sub_detail_field(sub, 'width'),
            _sub_detail_field(sub, 'thickness'),
            _sub_detail_field(sub, 'length'),
            _sub_detail_field(sub, 'quantity'),
            base_price=0,  # bu yerda faqat HAJM kerak, narx emas
        )
        total += vol
    return total


def _item_volume_m3(db, item, default_penoplast=None, penoplast_narxi=None) -> float:
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
        vol = 0.0
        if item.width and item.thickness and item.length:
            vol = (item.width/100) * (item.thickness/100) / 2 * float(item.length)
        # Ichki qo'shimcha detallar (masalan karniz ichidagi rebristo
        # qism) — bor bo'lsa, hajmiga QO'SHILADI (bir xil xomashyodan,
        # shuning uchun ombordan yechishda ALOHIDA hisoblanmaydi).
        vol += _sub_details_volume_m3(item)
        return vol
    elif cat == 'panel':
        if item.width and item.thickness:
            return (item.width/100) * (item.thickness/100) * qty
    elif cat == 'dona':
        # YANGI (2026-08): agar Kenglik+Qalinlik+"metr ekvivalenti"
        # (length maydonida, "Blok" turkumidagi kabi) saqlangan bo'lsa —
        # PROFIL formulasidan foydalanamiz (aniq, "1 metrdan necha dona
        # chiqadi" asosida hisoblangan). Bu — eskidan MUSTAQIL, YANGI yo'l.
        if item.width and item.thickness and item.length:
            return (item.width/100) * (item.thickness/100) / 2 * float(item.length)

        # ESKI (orqaga moslik): narx-nisbat usuli — yangi maydonlar
        # bo'lmagan, eski yozuvlar uchun, o'zgarishsiz qoladi.
        # MUHIM: agar "qulflangan" (unit_price_for_volume) qiymat saqlangan
        # bo'lsa — o'shani ishlatamiz (sotuv narxi keyinroq o'zgargan bo'lsa
        # ham, haqiqiy hajm o'zgarmasligi uchun). Eski yozuvlarda bu maydon
        # bo'lmasa — orqaga moslik uchun unit_price'ning o'zidan olamiz.
        unit_price = float(getattr(item, 'unit_price_for_volume', None) or item.unit_price or 0)
        if unit_price <= 0:
            return 0.0

        # 1 m³ sotuv narxi — detalda saqlangan bo'lsa shuni olamiz
        price_m3 = float(getattr(item, 'price_per_m3', None) or 0)

        # QO'SHILDI 2026-09-20. Detalda o'z "1 m³ narxi" maydoni bo'sh bo'lsa,
        # brauzer hisoblashda buyurtmaning "Asosiy narx"idan foydalangan
        # (orders.html: `effM3 = m3price || base_price`), lekin uni detalga
        # SAQLAMAGAN. Shuning uchun bu yerda ham avval o'sha asosiy narxga
        # murojaat qilamiz. Aks holda pastdagi TAN narxga tushib ketardik va
        # hajm sotuv/tan nisbatiga shishib qolardi — bu "hajmni qulflab
        # narxni oshirish" holatida o'lcham maydonlari tozalangan bo'lsa
        # jonli o'lchovda 74.5% farq bergan edi.
        if price_m3 <= 0:
            _ord = getattr(item, 'order', None)
            _bp = getattr(_ord, 'base_price', None) if _ord is not None else None
            if _bp:
                price_m3 = float(_bp)

        # Bo'lmasa — buyurtmadagi boshqa detallardan, oxirida penoplast tan narxidan
        if price_m3 <= 0:
            pid = getattr(item, 'penoplast_id', None)
            p = db.query(Inventory).filter(Inventory.id == pid).first() if pid else default_penoplast
            # kech48 (K47-1, 5-bo'lim 32-band): `penoplast_narxi` — foyda hisobi
            # (`calculate_order_profit`) shu buyurtmaning MUZLATILGAN 1 blok
            # narxini beradi. Bu zaxira yo'lda hajm = summa ÷ narx, tan narx esa
            # hajm × narx — ikkalasi BIR narxdan bo'lmasa (hajm joriy, narx
            # muzlatilgan) tan narx joriy narx bilan suzardi. Boshqa
            # chaqiruvchilar (ombordan yechish, tahrir farqi) bermaydi — xulq
            # o'zgarmaydi.
            _pn = penoplast_narxi if penoplast_narxi is not None else (p.price_per_unit if p else None)
            if p and _pn and p.volume_per_unit:
                # Tan narxi: blok narxi ÷ blok hajmi = 1 m³ tan narxi
                price_m3 = float(_pn) / float(p.volume_per_unit)

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


def _peno_of(db, pid, company_id=None, lock=False):
    """Penoplast pozitsiyasi — FAQAT shu korxona omboridan (2026-09-21).

    `pid` detalning o'z havolasi yoki korxonaning asosiy penoplasti. Korxona
    ma'lum bo'lsa, so'rov unga cheklanadi: begona pozitsiya topilmaydi va
    hech qachon ayirilmaydi/qaytarilmaydi."""
    from models import Inventory
    if not pid:
        return None
    q = db.query(Inventory).filter(Inventory.id == pid)
    if company_id is not None:
        q = q.filter(Inventory.company_id == company_id)
    if lock:
        q = q.with_for_update()
    return q.first()


def _company_of_items(items):
    """Detallar ro'yxatidan korxona (ORM detallarida `company_id` bor)."""
    for it in items or []:
        cid = getattr(it, 'company_id', None)
        if cid:
            return cid
    return None


def _group_volumes_by_penoplast(db, items, company_id=None) -> dict:
    """Detallarni plotnost bo'yicha guruhlaydi.
    Qaytaradi: {penoplast_id: total_volume_m3}
    MUHIM: "Tayyor mahsulotdan" tanlangan detallar (finished_product_id
    bor) — BU YERGA QO'SHILMAYDI, chunki ularning xomashyosi ALLAQACHON,
    o'sha mahsulot birinchi marta ishlab chiqarilganda ayirilgan edi.
    Agar shu yerda ham hisoblasak — IKKI MARTA ayirilgan bo'lardi."""
    if company_id is None:
        company_id = _company_of_items(items)
    default_p = get_default_penoplast(db, company_id=company_id)
    default_id = default_p.id if default_p else None

    volumes = {}
    for item in items:
        if getattr(item, 'finished_product_id', None):
            continue
        vol = _item_volume_m3(db, item, default_p)
        if vol <= 0:
            continue
        pid = getattr(item, 'penoplast_id', None) or default_id
        if not pid:
            continue
        volumes[pid] = volumes.get(pid, 0.0) + vol
    return volumes


def check_inventory_for_order(db: Session, order_data, company_id: int = None) -> dict:
    """
    Buyurtma uchun xomashyo yetishini tekshiradi.
    Har detal o'z plotnostidan hisoblanadi.
    company_id — `order_data` sxema (OrderCreate) bo'lsa, unda korxona
    yo'q, shuning uchun chaqiruvchi aniq beradi; ORM buyurtmada o'zidan.
    """
    cid = company_id if company_id is not None else getattr(order_data, 'company_id', None)
    shortages = []
    volumes = _group_volumes_by_penoplast(db, order_data.items, company_id=cid)
    total_volume_m3 = sum(volumes.values())

    if not volumes:
        return {"enough": True, "shortages": [], "total_volume_m3": 0}

    for pid, vol in volumes.items():
        p = _peno_of(db, pid, cid)
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
    import crud as _crud_lm

    log = []
    cid = getattr(order, 'company_id', None)
    volumes = _group_volumes_by_penoplast(db, order.items, company_id=cid)

    for pid, vol in volumes.items():
        p = _peno_of(db, pid, cid, lock=True)
        if not p:
            continue
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks_needed = vol / vol_per_unit
        # MUHIM: 0 ga cheklamaymiz — agar admin "yetishmasa ham davom et"
        # deb tasdiqlagan bo'lsa, ombor MANFIY ko'rsatishi kerak (haqiqiy
        # tanqislik miqdorini yashirmaslik uchun — bu ataylab qilingan).
        p.stock_quantity = float(p.stock_quantity) - blocks_needed
        log.append(f"{p.item_name}: -{blocks_needed:.2f} blok")
        # MUHIM: avval bu yerda "Ombor harakatlari" jurnaliga UMUMAN
        # yozilmasdi — faqat vaqtinchalik xabar uchun ishlatilardi. Endi
        # boshqa materiallar (Gips, Bazalt va h.k.) bilan bir xilda, haqiqiy
        # jurnalga ham yoziladi.
        try:
            _crud_lm.log_movement(db, p.id, p.item_name, movement_type="out",
                                   quantity=blocks_needed, unit="blok",
                                   order_id=getattr(order, 'id', None),
                                   reason=f"Buyurtma {getattr(order, 'order_number', '')} — Penoplast")
        except Exception:
            pass

    if volumes:
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

        # Ichki qo'shimcha detallar — ular ham xuddi shu "qolgan qism"
        # ulushida (fraction) qaytishi/qayta yechilishi kerak (parent
        # bilan bir xil xomashyodan bo'lgani uchun, alohida topshirish
        # ulushi kuzatilmaydi — parentnikiga qarab proratsiya qilinadi).
        self.sub_details = []
        for sub in (getattr(real_item, 'sub_details', None) or []):
            scat = (sub.category or 'profil').lower()
            sd = {"category": sub.category, "width": sub.width, "thickness": sub.thickness}
            if scat == 'profil':
                sd["length"] = float(sub.length or 0) * fraction
                sd["quantity"] = float(sub.quantity or 1)
            else:
                sd["length"] = sub.length
                sd["quantity"] = float(sub.quantity or 0) * fraction
            self.sub_details.append(sd)


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
        # kech60 (57-band): omborga qo'yilgan ortiqcha qism ham buyurtmadan chiqqan
        # (`OrderItem.remaining_qty`) — uning xomashyosi IKKINCHI marta qaytmaydi.
        remaining = item.remaining_qty
        if remaining <= 0.001:
            continue  # To'liq topshirilgan / omborga qo'yilgan — qaytariladigan narsa yo'q
        fraction = remaining / ordered
        result.append((item, fraction, remaining, ordered))
    return result


def buyurtmadan_qisman_chiqqan(order) -> bool:
    """kech60 (57-band, K59-3): buyurtmadan biror qism allaqachon CHIQQANMI — mijozga
    topshirilgan YOKI ortiqcha sifatida omborga qo'yilgan. Shunda o'chirish / tiklash
    xomashyoni faqat QOLGAN qism uchun qaytaradi / qayta yechadi
    (`return_inventory_for_order_partial`, loy — `loy_relevant_remaining_fraction`).
    Ikkalasi ham yo'q bo'lsa — avvalgidek butun buyurtma (`return_inventory_for_order`)."""
    if order.deliveries:
        return True
    return any(it.ortiqcha_qty > 0.001 for it in (order.items or []))


def return_inventory_for_order_partial(db: Session, order, sign: float = 1.0) -> list:
    """Qisman topshirilgan buyurtma bekor qilinganda/o'chirilganda —
    FAQAT hali topshirilmagan (mijozga berilmagan) qismi uchun xomashyoni
    omborga qaytaradi. Topshirib bo'lingan qism — mijozda, qaytmaydi.
    sign=-1.0 — buyurtma tiklanganda qayta ombordan yechish uchun."""

    log = []
    undelivered = get_undelivered_items(order)
    if not undelivered:
        return log

    prorated_items = [_ProratedItem(item, fraction) for item, fraction, _, _ in undelivered]
    verb = "qaytarildi" if sign > 0 else "qayta yechildi"

    # 1) Penoplast — qolgan qism bo'yicha
    cid = getattr(order, 'company_id', None)
    volumes = _group_volumes_by_penoplast(db, prorated_items, company_id=cid)
    for pid, vol in volumes.items():
        p = _peno_of(db, pid, cid, lock=True)
        if not p:
            continue
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks = (vol / vol_per_unit) * sign
        p.stock_quantity = float(p.stock_quantity) + blocks
        log.append(f"{p.item_name}: {blocks:+.2f} blok {verb} (qolgan qism)")

    return log


def return_inventory_for_order(db: Session, order, sign: float = 1.0) -> list:
    """
    Buyurtma o'chirilganda omborga xomashyo qaytaradi.
    Har detal o'z plotnostiga qaytariladi.
    sign=1.0 — qaytarish (standart). sign=-1.0 — teskarisi, ya'ni
    buyurtma TIKLANGANDA xuddi shu miqdorni qayta ombordan yechish uchun.
    """

    log = []
    cid = getattr(order, 'company_id', None)
    volumes = _group_volumes_by_penoplast(db, order.items, company_id=cid)

    for pid, vol in volumes.items():
        p = _peno_of(db, pid, cid, lock=True)
        if not p:
            continue
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks = (vol / vol_per_unit) * sign
        p.stock_quantity = float(p.stock_quantity) + blocks
        verb = "qaytarildi" if sign > 0 else "qayta yechildi"
        log.append(f"{p.item_name}: {blocks:+.2f} blok {verb}")

    if volumes:
        db.commit()
    return log


# ============================================================
# TAYYOR LOY ZAXIRASI
# ============================================================

def _get_planned_loy(order) -> float:
    """Buyurtma yaratilganda rejalashtirilgan loy miqdorini oladi.
    MUHIM: endi ALOHIDA, ishonchli ustundan (order.planned_loy_kg) o'qiladi —
    matn ichidan (notes) qidirish faqat shu tuzatishdan OLDIN yaratilgan
    ESKI buyurtmalar uchun zaxira (fallback) sifatida qoladi."""
    if getattr(order, 'planned_loy_kg', None) is not None:
        return float(order.planned_loy_kg)
    notes = order.notes or ''
    for part in notes.split(','):
        part = part.strip()
        if part.startswith('planned_loy='):
            try:
                return float(part.split('=')[1])
            except (ValueError, IndexError):
                pass
    return 0.0


def _remaining_fraction_for_items(items) -> float:
    """Berilgan detallar ro'yxati bo'yicha (ORDER-WIDE emas, faqat SHU
    detallar bo'yicha) QOLGAN (topshirilmagan) ulushni hisoblaydi —
    Order.delivery_percent bilan bir xil mantiq, lekin faqat kerakli
    detal to'plamiga cheklangan holda."""
    total_ordered = 0.0
    total_delivered = 0.0
    for it in items:
        ordered = it.order_qty_normalized
        if ordered <= 0:
            continue
        total_ordered += ordered
        # kech60 (57-band): omborga qo'yilgan ortiqcha qism ham chiqqan hisoblanadi
        total_delivered += min(it.delivered_qty + it.ortiqcha_qty, ordered)
    if total_ordered <= 0:
        return 1.0
    return max(0.0, 1 - total_delivered / total_ordered)


def loy_relevant_remaining_fraction(order) -> float:
    """Buyurtma o'chirilganda/tiklanganda LOY (qoplama) proporsional
    qaytarish/qayta yechish uchun QOLGAN ulush.

    MUHIM (2026-09 chuqur audit — ikkinchi bosqich): oldin bu yerda
    butun buyurtmaning ORDER-WIDE Order.delivery_percent'i ishlatilardi —
    lekin bu, buyurtmada LOY sarflamaydigan detallar (masalan "Tayyor
    mahsulotdan" olingan yoki qoplamasiz detallar) ham bo'lsa, juda
    noto'g'ri natija berishi mumkin edi. Masalan: 10 birlik qoplamali
    profil (loy kerak, hali topshirilmagan) + 990 birlik tayyor
    mahsulotdan detal (loy kerak emas, to'liq topshirilgan) — bunda
    order-wide delivery_percent ~99% chiqadi-yu, "qolgan 1%" loy
    qaytariladi, holbuki HAQIQATDA ~100% qaytishi kerak edi (chunki loy
    talab qiladigan yagona detal umuman topshirilmagan).

    Endi FAQAT haqiqatda LOY sarflaydigan detallar (qoplamali
    EMAS — uning loyi alohida tizim orqali hisoblanadi — va "Tayyor
    mahsulotdan" EMAS — uning xomashyosi ishlab chiqarishda allaqachon
    sarflangan) bo'yicha QOLGAN ulush hisoblanadi.

    kech62 (44-band, O'LCHANGAN — asl `25bcd8d`, SQLite va PG 16 AYNAN, `work/probe62.py`):
    bu ro'yxat MRP detalini (`mrp_product`) ham buyurtma loyini sarflovchi deb sanardi, holbuki
    MRP detali qoplamasi o'z BOM ining qoplama qatoridan yechiladi (11.0-band, ishlab chiqarishda
    avtomatik) — 41-band `_buyurtma_loyi_detalimi` ham uni chiqaradi. Natija: qoplamali profil 10 m
    (topshirilmagan) + qoplamali MRP 10 (to'liq topshirilgan), loy 30 kg — o'chirishda 15 kg qaytardi
    (to'g'risi 30), tiklashda 15 kg yechdi; aksi (profil topshirilgan, MRP yo'q) — 15 kg qaytardi
    (to'g'risi 0). Endi predikat YAGONA: qoplamali VA `_buyurtma_loyi_detalimi`."""
    items = [
        it for it in (order.items or [])
        if it.is_coated
        and _buyurtma_loyi_detalimi(it)
    ]
    if not items:
        return 1.0
    return _remaining_fraction_for_items(items)


def _set_planned_loy(order, kg: float) -> None:
    """Rejalashtirilgan loyni saqlaydi — endi to'g'ridan-to'g'ri, ishonchli
    ustunga (order.planned_loy_kg). Eski notes-belgisi ham, orqaga moslik
    uchun, parallel yozilib turadi (hozircha, keyinchalik olib tashlanishi
    mumkin)."""
    order.planned_loy_kg = kg
    notes = order.notes or ''
    parts = [p.strip() for p in notes.split(',') if p.strip() and not p.strip().startswith('planned_loy=')]
    parts.append(f'planned_loy={kg}')
    order.notes = ','.join(parts)


# ════════════════════════════════════════════════════════════════════
# kech58 (K58-1 / K58-2 / K58-3, 43-band) — BUYURTMA QOPLAMA RETSEPTI: YAGONA MANBA
# ════════════════════════════════════════════════════════════════════
# O'LCHANGAN (asl kod `e7dd594`, `work/probe58.py`, SQLite va HAQIQIY PG 16 — AYNAN):
#   K58-1: birinchi detal "Loy sotish" bo'lsa, buyurtmaning UMUMIY loyi tanlangan retseptdan
#          emas, "Loy sotish" retseptidan yechilardi (R1 5 200 / R2 20 000 so'm/kg: foydadagi
#          qoplama 52 000, to'g'risi 200 000). Brak summasi — birinchi QOPLAMALI detal
#          retseptidan, brak yechimi — detalning O'Z retseptidan: UCH xil manba (43-band).
#   K58-2: retsept "— Yo'q —" — loy korxonaning birinchi retseptidan yechilardi, lekin
#          foydada qoplama xarajati UMUMAN yo'q edi (jonli: buyurtma 185, 234 564.48 so'm).
#   K58-3: tahrirda retsept R1 -> R2 — ombor tegilmasdi, o'chirilganda loy R2 ga qaytardi
#          (R2 dan olinmagan 10 kg paydo bo'ldi, R1 ning 10 kg i qaytmadi).
# YECHIM (texnik — Claude): `orders.qoplama_retsept_id` — umumiy loy qaysi retseptdan yechilgan.
# FAQAT kech58 dan keyin YARATILGAN buyurtmaga yoziladi (FOYDALANUVCHI QARORI kech58:
# "Yo'q, faqat yangi buyurtmalar" — eski buyurtmalar foydasi o'zgarmaydi). Eski (NULL)
# buyurtma — avvalgi qoida AYNAN. Yechish, qaytarish, foyda, brak summasi va brak yechimi —
# hammasi `resolve_recipe(order=...)` / `buyurtma_qoplama_retsept_nomzodlari` orqali.

def _qoplama_retsept_nomzodlari_yangi(order) -> list:
    """YANGI buyurtma uchun qoplama retsepti nomzodlari (ustuvorlik tartibida, takrorsiz):
    1) buyurtma loyidan sarflaydigan QOPLAMALI detal (`_buyurtma_loyi_detalimi`);
    2) "Loy sotish" dan boshqa detal (UI buyurtma retseptini shu detallarga yozadi va
       tahrirda shu qoida bilan o'qiydi — `orders.html` `mainItem`);
    3) istalgan detal.
    Detallar `id` tartibida (PG da `ORDER BY` siz tartib UPDATE dan keyin o'zgarishi mumkin)."""
    items = list(getattr(order, 'items', None) or [])
    tartib = sorted(range(len(items)), key=lambda i: (getattr(items[i], 'id', None) is None,
                                                       getattr(items[i], 'id', None) or 0, i))
    items = [items[i] for i in tartib]

    def _tur(x):
        return (getattr(x, 'category', None) or '').lower()

    guruhlar = (
        [x for x in items if getattr(x, 'is_coated', False) and _buyurtma_loyi_detalimi(x)],
        [x for x in items if _tur(x) != 'loy_sotish'],
        items,
    )
    natija = []
    for g in guruhlar:
        for x in g:
            rid = getattr(x, 'recipe_id', None)
            if rid and rid not in natija:
                natija.append(rid)
    return natija


def buyurtma_qoplama_retsept_nomzodlari(order) -> list:
    """Buyurtma UMUMIY loyi retsepti nomzodlari — `resolve_recipe(order=...)` va foyda uchun.
    `qoplama_retsept_id` bor (kech58 dan keyin yaratilgan buyurtma) — avval u; so'ng (eski
    NULL buyurtmada — FAQAT) avvalgi qoida AYNAN: `order.items` tartibida `recipe_id` li detallar."""
    natija = []
    saqlangan = getattr(order, 'qoplama_retsept_id', None)
    if saqlangan:
        natija.append(saqlangan)
    for x in (getattr(order, 'items', None) or []):
        rid = getattr(x, 'recipe_id', None)
        if rid and rid not in natija:
            natija.append(rid)
    return natija


def buyurtma_qoplama_retseptini_tanla(db: Session, order, company_id: int = None):
    """YANGI qoida bo'yicha qoplama retsepti (korxona doirasida). Hech bir detalda retsept
    bo'lmasa — `resolve_recipe` zaxirasi (korxonaning birinchi retsepti): loy baribir shundan
    yechiladi, shuning uchun foyda ham shu retseptni ko'rishi SHART (K58-2)."""
    from models import Recipe
    cid = company_id if company_id is not None else getattr(order, 'company_id', None)
    q = db.query(Recipe)
    if cid is not None:
        q = q.filter(Recipe.company_id == cid)
    for rid in _qoplama_retsept_nomzodlari_yangi(order):
        r = q.filter(Recipe.id == rid).first()
        if r:
            return r
    if cid is None:
        return None
    return resolve_recipe(db, company_id=cid)


def resolve_recipe(db: Session, recipe_id: int = None, order=None,
                   company_id: int = None):
    """Retseptni HAR DOIM bitta korxona doirasida topadi — YAGONA manba.

    ⚠ 2026-09-21 — O'LCHANGAN SIZISH. Oldin retsept qidiruvi kamida
    5 joyda takrorlanardi va har birining oxirida `db.query(Recipe).first()`
    bor edi — BUTUN bazadagi birinchi retsept, ya'ni BOSHQA korxonaniki.

    Bu faqat o'qish sizishi emas edi: ingredientlar retseptning ichidan
    (`recipe.ingredients` → `ing.inventory_id`) olinadi, shuning uchun
    noto'g'ri retsept = noto'g'ri OMBOR. O'lchandi: retsepti yo'q YANGI
    korxona (B) loy ishlatganda A korxonaning omboridan xomashyo
    ayirildi (1000 → 995 → 992.5 kg).

    Shuning uchun ildiz shu yerda yopiladi: retsept to'g'ri korxonaniki
    bo'lsa — ombor ham avtomatik to'g'ri bo'ladi.

    Korxona qayerdan olinadi (tartib bilan):
      1) aniq berilgan `company_id`
      2) `order.company_id` (soxta buyurtma obyektlariga ham shu maydon
         qo'yilgan — pastdagi `_FakeOrder` larga qarang)
    Korxona ANIQLANMASA — "bazadagi birinchi retsept" zaxira yo'li
    ATAYLAB ishlatilmaydi. Retseptsiz qolish (hech narsa ayirilmaydi,
    jurnalga yoziladi) begona korxonaning retseptini jimgina
    ishlatishdan ko'ra xavfsizroq.
    """
    from models import Recipe

    cid = company_id
    if cid is None and order is not None:
        cid = getattr(order, 'company_id', None)

    q = db.query(Recipe)
    if cid is not None:
        q = q.filter(Recipe.company_id == cid)

    if recipe_id:
        r = q.filter(Recipe.id == recipe_id).first()
        if r:
            return r

    if order is not None:
        # kech58 (K58-1): buyurtmaning SAQLANGAN qoplama retsepti (yangi buyurtma), so'ng
        # avvalgi qoida AYNAN (eski buyurtma) — `buyurtma_qoplama_retsept_nomzodlari`.
        for rid in buyurtma_qoplama_retsept_nomzodlari(order):
            r = q.filter(Recipe.id == rid).first()
            if r:
                return r

    # Zaxira yo'l — FAQAT korxona aniq bo'lganda
    if cid is not None:
        return q.first()
    return None


def _get_order_recipe(db: Session, order, company_id: int = None):
    """Buyurtmaning retseptini topadi (korxona doirasida)."""
    return resolve_recipe(db, order=order, company_id=company_id)


def get_or_create_loy_stock(db: Session, recipe, company_id: int = None, commit: bool = True):
    """Retsept uchun 'Tayyor loy' ombor pozitsiyasini topadi yoki yaratadi.

    2026-09-18 — M8/F1a: qidiruv FAQAT `item_name` bo'yicha global edi va
    yangi pozitsiya `company_id` siz yaratilardi (vaqtinchalik `DEFAULT 1`
    ga tayanardi). Ya'ni B korxonaning buyurtmasi A korxonaning "Tayyor
    loy" zaxirasini topib, undan ayirib olishi mumkin edi.

    Korxona retseptning O'ZIDAN olinadi (`recipe.company_id`) — retsept
    esa chaqiruvchi tomonidan allaqachon tenant-tekshirilgan. Ataylab
    shunday: bu funksiya buyurtma oqimining ichidan, turli joylardan
    chaqiriladi va retsept har doim to'g'ri tenantni beradi.
    Biznes mantig'i (nom shakli, birlik, boshlang'ich qoldiq) O'ZGARMADI."""
    from models import Inventory

    if not recipe:
        return None

    cid = company_id if company_id is not None else getattr(recipe, "company_id", None)

    recipe_name = recipe.name.value if hasattr(recipe.name, 'value') else str(recipe.name)
    item_name = f"Tayyor loy ({recipe_name})"

    _q = db.query(Inventory).filter(Inventory.item_name == item_name)
    if cid is not None:
        _q = _q.filter(Inventory.company_id == cid)
    stock = _q.with_for_update().first()
    if stock:
        return stock

    stock = Inventory(
        company_id=cid,
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
    # kech63 (53-band): `commit=False` — chaqiruvchi qulf (101, buyurtma) ostida BITTA tranzaksiyada
    # ishlaydi (buyurtma tahriri); oraliq `commit` qulfni muddatidan OLDIN bo'shatardi.
    if commit:
        db.commit()
        db.refresh(stock)
    else:
        db.flush()
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


def take_loy_from_stock(db: Session, recipe, kg_needed: float, order=None, reason_override: str = None,
                        commit: bool = True):
    """Ombordagi tayyor loydan oladi.
    Qaytaradi: (olingan_kg, qolgan_ehtiyoj_kg, log_matni)
    kech63 (53-band): `commit=False` — faqat `flush` (chaqiruvchining tranzaksiyasi / qulfi saqlanadi)."""
    if kg_needed <= 0:
        return 0.0, 0.0, ""

    stock = get_or_create_loy_stock(db, recipe, commit=commit)
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
    if commit:
        db.commit()
    else:
        db.flush()
    msg = f"{stock.item_name}: -{taken:.1f} kg (zaxiradan)"
    print(f"✓ {msg}")
    return taken, kg_needed - taken, msg


# MUHIM (2026-09 — Fasa 3, brak-yozish konsolidatsiyasi): deduct_raw_material_
# for_finished_product_brak() shu yerda bo'lgan — yagona chaqiruvchisi
# crud.create_finished_product_brak() (Qaytarishlar sahifasi, "Ishlab
# chiqarishdan brak") olib tashlangani sabab, bu funksiya ham endi
# ishlatilmaydi va olib tashlandi. O'rniga: record_finished_product_
# production_brak() (crud.py) — Tayyor mahsulotlar sahifasi — ishlatiladi,
# u xuddi shu ishni (qo'shimcha xomashyoni ombordan ayirish, mahsulot
# soniga tegmasdan) qiladi, ammo ombor yetarliligini oldindan tekshiradi
# va InventoryMovement'ni izchil qayd etadi.


# ════════════════════════════════════════════════════════════════════
# kech54 (13-band, 41-band) — BRAK LOYI: buyurtma loyining detalga tushadigan ulushi
# ════════════════════════════════════════════════════════════════════
# O'LCHANGAN (asl kod `aecce02`, SQLite va HAQIQIY PG 16, `work/probe54.py`): buyurtmada
# loy BITTA umumiy son bo'lib kiritiladi ("Loy miqdori — barcha detallar uchun"), brakda
# esa u detallarga `order_qty_normalized` yig'indisi bo'yicha bo'linardi — metr (profil,
# panel) va dona bir xil birlik deb qo'shilardi (profil 10 m + panel 10 m + 100 dona, loy
# 30 kg: 100 dona loyning 25 kg ini "olardi"); maxrajga tayyor mahsulotdan olingan detal va
# MRP detali ham kirardi, holbuki bu buyurtma loyidan ular uchun sarf YO'Q (`_loy_remaining_
# fraction` ham ularni chiqaradi) — yangi profil braki 1 kg o'rniga 0.5 kg loy yechardi.
# FOYDALANUVCHI QARORI (kech54, tugma bilan): "Qoplama narxi ulushiga qarab (qimmat detal
# ko'proq)". Qoplama narxi — detal narxining qoplama uchun olingan qismi: penoplast
# detallarida qoplamali narx = qoplamasiz × QOPLAMA_NARX_KOEF (frontend `calculateItem`,
# `crud.create_order` izohi — narx YAKUNIY holda saqlanadi), ya'ni qoplama qismi =
# narx × (1 − 1 / KOEF). Ichki qo'shimcha detallar (`sub_details`) — o'z qoplama belgisi va
# narxi bilan (ota narxiga ALLAQACHON qo'shilgan, shuning uchun otadan ayiriladi).
# Hamma detal narxi 0 bo'lsa (narxsiz buyurtma) — eski usul (birlik soni), taxmin qilinmaydi.
QOPLAMA_NARX_KOEF = 2.0


def _buyurtma_loyi_kg(order) -> float:
    """Buyurtmaning loy miqdori (kg): haqiqiy → izohdagi `loy_kg=` → reja (avvalgidek)."""
    loy_kg = float(order.actual_loy_kg) if order.actual_loy_kg is not None else 0.0
    if loy_kg <= 0 and order.notes:
        import re as _re_loykg54
        m = _re_loykg54.search(r'loy_kg=([\d.]+)', str(order.notes))
        if m:
            try:
                loy_kg = float(m.group(1))
            except ValueError:
                pass
    if loy_kg <= 0:
        loy_kg = _get_planned_loy(order)
    return float(loy_kg or 0)


def _buyurtma_loyi_detalimi(oi) -> bool:
    """Detal buyurtmaning UMUMIY loyidan sarf qiladimi: tayyor mahsulotdan olingan
    (loyi ishlab chiqarishda sarflangan), "Loy sotish" (o'z retsepti bilan alohida
    yechiladi) va MRP detali (qoplamasi o'z BOM ining qoplama qatoridan) — YO'Q."""
    cat = (getattr(oi, 'category', None) or '').lower()
    if cat in ('loy_sotish', 'mrp_product'):
        return False
    return not getattr(oi, 'finished_product_id', None)


def _qoplama_narxi(oi) -> float:
    """Detal narxining QOPLAMA uchun olingan qismi (so'm) — 41-band qarori."""
    ulush = 1.0 - 1.0 / QOPLAMA_NARX_KOEF
    subs = list(getattr(oi, 'sub_details', None) or [])
    sub_jami = sum(max(0.0, float(getattr(s, 'total_price', 0) or 0)) for s in subs)
    asosiy = max(0.0, float(getattr(oi, 'total_price', 0) or 0) - sub_jami)
    q = asosiy * ulush if getattr(oi, 'is_coated', False) else 0.0
    for s in subs:
        if getattr(s, 'is_coated', False):
            q += max(0.0, float(getattr(s, 'total_price', 0) or 0)) * ulush
    return q


def _brak_loyi_birlikka(order, order_item) -> float:
    """Detalning 1 birligi (`order_qty_normalized` birligi) uchun buyurtma loyidan
    tushadigan kg. Brak yechimi (`deduct_raw_material_for_brak`) va brak summasi
    (`get_order_item_unit_cost`) SHU BITTA manbadan oladi."""
    if not order or not order_item or not getattr(order_item, 'is_coated', False):
        return 0.0
    if not _buyurtma_loyi_detalimi(order_item):
        return 0.0
    miqdor = float(order_item.order_qty_normalized or 0)
    if miqdor <= 0:
        return 0.0
    loy_kg = _buyurtma_loyi_kg(order)
    if loy_kg <= 0:
        return 0.0
    loy_detallari = [oi for oi in (order.items or []) if _buyurtma_loyi_detalimi(oi)]
    jami = sum(_qoplama_narxi(oi) for oi in loy_detallari)
    if jami > 0:
        return loy_kg * (_qoplama_narxi(order_item) / jami) / miqdor
    # Zaxira: buyurtmada narx yo'q — eski usul (qoplamali detallar birlik soni bo'yicha)
    birliklar = sum(float(oi.order_qty_normalized or 0) for oi in loy_detallari if oi.is_coated)
    return (loy_kg / birliklar) if birliklar > 0 else 0.0


# ════════════════════════════════════════════════════════════════════
# kech54 (13-band, 5-qadam) — MRP MAHSULOTI BRAKI: retsept SURATIDAN
# ════════════════════════════════════════════════════════════════════
# O'LCHANGAN (asl kod `aecce02`, SQLite va HAQIQIY PG 16, `work/probe55.py`): MRP detali
# (penoplast / loy retsepti yo'q) braki summasi 0 va xomashyo yechilmasdi; qoplamali MRP
# detalida esa BUYURTMA loyi retseptidan (MRP qoplamasi emas) yechilardi; "Ishlab
# chiqarishda chiqdi" (MRP tayyor mahsuloti) — 400 "xomashyo nisbati topilmadi".
# YECHIM (texnik — Claude): 1 birlik sarf — shu mahsulotni ishlab chiqargan (boshlangan
# yoki yakunlangan) ishlab chiqarish buyurtmasi(lar)ning `recipe_snapshot_json` idan,
# OMBOR birligida (`total_quantity_needed_stock_unit`, isrof foizi bilan), bir necha
# buyurtma bo'lsa — miqdor bo'yicha o'rtacha. Qadoq (`packaging`) qatorlari brakda
# sarflanmaydi (brak — ishlab chiqarish ichida, qadoqdan oldin). Qoplama qatorlari —
# faqat qoplama tortilgan bo'lsa (buyurtma braki: "loy tortilganmi"). Bekor qilingan
# / qoralama buyurtma hisobga olinmaydi. Surat yo'q (ishlab chiqarish boshlanmagan) — None.


def _mrp_eski_surat_qoplamalari(db, po) -> set:
    """`is_coating` kaliti bo'lmagan (kech54 dan oldingi) suratlar uchun: qoplama
    xomashyolari — buyurtmada TANLANGAN ixtiyoriy qatorlardan `is_coating` belgililari;
    ular BOM dan o'chib ketgan bo'lsa — shu BOM ning hozirgi qoplama qatorlari."""
    import json as _json_eq
    from production_models import BOMItem
    try:
        tanlangan = set(_json_eq.loads(po.selected_optional_bom_item_ids_json or "[]"))
    except Exception:
        tanlangan = set()
    bis = db.query(BOMItem).filter(BOMItem.bom_id == po.bom_id,
                                       BOMItem.company_id == po.company_id).all()
    inv = {bi.inventory_id for bi in bis
           if bi.id in tanlangan and bi.is_optional and getattr(bi, 'is_coating', False)}
    if inv:
        return inv
    return {bi.inventory_id for bi in bis if bi.is_optional and getattr(bi, 'is_coating', False)}


def _mrp_birlik_sarfi(db, company_id, order_item=None, finished_product=None,
                      qoplama: bool = True, surat_narxlari: dict = None):
    """MRP mahsulotining 1 birligi uchun xomashyo: {inventory_id: miqdor (ombor birligida)}.
    None — surati bor ishlab chiqarish buyurtmasi YO'Q (hali boshlanmagan).

    kech55 (34-band): `surat_narxlari` (lug'at) berilsa — har material uchun
    [miqdor, qiymat] yig'iladi, qiymat suratdagi `unit_price_at_time` (ishlab
    chiqarish paytidagi ombor birligi narxi) bilan; chaqiruvchi o'rtacha narxni
    oladi. Sarf (qaytadigan natija) va qatorlar tanlovi O'ZGARMAYDI.
    """
    import json as _json_ms
    from production_models import ProductionOrder
    q = db.query(ProductionOrder).filter(
        ProductionOrder.status.in_(["in_progress", "completed"]),
        ProductionOrder.recipe_snapshot_json.isnot(None))
    if company_id is not None:
        q = q.filter(ProductionOrder.company_id == company_id)
    if order_item is not None:
        q = q.filter(ProductionOrder.source_order_item_id == order_item.id)
    elif finished_product is not None:
        q = q.filter(ProductionOrder.finished_product_id == finished_product.id)
    else:
        return None
    jami_miqdor = 0.0
    sarf = {}
    for po in q.order_by(ProductionOrder.id).all():
        pq = float(po.quantity or 0)
        try:
            surat = _json_ms.loads(po.recipe_snapshot_json or "[]")
        except Exception:
            surat = None
        if pq <= 0 or not isinstance(surat, list):
            continue
        jami_miqdor += pq
        eski_qoplama = None
        for qator in surat:
            if not isinstance(qator, dict) or not qator.get("included"):
                continue
            if (qator.get("component_type") or "raw_material") == "packaging":
                continue
            if "is_coating" in qator:
                qoplamami = bool(qator.get("is_coating"))
            else:
                if eski_qoplama is None:
                    eski_qoplama = _mrp_eski_surat_qoplamalari(db, po)
                qoplamami = bool(qator.get("is_optional")) and qator.get("inventory_id") in eski_qoplama
            if qoplamami and not qoplama:
                continue
            kerak = float(qator.get("total_quantity_needed_stock_unit",
                                    qator.get("total_quantity_needed", 0)) or 0)
            if kerak <= 0 or not qator.get("inventory_id"):
                continue
            sarf[qator["inventory_id"]] = sarf.get(qator["inventory_id"], 0.0) + kerak
            if surat_narxlari is not None and qator.get("unit_price_at_time") is not None:
                _sx = surat_narxlari.setdefault(qator["inventory_id"], [0.0, 0.0])
                _sx[0] += kerak
                _sx[1] += kerak * float(qator.get("unit_price_at_time") or 0)
    if jami_miqdor <= 0:
        return None
    return {k: v / jami_miqdor for k, v in sarf.items()}


def _mrp_sarf_qiymati(db, sarf: dict, company_id, narxlar: dict = None) -> float:
    """1 birlik sarfning JORIY narxdagi qiymati (brak yozilgan paytdagi narx — 13-band 2-qadam).
    kech55 (34-band): `narxlar` berilsa ({inventory_id: narx}) — lug'atdagi material o'sha
    narxda (qaytgan mahsulot — ishlab chiqarish paytidagi narx), qolgani joriy narxda."""
    from models import Inventory
    jami = 0.0
    for inv_id, miqdor in (sarf or {}).items():
        q = db.query(Inventory).filter(Inventory.id == inv_id)
        if company_id is not None:
            q = q.filter(Inventory.company_id == company_id)
        inv = q.first()
        if inv:
            _nx = narxlar.get(inv_id) if narxlar else None
            jami += float(miqdor) * (float(_nx) if _nx is not None else float(inv.price_per_unit or 0))
    return jami


def _mrp_brakini_yech(db, order_item, order, brak_qty: float, coating_applied: bool,
                      company_id, log: list) -> list:
    """Buyurtmadagi MRP detali braki: suratdagi 1 birlik sarf × brak miqdori ombordan
    yechiladi (`crud.log_movement` — brak yozuviga bog'lam, brak belgisi va narx shu
    yerdan). Ombor 0 ga qirqilmaydi (20-band qoidasi — xomashyo haqiqatan sarflangan)."""
    import crud as _crud_mb
    from models import Inventory
    sarf = _mrp_birlik_sarfi(db, company_id, order_item=order_item, qoplama=bool(coating_applied))
    for inv_id, birlik in sorted((sarf or {}).items()):
        kerak = float(birlik) * float(brak_qty)
        if kerak <= 0:
            continue
        q = db.query(Inventory).filter(Inventory.id == inv_id)
        if company_id is not None:
            q = q.filter(Inventory.company_id == company_id)
        inv = q.with_for_update().first()
        if not inv:
            continue
        inv.stock_quantity = float(inv.stock_quantity or 0) - kerak
        _crud_mb.log_movement(
            db, inv.id, inv.item_name, movement_type="out", quantity=kerak, unit=inv.unit,
            reason=_crud_mb._jurnal_sabab(f"Brak — {order_item.name} (MRP, {brak_qty:g} birlik)"),
            order_id=order.id if order else None, company_id=getattr(inv, 'company_id', None))
        log.append(f"{inv.item_name}: -{kerak:g} {inv.unit} (brak — MRP)")
    db.commit()
    return log


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
    from models import InventoryMovement

    log = []
    if brak_qty <= 0 or not order_item:
        return log

    _bcid = getattr(order, 'company_id', None) or getattr(order_item, 'company_id', None)
    # kech54 (13-band, 5-qadam): MRP detali — retsept suratidan (yuqoridagi izoh).
    # Tayyor mahsulotdan olingan MRP detali — avvalgidek (xomashyo yechilmaydi).
    if ((getattr(order_item, 'category', None) or '').lower() == 'mrp_product'
            and not getattr(order_item, 'finished_product_id', None)):
        return _mrp_brakini_yech(db, order_item, order, brak_qty, coating_applied, _bcid, log)
    default_p = get_default_penoplast(db, company_id=_bcid)
    total_volume = _item_volume_m3(db, order_item, default_p)
    qty_units = order_item.order_qty_normalized
    if total_volume > 0 and qty_units > 0:
        per_unit_volume = total_volume / qty_units
        brak_volume = per_unit_volume * brak_qty
        pid = order_item.penoplast_id or (default_p.id if default_p else None)
        if pid and brak_volume > 0:
            p = _peno_of(db, pid, _bcid)
            if p and p.volume_per_unit and p.volume_per_unit > 0:
                blocks = brak_volume / float(p.volume_per_unit)
                old_qty = float(p.stock_quantity or 0)
                # 20-band (2026-09-21): 0 ga QIRQILMAYDI. Penoplast allaqachon
                # kesilgan — sarf haqiqiy; jurnalga ham to'liq `blocks` yoziladi.
                # Ilgari `max(0, ...)` manfiy qoldiqni ("qarz" — masalan
                # `deduct_inventory_for_order` ataylab qoldirgan tanqislikni)
                # jimgina 0 ga ko'tarib o'chirardi, jurnal esa to'liq sarfni
                # ko'rsatardi — ombor va jurnal bir-biriga zid bo'lib qolardi.
                p.stock_quantity = old_qty - blocks
                db.add(InventoryMovement(
                    inventory_id=p.id, item_name=p.item_name, movement_type="out",
                    quantity=blocks, unit=p.unit,
                    reason=f"Brak — {order_item.name} ({brak_qty:g} birlik)",
                    order_id=order.id if order else None,
                    # kech45 (13-band): brak yozuviga bog'lam (o'chirishda qaytadi)
                    return_item_id=db.info.get("_brak_qaytarish_id"),
                    # kech46 (13-band, 2-qadam): chiqim paytidagi narx muzlatiladi
                    unit_cost=float(p.price_per_unit or 0),
                    # kech52 (13-band, 3-qadam): brak belgisi — hisobot matnga qaramaydi
                    is_brak=True
                ))
                log.append(f"{p.item_name}: -{blocks:.3f} blok (brak uchun)")

    if coating_applied and order_item.is_coated and order:
        # kech54 (41-band): 1 birlik loyi — qoplama narxi ulushi bo'yicha (`_brak_loyi_birlikka`)
        loy_per_unit = _brak_loyi_birlikka(order, order_item)
        if loy_per_unit > 0:
            brak_loy_kg = loy_per_unit * brak_qty
            if brak_loy_kg > 0:
                # kech58 (K58-1, 43-band): brak loyi — buyurtma loyi YECHILGAN retseptdan
                # (`resolve_recipe(order=...)`), detalning o'z `recipe_id` sidan EMAS.
                loy_log = deduct_loy_ingredients(
                    db, order, brak_loy_kg, recipe_id=None,
                    reason_override=f"Brak — {order_item.name} (qoplama, {brak_qty:g} birlik)"
                )
                log.extend([f"{l} (brak — qoplama)" for l in loy_log])

    db.commit()
    return log


def check_loy_ingredients_for_order(db: Session, order_recipe_id: int, loy_kg: float,
                                    company_id: int = None, commit: bool = True) -> dict:
    """Qoplama (loy) uchun kerakli xomashyo yetarli-yetarli emasligini
    OLDINDAN tekshiradi (hali hech narsa ayirilmasdan). Avval "tayyor loy"
    zaxirasi hisobga olinadi, keyin qolgan qism uchun retsept xomashyosi
    tekshiriladi — deduct_loy_ingredients() bilan BIR XIL mantiq."""
    from models import Inventory

    if loy_kg <= 0:
        return {"enough": True, "shortages": []}

    # 2026-09-21 — TENANT: retsept faqat o'z korxonasidan (resolve_recipe).
    recipe = resolve_recipe(db, recipe_id=order_recipe_id, company_id=company_id)
    if not recipe:
        return {"enough": True, "shortages": []}

    # Tayyor loy zaxirasi bor-yo'qligini tekshiramiz (ayirmasdan, faqat o'qib)
    # kech63 (53-band): `commit=False` — pozitsiya yangi yaratilsa ham faqat `flush` (tahrir qulfi).
    stock = get_or_create_loy_stock(db, recipe, commit=commit)
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


def deduct_loy_ingredients(db: Session, order, loy_kg: float, use_stock: bool = True, recipe_id: int = None, reason_override: str = None, company_id: int = None, commit: bool = True) -> list:
    """
    Loy (qoplama) uchun ingredientlarni ombordan ayiradi.
    use_stock=True bo'lsa — avval tayyor loy zaxirasidan oladi.
    recipe_id berilsa — aynan O'SHA retsept ishlatiladi (masalan "Loy sotish"
    detali uchun, buyurtmaning umumiy qoplama retseptidan farqli bo'lishi
    mumkin). Berilmasa — avvalgidek, buyurtmadan avtomatik topiladi.
    reason_override berilsa — jurnal yozuvida standart "Buyurtma X (loy)"
    o'rniga shu matn ishlatiladi (masalan brak hisoboti uchun "Brak — ...").
    kech63 (53-band): `commit=False` — oxirida (va tayyor loy zaxirasida) faqat `flush`:
    chaqiruvchi qulf (101, buyurtma) ostida BITTA tranzaksiyada ishlaydi (buyurtma tahriri).
    """
    from models import Inventory

    if loy_kg <= 0:
        return []

    log = []

    # 2026-09-21 — TENANT: berilgan recipe_id ham korxona bo'yicha
    # tekshiriladi; zaxira yo'l ("bazadagi birinchi retsept") korxona
    # noma'lum bo'lsa ISHLATILMAYDI. Sabab: ingredientlar retseptdan
    # olinadi, ya'ni begona retsept = begona OMBORDAN ayirish.
    recipe = resolve_recipe(db, recipe_id=recipe_id, order=order,
                            company_id=company_id)

    if not recipe:
        print("⚠ Retsept topilmadi — loy ingredientlari ayirilmadi")
        return []

    # 1) Avval tayyor loy zaxirasidan olamiz
    if use_stock:
        taken, loy_kg, msg = take_loy_from_stock(db, recipe, loy_kg, order=order, reason_override=reason_override,
                                                 commit=commit)
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
            # 2026-09-21 — FOYDALANUVCHI QARORI (19-band): loy xomashyosi
            # yetishmasa ishlab chiqarish TO'XTAMAYDI, qoldiq MANFIYGA
            # tushadi va keyingi kirimda qoplanadi (so'zma-so'z: "ishlab
            # chiqarish to'xtamaydi, manfiyga tushib qoladi, omborga kirim
            # qilinganda ayirilib tashlanadi, shunday ishlasin").
            # Ilgari (2026-09 audit) bu yerda qoldiq 0 da to'xtatilardi —
            # yetishmagan miqdor HECH QAYERDA qolmasdi: keyingi kirim uni
            # qoplamas, ombor haqiqatdagidan KO'P ko'rinardi. Kirim
            # (`crud._purchase_stock_no_commit`) manfiy qoldiqni arifmetik
            # qoplaydi va narxni faqat yangi xariddan oladi. Qo'lda chiqim
            # (`crud.update_stock`) manfiy qoldiqdan chiqim qilishni RAD
            # etadi (qarz jimgina o'chmasin). Faqat LOY ingredientlari —
            # penoplast yetishmasa avvalgidek to'xtaydi.
            current = float(inv_item.stock_quantity or 0)
            new_qty = current - needed_kg
            inv_item.stock_quantity = new_qty
            log.append(f"{inv_item.item_name}: -{needed_kg:.2f} {inv_item.unit}")
            if new_qty < -0.001:
                # Shu ayirishning omborda YO'Q qismi (qoldiq oldindan
                # manfiy bo'lsa — butun ayirish).
                shortage = min(needed_kg, -new_qty)
                log.append(f"⚠️ {inv_item.item_name}: omborda YETARLI EMAS EDI — {shortage:.2f} {inv_item.unit} yetishmovchilik; qoldiq manfiy: {new_qty:.2f} {inv_item.unit}, keyingi kirimda qoplanadi")
                print(f"⚠ {inv_item.item_name}: YETISHMOVCHILIK {shortage:.2f} {inv_item.unit}, qoldiq {new_qty:.2f}")
            print(f"✓ {inv_item.item_name}: -{needed_kg:.2f} ayirildi")
            import crud as _crud
            _crud.log_movement(
                db, inv_item.id, inv_item.item_name, movement_type="out",
                quantity=needed_kg, unit=inv_item.unit,
                reason=reason_override or f"Buyurtma {getattr(order, 'order_number', None) or (order.id if order else '?')} (loy)",
                order_id=order.id if order else None
            )

    if commit:
        db.commit()
    else:
        db.flush()
    return log


def return_loy_ingredients(db: Session, order, loy_kg: float, recipe_id: int = None,
                           company_id: int = None, reason_override: str = None,
                           commit: bool = True) -> list:
    """
    Loy ingredientlarini omborga qaytaradi (buyurtma o'chirilganda).
    recipe_id berilsa — aynan O'SHA retsept ishlatiladi.

    20-band (2026-09-21): `reason_override` — jurnal sababi (masalan tayyor
    mahsulot o'chirilganda). Ilgari u yo'l soxta "TERMOPANEL +" buyurtma
    obyekti bilan chaqirilar va HAR QANDAY mahsulot o'chirilganda jurnalga
    "Buyurtma TERMOPANEL + bekor qilindi" yozilardi. Berilmasa — eski matn.

    2026-09-21 — TENANT: retsept qidiruvi `resolve_recipe` ga o'tkazildi.
    Qaytarish ham xuddi ayirish kabi xavfli edi — begona retsept bilan
    BEGONA omborga xomashyo "qaytarilardi".

    kech63 (53-band): `commit=False` — oxirida faqat `flush` (buyurtma tahriri qulf ostida).
    """
    from models import Inventory

    if loy_kg <= 0:
        return []

    log = []

    recipe = resolve_recipe(db, recipe_id=recipe_id, order=order,
                            company_id=company_id)

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
                reason=reason_override or f"Buyurtma {getattr(order, 'order_number', order.id)} bekor qilindi (loy qaytarildi)",
                order_id=order.id
            )

    if commit:
        db.commit()
    else:
        db.flush()
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
        self.unit_price_for_volume = d.get('unit_price_for_volume')
        self.penoplast_id = d.get('penoplast_id')
        self.price_per_m3 = d.get('price_per_m3')
        self.finished_product_id = d.get('finished_product_id')
        # Ichki qo'shimcha detallar — dict shaklida keladi (bevosita
        # _item_volume_m3/_sub_details_volume_m3 buni o'qiy oladi)
        self.sub_details = d.get('sub_details') or []


def adjust_inventory_diff(db: Session, old_items, new_items, order_id: int = None,
                          company_id: int = None, commit: bool = True) -> list:
    """Eski va yangi detallarni solishtirib, ombordagi penoplastni
    faqat farq miqdorida to'g'rilaydi.

    old_items / new_items — OrderItem obyektlari yoki dict lar ro'yxati.

    kech41 (14-band): `commit=False` — faqat `flush`; chaqiruvchi qulf (101,
    buyurtma) ostida ishlasa, oraliq `commit` qulfni muddatidan OLDIN
    bo'shatmasin. O'LCHANGAN (PG): `delete_order_item` qulf olsa ham shu
    `commit` qulfni bo'shatar, parallel yetkazish detal hali o'chmagan holatni
    ko'rib, keyin FK xatosi (500) bilan yiqilardi.
    """
    import crud as _crud

    def _norm(items):
        out = []
        for it in items:
            out.append(_FakeItem(it) if isinstance(it, dict) else it)
        return out

    if company_id is None and order_id:
        from models import Order as _Ord
        company_id = db.query(_Ord.company_id).filter(_Ord.id == order_id).scalar()
    old_vol = _group_volumes_by_penoplast(db, _norm(old_items), company_id=company_id)
    new_vol = _group_volumes_by_penoplast(db, _norm(new_items), company_id=company_id)

    log = []
    all_ids = set(old_vol.keys()) | set(new_vol.keys())

    for pid in all_ids:
        old_v = old_vol.get(pid, 0.0)
        new_v = new_vol.get(pid, 0.0)
        diff = new_v - old_v          # + = ko'paydi, − = kamaydi

        if abs(diff) < 0.0001:
            continue

        p = _peno_of(db, pid, company_id, lock=True)
        if not p:
            continue

        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks = diff / vol_per_unit

        if blocks > 0:
            # 20-band (2026-09-21): 0 ga QIRQILMAYDI — `deduct_inventory_for_order`
            # bilan bir xil qoida (tanqislik yashirilmaydi, manfiy "qarz"
            # keyingi kirimda qoplanadi). Jurnalga ham to'liq `blocks` yoziladi.
            p.stock_quantity = float(p.stock_quantity) - blocks
            log.append(f"{p.item_name}: -{blocks:.2f} blok (qo'shildi)")
            # MUHIM: bu harakat AVVAL "Ombor harakatlari" jurnaliga yozilmasdi
            # — shuning uchun buyurtma tahrirlanganda Penoplast o'zgarishi
            # "yashirin" qolib, faqat oxirgi raqamda ko'rinib turardi.
            _crud.log_movement(db, pid, p.item_name, "out", blocks, unit="blok",
                                reason="Buyurtma tahrirlandi — qo'shimcha detal", order_id=order_id)
        else:
            p.stock_quantity = float(p.stock_quantity) + abs(blocks)
            log.append(f"{p.item_name}: +{abs(blocks):.2f} blok (qaytdi)")
            _crud.log_movement(db, pid, p.item_name, "in", abs(blocks), unit="blok",
                                reason="Buyurtma tahrirlandi — detal kamaytirildi/o'chirildi", order_id=order_id)

    if log:
        if commit:
            db.commit()
        else:
            db.flush()
    return log


def check_inventory_diff(db: Session, old_items, new_items, company_id: int = None) -> dict:
    """Tahrirlashdan keyin xomashyo yetadimi — tekshiradi."""

    def _norm(items):
        return [_FakeItem(it) if isinstance(it, dict) else it for it in items]

    old_vol = _group_volumes_by_penoplast(db, _norm(old_items), company_id=company_id)
    new_vol = _group_volumes_by_penoplast(db, _norm(new_items), company_id=company_id)

    shortages = []
    for pid in set(old_vol.keys()) | set(new_vol.keys()):
        diff = new_vol.get(pid, 0.0) - old_vol.get(pid, 0.0)
        if diff <= 0:
            continue
        p = _peno_of(db, pid, company_id)
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


def get_loy_cost_per_kg(db: Session, recipe_id: int = None,
                        company_id: int = None, narxlar: dict = None) -> dict:
    """Retsept bo'yicha 1 kg loyning tan narxi.

    ⚠ 2026-09-21: `company_id` YO'Q edi. Ikki xavf bor edi:
      1) berilgan `recipe_id` korxona bo'yicha tekshirilmasdi;
      2) retsept topilmasa `db.query(Recipe).first()` — BUTUN bazadagi
         birinchi retseptni olardi, ya'ni boshqa korxonanikini.
    O'lchangan: B korxona admini `/api/loy-cost` da A ning retsepti
    (`AAA_Rec`) va uning tan narxini ko'rdi."""

    # 2026-09-21 (2-tuzatish): qidiruv `resolve_recipe` ga o'tkazildi.
    # Sabab: bu yerdagi zaxira yo'l `company_id` BERILMAGANDA hamon
    # butun bazadan birinchi retseptni olardi — ya'ni himoya
    # chaqiruvchining esida saqlashiga bog'liq edi. Endi korxona
    # noma'lum bo'lsa zaxira yo'l umuman ishlamaydi.
    recipe = resolve_recipe(db, recipe_id=recipe_id, company_id=company_id)

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
        # kech55 (34-band): `narxlar` berilsa ({inventory_id: 1 birlik narxi} —
        # buyurtmada ISHLATILGAN paytdagi narx, `_buyurtma_sarf_narxlari`) o'sha
        # narx; lug'atda yo'q material va `narxlar` berilmagan chaqiruv — JORIY
        # narx (avvalgi xulq AYNAN).
        _ing_narx = (float(narxlar[inv.id]) if (narxlar and inv.id in narxlar)
                     else float(inv.price_per_unit or 0))
        if _ing_narx:
            per_kg = (kg / batch) * _ing_narx
            cost += per_kg
            breakdown.append({
                "name": inv.item_name,
                "kg_per_batch": kg,
                "price": _ing_narx,
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

def calculate_monthly_master_kpi(db: Session, year: int, month: int,
                                 company_id: int = None) -> dict:
    """Shu oy SOF FOYDASIDAN usta KPI xarajatini hisoblaydi (yillik jamlanadi,
    lekin har oy tegishli ulushi xarajat sifatida yoziladi)."""
    from models import Order, OrderStatus, Master, FinishedProductSale as _FPS_kpi
    from sqlalchemy import extract

    # M5 (2026-09-18) — TENANT: ilgari barcha korxonalar ustalari
    # olinardi, ya'ni B ustasining KPI xarajati A ning oylik hisobiga
    # tushardi.
    _mq = db.query(Master).filter(Master.is_active == True, Master.kpi_percent > 0)
    if company_id is not None:
        _mq = _mq.filter(Master.company_id == company_id)
    masters = _mq.all()
    breakdown = []
    total = 0.0

    for m in masters:
        # MUHIM: o'chirilgan buyurtmalar ham hisobga olinadi — moliyaviy
        # tarix (shu jumladan Usta KPI hisobi) o'zgarmasligi kerak.
        _oq = db.query(Order).filter(
            Order.master_id == m.id,
            Order.status == OrderStatus.READY,
            extract('year', Order.completed_at) == year,
            extract('month', Order.completed_at) == month
        )
        if company_id is not None:      # M5
            _oq = _oq.filter(Order.company_id == company_id)
        orders = _oq.all()

        monthly_profit = 0.0
        for o in orders:
            try:
                profit_data = calculate_order_profit(db, o.id)
                monthly_profit += float(profit_data.get("foyda", 0))
            except Exception as e:
                try:
                    import crud as _crud_log
                    _crud_log.log_error(db, str(e), endpoint=f"calculate_monthly_master_kpi:calculate_order_profit order#{o.id}")
                except Exception:
                    pass

        # MUHIM (2026-09): Tayyor mahsulot bo'limidan TO'G'RIDAN-TO'G'RI
        # (buyurtmasiz) sotilgan, lekin sotuv paytida shu ustaga
        # BIRIKTIRILGAN (master_id) sotuvlar — ular ham shu ustaning KPI
        # hisobiga qo'shiladi. Aks holda usta "Tayyor mahsulot" bo'limidan
        # to'g'ridan-to'g'ri xarid qilib sotsa, buyurtma ochilmagani uchun
        # KPI umuman hisoblanmay qolar edi.
        fp_sales = db.query(_FPS_kpi).filter(
            _FPS_kpi.master_id == m.id,
            extract('year', _FPS_kpi.sold_at) == year,
            extract('month', _FPS_kpi.sold_at) == month
        ).all()
        monthly_profit += sum(float(s.total_amount or 0) - float(s.cost_amount or 0) for s in fp_sales)

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


def calculate_monthly_ehson(db: Session, year: int, month: int,
                            company_id: int = None) -> dict:
    """Shu oy SOF FOYDASIDAN — admin belgilagan foizga ko'ra — Ehson (xayriya)
    miqdorini hisoblaydi. Usta KPI bilan bir xil mantiqda, lekin bitta,
    umumiy (butun korxona) foiz asosida — har bir alohida usta emas.

    MUHIM: "monthly_profit" — Ehson foizi 0 bo'lsa ham HAR DOIM to'g'ri
    hisoblanadi (chunki bu qiymat, Moliyadagi "Buyurtmalardan foyda"
    ko'rsatkichi uchun ham ishlatiladi — Ehson yoqilgan-yoqilmaganidan
    qat'i nazar)."""
    from models import Order, OrderStatus
    from sqlalchemy import extract
    import crud as _crud

    percent = float(_crud.get_setting(db, "ehson_percent", "0",
                                      company_id=company_id) or 0)

    # MUHIM: o'chirilgan buyurtmalar ham hisobga olinadi — moliyaviy
    # tarix (shu jumladan Ehson hisobi) o'zgarmasligi kerak.
    _oq = db.query(Order).filter(
        Order.status == OrderStatus.READY,
        extract('year', Order.completed_at) == year,
        extract('month', Order.completed_at) == month
    )
    if company_id is not None:      # M5
        _oq = _oq.filter(Order.company_id == company_id)
    orders = _oq.all()

    monthly_profit = 0.0
    for o in orders:
        try:
            profit_data = calculate_order_profit(db, o.id)
            monthly_profit += float(profit_data.get("foyda", 0))
        except Exception as e:
            try:
                _crud.log_error(db, str(e), endpoint=f"calculate_monthly_ehson:calculate_order_profit order#{o.id}")
            except Exception:
                pass

    # Tayyor mahsulot to'g'ridan-to'g'ri sotuvi ham —
    # bu ham korxonaning haqiqiy foydasi, Ehson shu foydadan hisoblanadi
    from models import FinishedProductSale as _FPS
    # 2026-09-18 — TENANT: bu funksiya `get_monthly_report` ICHIDAN
    # chaqiriladi (ehson xarajati), shuning uchun filtrsiz qolgan bu
    # so'rov FAIL-2 ning bir qismi edi — A ning sotuv foydasi B ning
    # ehson hisobiga qo'shilardi.
    _fpsq2 = db.query(_FPS).filter(
        extract('year', _FPS.sold_at) == year,
        extract('month', _FPS.sold_at) == month
    )
    if company_id is not None:
        _fpsq2 = _fpsq2.filter(_FPS.company_id == company_id)
    fp_sales = _fpsq2.all()
    monthly_profit += sum(float(s.total_amount or 0) - float(s.cost_amount or 0) for s in fp_sales)

    if monthly_profit <= 0:
        return {"percent": percent, "monthly_profit": round(monthly_profit), "ehson_amount": 0}

    ehson_amount = monthly_profit * percent / 100
    return {"percent": percent, "monthly_profit": round(monthly_profit), "ehson_amount": round(ehson_amount)}


def calculate_monthly_employee_pay(db: Session, year: int, month: int,
                                   daromad: float, sof_foyda_before: float,
                                   jami_metr: float, jami_dona: float,
                                   jami_blok: float, jami_qoplama_birlik: float = 0.0,
                                   company_id: int = None) -> dict:
    """Moslashuvchan hodimlar uchun oylik to'lovni hisoblaydi.
    daromad, sof_foyda_before — shu oy uchun (hodim xarajatlarigacha).
    jami_metr/dona/blok — shu oy ishlab chiqarilgan miqdorlar (hammasi).
    jami_qoplama_birlik — shu oy QOPLANGAN detallar: metr + dona (profil/panel metrda,
    donali dona bilan, bittalashtirib qo'shilgan) — qoplamachi bonusi uchun."""
    from models import Employee, PayType
    from datetime import datetime as _dt_emp
    from calendar import monthrange as _monthrange_emp
    import crud as _crud

    # MUHIM (2026-09): hodim, FAQAT allaqachon ISHGA KIRGAN oylar uchun
    # hisoblanishi kerak — aks holda, masalan Sentyabrda yangi qo'shilgan
    # hodim, tizim tomonidan, "Iyul/Avgust uchun ham qarzdormiz" deb,
    # NOTO'G'RI hisoblanib qolar edi (garchi u hali ishga kirmagan bo'lsa
    # ham). Shu oyning OXIRGI kunigacha ishga kirgan hodimlarni olamiz.
    _last_day = _monthrange_emp(year, month)[1]
    _month_end = _dt_emp(year, month, _last_day, 23, 59, 59)
    # M5 (2026-09-18) — TENANT: B korxonaning xodimi A ning oylik
    # to'lov hisobiga tushmasligi uchun.
    _eq = db.query(Employee).filter(
        Employee.is_active == True,
        Employee.is_deleted.isnot(True),
        Employee.hire_date <= _month_end
    )
    if company_id is not None:
        _eq = _eq.filter(Employee.company_id == company_id)
    employees = _eq.all()
    breakdown = []
    total = 0.0

    unit_map = {
        "metr": jami_metr, "dona": jami_dona, "blok": jami_blok,
    }

    for e in employees:
        amount = 0.0
        detail = ""

        # MUHIM: e.fixed_amount/e.pay_type kabi JORIY qiymatlar EMAS —
        # aynan shu (year, month) uchun O'SHA PAYTDA amal qilgan to'lov
        # parametrlari olinadi. Shu sababli, oylik keyinchalik oshirilsa
        # ham, o'tgan oylarning hisob-kitobi o'zgarib qolmaydi.
        comp = _crud.get_employee_compensation_for_month(db, e.id, year, month)
        c_pay_type = comp["pay_type"]
        c_fixed = comp["fixed_amount"]
        c_percent = comp["percent_value"]
        c_unit_rate = comp["per_unit_rate"]
        c_unit_type = comp["per_unit_type"]
        c_extra_monthly = comp["extra_monthly"]

        if c_pay_type == PayType.FIXED:
            amount = float(c_fixed or 0)
            detail = f"Doimiy oylik"

        elif c_pay_type == PayType.PERCENT_SALES:
            amount = daromad * float(c_percent or 0) / 100
            detail = f"Sotuv {fmt_num(daromad)} × {c_percent}%"

        elif c_pay_type == PayType.PERCENT_PROFIT:
            amount = max(0, sof_foyda_before) * float(c_percent or 0) / 100
            detail = f"Foyda {fmt_num(sof_foyda_before)} × {c_percent}%"

        elif c_pay_type == PayType.PER_UNIT:
            qty = unit_map.get(c_unit_type, 0)
            amount = qty * float(c_unit_rate or 0)
            detail = f"{qty:g} {c_unit_type} × {fmt_num(c_unit_rate)}"

        elif c_pay_type == PayType.FIXED_PLUS_COATING:
            base = float(c_fixed or 0)
            rate = float(c_unit_rate or 1000)
            bonus = jami_qoplama_birlik * rate
            amount = base + bonus
            detail = f"Oylik {fmt_num(base)} + {jami_qoplama_birlik:g} metr/dona × {fmt_num(rate)} = {fmt_num(bonus)}"

        # Ixtiyoriy qo'shimcha doimiy oylik — istalgan to'lov turiga qo'shiladi
        if c_extra_monthly:
            amount += float(c_extra_monthly)
            extra_txt = f"qo'shimcha oylik {fmt_num(c_extra_monthly)}"
            detail = f"{detail} + {extra_txt}" if detail else extra_txt

        # QO'LDA KAMAYTIRISH — masalan kelmagan kunlar uchun (admin real
        # vaziyatni bilgan holda kiritadi, avtomatik formula EMAS).
        # QO'LDA BONUS — masalan yaxshi ishlagani uchun qo'shimcha rag'bat.
        # MUHIM: bu — Moliya, Hisobotlar bilan BIR XIL manbadan (shu
        # funksiyadan) o'qiladi, shuning uchun barcha joyda avtomatik sinxron.
        adjustment = 0.0
        adjustment_reason = None
        bonus = 0.0
        bonus_reason_val = None
        from models import EmployeeMonthlyAdjustment
        adj = db.query(EmployeeMonthlyAdjustment).filter(
            EmployeeMonthlyAdjustment.employee_id == e.id,
            EmployeeMonthlyAdjustment.year == year,
            EmployeeMonthlyAdjustment.month == month
        ).first()
        if adj:
            if float(adj.reduction_amount or 0) > 0:
                adjustment = float(adj.reduction_amount)
                adjustment_reason = adj.reason
                amount = max(0, amount - adjustment)
                adj_txt = f"− {fmt_num(adjustment)} (kamaytirish{': ' + adjustment_reason if adjustment_reason else ''})"
                detail = f"{detail} {adj_txt}" if detail else adj_txt
            if float(adj.bonus_amount or 0) > 0:
                bonus = float(adj.bonus_amount)
                bonus_reason_val = adj.bonus_reason
                amount = amount + bonus
                bonus_txt = f"+ {fmt_num(bonus)} (bonus{': ' + bonus_reason_val if bonus_reason_val else ''})"
                detail = f"{detail} {bonus_txt}" if detail else bonus_txt

        # MUHIM: avval faqat "amount > 0" bo'lsa ro'yxatga qo'shilardi —
        # bu, agar "kamaytirish" hodimning butun oyligini "0"gacha
        # tushirib yuborsa (masalan butun oy kelmagan bo'lsa), hodimni
        # RO'YXATDAN BUTUNLAY YO'QOTIB YUBORARDI, va "Bonus/Kamaytirish"
        # tugmalari qayta bosib bo'lmaydigan holga kelardi (chunki
        # hodimning o'zi ko'rinmay qolardi). Endi — agar adjustment yoki
        # bonus qo'llanilgan bo'lsa, "amount=0" bo'lsa ham hodim ro'yxatda
        # qoladi (shunda uni yana ko'rish/tuzatish mumkin bo'ladi).
        if amount > 0 or adjustment > 0 or bonus > 0:
            total += amount
            avans = get_employee_advances_total(db, e.id, year, month)
            breakdown.append({
                "employee_id": e.id,
                "name": e.name,
                "position": e.position,
                "pay_type": c_pay_type.value,
                "detail": detail,
                "amount": round(amount),
                "avans": round(avans),
                "qolgan": round(amount - avans),
                "adjustment": round(adjustment) if adjustment else 0,
                "adjustment_reason": adjustment_reason,
                "bonus": round(bonus) if bonus else 0,
                "bonus_reason": bonus_reason_val
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


def get_order_item_unit_cost(db: Session, order, item, include_coating: bool = True,
                             muzlatilgan: bool = False) -> float:
    """Bitta detalning 1 birlik (metr/dona) TAN NARXI — penoplast + (agar
    include_coating=True bo'lsa) loy. Brak qiymatini hisoblash uchun —
    sotuv narxi emas, xomashyo qiymati.
    include_coating=False — faqat Penoplast (loy hali tortilmagan holat uchun).

    kech55 (5-bo'lim 34-band, O'LCHANGAN — `work/probe56.py`): muzlatilgan=True —
    xomashyo shu buyurtmada ISHLATILGAN paytdagi narxda (`_buyurtma_sarf_narxlari`,
    32-band qarori "ishlatilgan paytdagi narxda muzlatilsin" bilan bir xil manba);
    MRP mahsuloti — ishlab chiqarish suratidagi narxda (`unit_price_at_time`).
    Faqat QAYTGAN mahsulot tannarxi uchun (`crud.add_returned_to_stock`): aks holda
    narx oshgandan keyin qaytgan 2 m (5 000 so'm/m ga qilingan) 30 000 so'm tannarx
    bilan omborga tushib, sotuv / kamaytirishda foydani sun'iy kamaytirardi.
    Brak summasi va oldindan ko'rish — JORIY narx (13-band 2-qadam), muzlatilgan=False.
    Jurnali yo'q eski buyurtma / surat narxisiz qator — joriy narx (taxmin qilinmaydi)."""

    if getattr(item, 'finished_product_id', None):
        # FASA 4B: avval bu yerda `cost_price / produced_quantity` ishlatilardi
        # — bu sotish (`cost_price / joriy_qoldiq`) va buyurtmaga olish/qaytarish
        # (xomashyoning JONLI narxidan hisoblangan `_fp_stable_unit_cost`)dagi
        # formuladan farq qilardi, ya'ni bitta mahsulotning "1 birlik tan narxi"
        # UCH XIL joyda UCH XIL son bo'lardi. Endi hammasi BITTA manbadan —
        # xomashyoning joriy narxidan hisoblanadigan _fp_stable_unit_cost'dan.
        from models import FinishedProduct
        # M4 (2026-09-18) — TENANT: tan narx manbasi buyurtmaning O'Z
        # korxonasidagi mahsulot bo'lishi shart.
        _ucq = db.query(FinishedProduct).filter(FinishedProduct.id == item.finished_product_id)
        _uc_cid = getattr(order, 'company_id', None)
        if _uc_cid is not None:
            _ucq = _ucq.filter(FinishedProduct.company_id == _uc_cid)
        fp = _ucq.first()
        if fp:
            import crud as _crud_unitcost
            unit_cost = _crud_unitcost._fp_stable_unit_cost(db, fp)
            if unit_cost > 0:
                return unit_cost
            # Orqaga moslik: xomashyo ma'lumoti yo'q (eski/oddiy) yozuvlar uchun
            base_qty = float(fp.produced_quantity if fp.produced_quantity is not None else (fp.quantity or 0))
            if base_qty > 0 and fp.cost_price:
                return float(fp.cost_price) / base_qty
        return 0.0

    _ucid = getattr(order, 'company_id', None) or getattr(item, 'company_id', None)
    # kech55 (34-band): muzlatilgan narxlar (faqat muzlatilgan=True da; aks holda bo'sh — joriy narx).
    _mz_narx = _buyurtma_sarf_narxlari(db, order) if (muzlatilgan and order is not None) else {}
    # kech54 (13-band, 5-qadam): MRP mahsuloti — retsept suratidagi xomashyo JORIY narxda
    # (brak yozilgan paytdagi narx); surat yo'q — 0 (brak baribir rad etiladi).
    if (getattr(item, 'category', None) or '').lower() == 'mrp_product':
        _mz_surat = {} if muzlatilgan else None
        _msarf = _mrp_birlik_sarfi(db, _ucid, order_item=item, qoplama=include_coating,
                                   surat_narxlari=_mz_surat)
        _mz_mrp = {k: v / m for k, (m, v) in (_mz_surat or {}).items() if m > 0}
        return round(_mrp_sarf_qiymati(db, _msarf, _ucid, narxlar=_mz_mrp)) if _msarf else 0.0
    default_p = get_default_penoplast(db, company_id=_ucid)
    pid = item.penoplast_id or (default_p.id if default_p else None)
    volume = _item_volume_m3(db, item, default_p,
                             penoplast_narxi=(_mz_narx.get(pid) if pid else None))

    peno_cost_total = 0.0
    if volume > 0 and pid:
        p = _peno_of(db, pid, _ucid)
        if p and p.volume_per_unit:
            blocks = volume / float(p.volume_per_unit)
            _blok_narx = _mz_narx.get(p.id)
            peno_cost_total = blocks * (float(_blok_narx) if _blok_narx is not None
                                        else float(p.price_per_unit or 0))

    qty_units = item.order_qty_normalized
    peno_cost_per_unit = (peno_cost_total / qty_units) if qty_units > 0 else 0.0

    loy_cost_per_unit = 0.0
    if include_coating and item.is_coated and order:
        # kech58 (K58-1, 43-band): brak summasidagi loy narxi — buyurtma loyi YECHILGAN
        # retseptdan (brak yechimi va buyurtma yechimi bilan BITTA manba).
        _qr58 = resolve_recipe(db, order=order, company_id=getattr(order, 'company_id', None))
        recipe_id = _qr58.id if _qr58 else None

        # kech54 (41-band): 1 birlik loyi — qoplama narxi ulushi bo'yicha (`_brak_loyi_birlikka`)
        loy_kg_per_unit = _brak_loyi_birlikka(order, item)
        if loy_kg_per_unit > 0:
            # 2026-09-21 — TENANT: korxona buyurtmaning O'ZIDAN olinadi.
            loy_info = get_loy_cost_per_kg(
                db, recipe_id, company_id=getattr(order, 'company_id', None),
                narxlar=_mz_narx or None)
            loy_cost_per_unit = loy_kg_per_unit * float(loy_info.get("cost_per_kg", 0))

    return round(peno_cost_per_unit + loy_cost_per_unit)
