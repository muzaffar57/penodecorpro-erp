"""
PenoDecorPro ERP — CRUD operatsiyalari
========================================
CRUD = Create (yaratish), Read (o'qish), Update (yangilash), Delete (o'chirish).
Bu fayl bazaga yozish va o'qish funksiyalarini saqlaydi.
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from models import Master
from schemas import MasterCreate, MasterUpdate


# ============================================================
# MASTER CRUD
# ============================================================

def create_master(db: Session, master_data: MasterCreate) -> Master:
    """Yangi ustani bazaga qo'shadi."""
    db_master = Master(
        name=master_data.name,
        phone=master_data.phone,
        cashback_percent=master_data.cashback_percent,
        telegram_id=master_data.telegram_id,
        notes=master_data.notes,
        is_active=True
    )
    db.add(db_master)
    db.commit()
    db.refresh(db_master)
    return db_master


def get_masters(db: Session, only_active: bool = False) -> List[Master]:
    """Barcha ustalarni qaytaradi."""
    query = db.query(Master)
    if only_active:
        query = query.filter(Master.is_active == True)
    return query.order_by(Master.name).all()


def get_master(db: Session, master_id: int) -> Optional[Master]:
    """ID bo'yicha bitta ustani qaytaradi."""
    return db.query(Master).filter(Master.id == master_id).first()


def update_master(db: Session, master_id: int, master_data: MasterUpdate) -> Optional[Master]:
    """Mavjud ustani yangilaydi."""
    db_master = get_master(db, master_id)
    if not db_master:
        return None

    # Faqat berilgan maydonlarni yangilaymiz
    update_data = master_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_master, field, value)

    db.commit()
    db.refresh(db_master)
    return db_master


def delete_master(db: Session, master_id: int) -> bool:
    """Ustani o'chiradi (haqiqatda is_active=False qilamiz, ma'lumot saqlanadi)."""
    db_master = get_master(db, master_id)
    if not db_master:
        return False
    db_master.is_active = False
    db.commit()
    return True


# ============================================================
# INVENTORY CRUD
# ============================================================

from models import Inventory
from schemas import InventoryCreate, InventoryUpdate


def add_item(db: Session, item_data: InventoryCreate) -> Inventory:
    """Yangi xomashyo qo'shadi."""
    is_peno = getattr(item_data, 'is_penoplast', False)
    is_default = getattr(item_data, 'is_default_penoplast', False)

    # Agar asosiy deb belgilangan bo'lsa — eskisini bekor qilamiz
    if is_peno and is_default:
        db.query(Inventory).filter(Inventory.is_default_penoplast == True).update(
            {"is_default_penoplast": False}
        )

    db_item = Inventory(
        item_name=item_data.item_name,
        stock_quantity=item_data.stock_quantity,
        unit=item_data.unit,
        min_stock=item_data.min_stock,
        price_per_unit=item_data.price_per_unit,
        volume_per_unit=item_data.volume_per_unit,
        is_penoplast=is_peno,
        is_default_penoplast=(is_default and is_peno),
        notes=item_data.notes
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    # Agar birinchi penoplast bo'lsa — avtomatik asosiy qilamiz
    if is_peno:
        has_default = db.query(Inventory).filter(
            Inventory.is_default_penoplast == True
        ).first()
        if not has_default:
            db_item.is_default_penoplast = True
            db.commit()
            db.refresh(db_item)

    return db_item


def get_inventory(db: Session) -> List[Inventory]:
    """Barcha xomashyo ro'yxatini qaytaradi."""
    return db.query(Inventory).order_by(Inventory.item_name).all()


def get_item(db: Session, item_id: int) -> Optional[Inventory]:
    """ID bo'yicha bitta xomashyoni qaytaradi."""
    return db.query(Inventory).filter(Inventory.id == item_id).first()


def get_item_by_name(db: Session, name: str) -> Optional[Inventory]:
    """Nom bo'yicha xomashyoni topadi."""
    return db.query(Inventory).filter(Inventory.item_name == name).first()


def update_stock(db: Session, item_id: int, quantity_change: float) -> Optional[Inventory]:
    """Mahsulot qoldig'ini yangilaydi (musbat = qo'shish, manfiy = ayirish).
    Keyinchalik buyurtma bajarilganda avtomatik ishlatiladi."""
    db_item = get_item(db, item_id)
    if not db_item:
        return None
    new_qty = db_item.stock_quantity + quantity_change
    if new_qty < 0:
        new_qty = 0  # Manfiy bo'lmasin
    db_item.stock_quantity = new_qty
    db.commit()
    db.refresh(db_item)
    return db_item


def update_item(db: Session, item_id: int, item_data: InventoryUpdate) -> Optional[Inventory]:
    """Xomashyo ma'lumotlarini yangilaydi."""
    db_item = get_item(db, item_id)
    if not db_item:
        return None
    update_data = item_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)
    db.commit()
    db.refresh(db_item)
    return db_item


def delete_item(db: Session, item_id: int) -> bool:
    """Xomashyoni o'chiradi."""
    db_item = get_item(db, item_id)
    if not db_item:
        return False
    db.delete(db_item)
    db.commit()
    return True


def get_low_stock_items(db: Session) -> List[Inventory]:
    """Qoldiq min_stock dan kam bo'lgan xomashyolar (ogohlantirish)."""
    return db.query(Inventory).filter(Inventory.stock_quantity <= Inventory.min_stock).all()


# ============================================================
# RECIPE CRUD
# ============================================================

from models import Recipe, RecipeType
from schemas import RecipeCreate


def create_recipe(db: Session, recipe_data: RecipeCreate) -> Recipe:
    """Yangi retsept qo'shadi.
    name: 'Kvars' yoki 'Oq Marmar' — RecipeType enum bo'yicha."""
    # String ni enum ga aylantiramiz
    if recipe_data.name.lower() in ['kvars', 'quartz']:
        recipe_type = RecipeType.QUARTZ
    elif recipe_data.name.lower() in ['oq marmar', 'marble', 'marmar']:
        recipe_type = RecipeType.MARBLE
    else:
        # Default
        recipe_type = RecipeType.QUARTZ

    db_recipe = Recipe(
        name=recipe_type,
        akril_kg=recipe_data.akril_kg,
        pva_kg=recipe_data.pva_kg,
        qum_kg=recipe_data.qum_kg,
        kroshka_kg=recipe_data.kroshka_kg,
        penogasitel_kg=recipe_data.penogasitel_kg,
        shtukaturka_kg=recipe_data.shtukaturka_kg,
        suv_kg=recipe_data.suv_kg,
        biotsid_ml=recipe_data.biotsid_ml,
        batch_size_kg=recipe_data.batch_size_kg,
        notes=recipe_data.notes
    )
    db.add(db_recipe)
    db.commit()
    db.refresh(db_recipe)
    return db_recipe


def get_recipes(db: Session) -> List[Recipe]:
    """Barcha retseptlarni qaytaradi."""
    return db.query(Recipe).all()


def get_recipe(db: Session, recipe_id: int) -> Optional[Recipe]:
    """ID bo'yicha bitta retseptni qaytaradi."""
    return db.query(Recipe).filter(Recipe.id == recipe_id).first()


def get_recipe_by_name(db: Session, name: str) -> Optional[Recipe]:
    """Nom bo'yicha retseptni topadi (Kvars yoki Oq Marmar)."""
    if name.lower() in ['kvars', 'quartz']:
        return db.query(Recipe).filter(Recipe.name == RecipeType.QUARTZ).first()
    elif name.lower() in ['oq marmar', 'marble', 'marmar']:
        return db.query(Recipe).filter(Recipe.name == RecipeType.MARBLE).first()
    return None


def delete_recipe(db: Session, recipe_id: int) -> bool:
    """Retseptni o'chiradi."""
    db_recipe = get_recipe(db, recipe_id)
    if not db_recipe:
        return False
    db.delete(db_recipe)
    db.commit()
    return True


# ============================================================
# PROJECT CRUD
# ============================================================

from models import Project, Order, OrderItem, ProjectStatus, OrderStatus, OrderType
from schemas import ProjectCreate, OrderCreate


def create_project(db: Session, project_data: ProjectCreate) -> Project:
    """Yangi loyiha qo'shadi."""
    # Eng katta raqamni topib +1 qilamiz (count emas, chunki o'chirilgan bo'lishi mumkin)
    last = db.query(Project).order_by(Project.id.desc()).first()
    next_num = (last.id + 1) if last else 1
    # Agar shu raqamli loyiha mavjud bo'lsa, keyingisini olamiz
    while db.query(Project).filter(Project.project_number == f"PRJ-{next_num:03d}").first():
        next_num += 1
    project_number = f"PRJ-{next_num:03d}"

    db_project = Project(
        project_number=project_number,
        project_name=project_data.project_name,
        client_name=project_data.client_name,
        client_phone=project_data.client_phone,
        client_address=project_data.client_address,
        description=project_data.description,
        total_budget=project_data.total_budget or 0,
        notes=project_data.notes,
        status=ProjectStatus.ACTIVE
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


def get_projects(db: Session) -> List[Project]:
    return db.query(Project).order_by(Project.start_date.desc()).all()


def get_projects_with_stats(db: Session) -> List:
    """Loyihalar + buyurtmalar summasi + qarz hisobi (orders ham qo'shilgan)."""
    projects = db.query(Project).order_by(Project.start_date.desc()).all()
    for p in projects:
        orders_count = len(p.orders) if p.orders else 0
        orders_sum = sum(float(o.total_amount or 0) for o in (p.orders or []))
        budget = float(p.total_budget or 0)
        paid = float(p.total_paid or 0)
        actual = budget if budget > 0 else orders_sum
        debt = actual - paid

        # Atributlar qo'shamiz (template uchun)
        p.orders_count = orders_count
        p.orders_sum = orders_sum
        p.debt = debt
        p.actual_sum = actual
    return projects


def add_payment(db: Session, project_id: int, amount: float) -> Optional[Project]:
    """Loyihaga zaklat (avans) qo'shish."""
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        return None
    db_project.total_paid = (float(db_project.total_paid or 0) + amount)
    db.commit()
    db.refresh(db_project)
    return db_project


def get_project(db: Session, project_id: int) -> Optional[Project]:
    return db.query(Project).filter(Project.id == project_id).first()


# ============================================================
# ORDER CRUD
# ============================================================

def create_order(db: Session, order_data: OrderCreate) -> Order:
    """Yangi buyurtma + detallar qo'shadi.

    Mantiq:
    - is_coated=True bo'lsa, narx 2 barobar qilinadi (qoplama qo'shimcha xizmat)
    - Har bir item ning total_price = quantity * unit_price (qoplamali bo'lsa x2)
    - Buyurtma umumiy summasi avtomatik hisoblanadi
    """
    # Order raqami: ORD-{project_id}-{seq}
    seq = db.query(Order).filter(Order.project_id == order_data.project_id).count() + 1
    order_number = f"ORD-{order_data.project_id:03d}-{seq}"

    # OrderType ni aniqlash
    order_type = OrderType.PRODUCT if order_data.order_type == "product" else OrderType.SERVICE

    is_draft = getattr(order_data, 'is_draft', False)

    db_order = Order(
        order_number=order_number,
        project_id=order_data.project_id,
        order_type=order_type,
        status=OrderStatus.DRAFT if is_draft else OrderStatus.IN_PROGRESS,
        master_id=order_data.master_id,
        deadline=getattr(order_data, 'deadline', None),
        notes=order_data.notes,
        total_amount=0
    )
    db.add(db_order)
    db.flush()  # ID olish uchun

    # Detallarni qo'shamiz va umumiy summani hisoblaymiz
    total_amount = 0
    for item_data in order_data.items:
        # unit_price allaqachon frontend tomonida hisoblangan (qoplamali bo'lsa x2)
        item_total = item_data.unit_price * item_data.quantity
        total_amount += item_total

        db_item = OrderItem(
            order_id=db_order.id,
            name=item_data.name,
            category=item_data.category,
            width=item_data.width,
            thickness=item_data.thickness,
            length=item_data.length,
            quantity=item_data.quantity,
            is_coated=item_data.is_coated,
            recipe_id=order_data.recipe_id,
            penoplast_id=getattr(item_data, 'penoplast_id', None),
            price_per_m3=getattr(item_data, 'price_per_m3', None),
            unit_price=item_data.unit_price,
            total_price=item_total,
            notes=item_data.notes
        )
        db.add(db_item)

    db_order.total_amount = total_amount
    # Kelishilgan summa — boshida jami summaga teng (chegirmasiz)
    db_order.agreed_amount = getattr(order_data, 'agreed_amount', None) or total_amount
    if total_amount > 0 and float(db_order.agreed_amount) < total_amount:
        db_order.discount_percent = round((total_amount - float(db_order.agreed_amount)) / total_amount * 100, 2)
    db.commit()
    db.refresh(db_order)
    return db_order


def get_orders(db: Session, project_id: Optional[int] = None) -> List[Order]:
    query = db.query(Order)
    if project_id:
        query = query.filter(Order.project_id == project_id)
    return query.order_by(Order.created_at.desc()).all()


def get_order(db: Session, order_id: int) -> Optional[Order]:
    return db.query(Order).filter(Order.id == order_id).first()


def mark_order_ready(db: Session, order_id: int) -> dict:
    """Buyurtmani 'Tayyor' qilib belgilash + avtomatik mantiq.

    MUHIM AVTOMATIKA:
    1. Status -> READY
    2. Recipe bo'yicha Inventory dan xomashyo ayrish
    3. Usta KPI hisoblash (3% cashback + 1000 so'm/metr)
    """
    db_order = get_order(db, order_id)
    if not db_order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    if db_order.status == OrderStatus.READY:
        return {"success": False, "message": "Bu buyurtma allaqachon tayyor"}

    # 1. Status yangilash
    db_order.status = OrderStatus.READY
    db_order.completed_at = datetime.utcnow()

    # 2. Recipe asosida Inventory kamaytirish
    inventory_log = []
    if db_order.items and db_order.items[0].recipe_id:
        recipe = db.query(Recipe).filter(Recipe.id == db_order.items[0].recipe_id).first()
        if recipe:
            # Qancha qoplama qilinishi kerak (qoplamali itemlar yig'indisi)
            total_coated_qty = sum(
                (item.length or 0) * item.quantity if item.length else item.quantity
                for item in db_order.items if item.is_coated
            )

            # Retsept asosida har bir komponentni hisoblaymiz
            # batch_size_kg uchun retsept bor, total_coated_qty metr uchun
            # Taxminiy: 1 metr karniz ~0.5 kg qoplama ishlatadi
            kg_per_meter = 0.5
            total_kg_needed = total_coated_qty * kg_per_meter

            # Necha partiya kerak
            batches = total_kg_needed / recipe.batch_size_kg if recipe.batch_size_kg else 0

            # Komponentlarni kamaytiramiz
            components = {
                "Akril": recipe.akril_kg * batches,
                "PVA": recipe.pva_kg * batches,
                "Qum": recipe.qum_kg * batches,
                "Kroshka": recipe.kroshka_kg * batches,
                "Penogasitel": recipe.penogasitel_kg * batches,
                "Shtukaturka": recipe.shtukaturka_kg * batches,
                "Suv": recipe.suv_kg * batches,
                "Biotsid": recipe.biotsid_ml * batches,
            }

            for comp_name, qty in components.items():
                if qty > 0:
                    # Inventoryda topish (qisman moslik bilan)
                    inv_item = db.query(Inventory).filter(
                        Inventory.item_name.ilike(f"%{comp_name}%")
                    ).first()
                    if inv_item:
                        inv_item.stock_quantity = max(0, inv_item.stock_quantity - qty)
                        inventory_log.append(f"{inv_item.item_name}: -{qty:.2f} {inv_item.unit}")

    # 3. Usta KPI hisoblash
    kpi_info = None
    if db_order.master_id:
        master = db.query(Master).filter(Master.id == db_order.master_id).first()
        if master:
            # 3% cashback
            cashback = float(db_order.total_amount) * 0.03
            # 1000 so'm har metr uchun
            total_meters = sum(
                (item.length or 0) * item.quantity for item in db_order.items if item.is_coated
            )
            meter_bonus = total_meters * 1000
            total_kpi = cashback + meter_bonus
            kpi_info = {
                "master": master.name,
                "cashback_3%": round(cashback),
                "meter_bonus": round(meter_bonus),
                "total_kpi": round(total_kpi),
                "total_meters": total_meters
            }

    db.commit()
    db.refresh(db_order)

    return {
        "success": True,
        "message": "Buyurtma tayyor!",
        "inventory_changes": inventory_log,
        "master_kpi": kpi_info
    }


# ============================================================
# ORDER edit/delete
# ============================================================

def update_order_item(db: Session, item_id: int, item_data: dict) -> Optional[OrderItem]:
    """Buyurtma detalini yangilash — ombor farq bo'yicha to'g'rilanadi."""
    import services

    db_item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not db_item:
        return None

    order = db_item.order
    is_draft = order.status == OrderStatus.DRAFT if order else False

    # Eski holat snapshot
    old_snap = [{
        "category": db_item.category,
        "width": db_item.width,
        "thickness": db_item.thickness,
        "length": db_item.length,
        "quantity": float(db_item.quantity or 1),
        "unit_price": float(db_item.unit_price or 0),
        "penoplast_id": db_item.penoplast_id
    }]

    for field, value in item_data.items():
        if hasattr(db_item, field):
            setattr(db_item, field, value)

    db_item.total_price = float(db_item.unit_price or 0) * float(db_item.quantity or 1)
    db.flush()

    # Yangi holat snapshot
    new_snap = [{
        "category": db_item.category,
        "width": db_item.width,
        "thickness": db_item.thickness,
        "length": db_item.length,
        "quantity": float(db_item.quantity or 1),
        "unit_price": float(db_item.unit_price or 0),
        "penoplast_id": db_item.penoplast_id
    }]

    # Omborni farq bo'yicha to'g'rilaymiz
    if not is_draft:
        services.adjust_inventory_diff(db, old_snap, new_snap)

    # Order summasi
    if order:
        order.total_amount = sum(float(it.total_price or 0) for it in order.items)
        db.flush()
        db.refresh(order)
        _update_order_payment_status(db, order)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_order(db: Session, order_id: int) -> bool:
    """Buyurtmani o'chirish."""
    db_order = db.query(Order).filter(Order.id == order_id).first()
    if not db_order:
        return False
    db.delete(db_order)
    db.commit()
    return True


def delete_order_item(db: Session, item_id: int) -> bool:
    """Detal o'chirish — xomashyo omborga qaytariladi."""
    import services

    db_item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not db_item:
        return False

    order = db_item.order
    is_draft = order.status == OrderStatus.DRAFT if order else False

    # O'chiriladigan detalning xomashyosini qaytaramiz
    if not is_draft:
        old_snap = [{
            "category": db_item.category,
            "width": db_item.width,
            "thickness": db_item.thickness,
            "length": db_item.length,
            "quantity": float(db_item.quantity or 1),
            "unit_price": float(db_item.unit_price or 0),
            "penoplast_id": db_item.penoplast_id
        }]
        services.adjust_inventory_diff(db, old_snap, [])

    db.delete(db_item)
    db.flush()

    if order:
        order.total_amount = sum(float(it.total_price or 0) for it in order.items)
        db.flush()
        db.refresh(order)
        _update_order_payment_status(db, order)

    db.commit()
    return True


def update_project(db: Session, project_id: int, project_data) -> Optional[Project]:
    """Loyihani yangilash."""
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        return None
    # Pydantic v2 model_dump yoki dict
    if hasattr(project_data, 'model_dump'):
        update_data = project_data.model_dump(exclude_unset=True)
    else:
        update_data = {k: v for k, v in project_data.items() if v is not None}

    for field, value in update_data.items():
        if hasattr(db_project, field) and value is not None:
            setattr(db_project, field, value)

    db.commit()
    db.refresh(db_project)
    return db_project


def delete_project(db: Session, project_id: int) -> bool:
    """Loyihani o'chirish."""
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        return False
    db.delete(db_project)
    db.commit()
    return True


# ============================================================
# RETURN ITEM CRUD
# ============================================================

from models import ReturnItem, ReturnReason
from schemas import ReturnItemCreate


def create_return_item(db: Session, data: ReturnItemCreate) -> ReturnItem:
    """Yangi qaytarishni bazaga qo'shadi."""
    try:
        reason_enum = ReturnReason(data.reason)
    except ValueError:
        reason_enum = ReturnReason.DEFECT

    item = ReturnItem(
        order_id=data.order_id,
        item_name=data.item_name,
        quantity=data.quantity,
        unit=data.unit,
        reason=reason_enum,
        refund_amount=data.refund_amount,
        is_refunded=False,
        notes=data.notes
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_return_items(db: Session, order_id: Optional[int] = None) -> List:
    """Barcha qaytarishlar yoki bitta buyurtma bo'yicha."""
    query = db.query(ReturnItem)
    if order_id:
        query = query.filter(ReturnItem.order_id == order_id)
    return query.order_by(ReturnItem.returned_at.desc()).all()


def get_return_item(db: Session, return_id: int) -> Optional[ReturnItem]:
    return db.query(ReturnItem).filter(ReturnItem.id == return_id).first()


def mark_refunded(db: Session, return_id: int) -> Optional[ReturnItem]:
    """Qaytarishni 'to'landi' deb belgilaydi."""
    item = get_return_item(db, return_id)
    if not item:
        return None
    item.is_refunded = True
    db.commit()
    db.refresh(item)
    return item


def delete_return_item(db: Session, return_id: int) -> bool:
    item = get_return_item(db, return_id)
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


def get_return_stats(db: Session) -> dict:
    """Qaytarishlar statistikasi."""
    all_returns = db.query(ReturnItem).all()
    total_count = len(all_returns)
    total_refund = sum(float(r.refund_amount) for r in all_returns)
    pending_refund = sum(float(r.refund_amount) for r in all_returns if not r.is_refunded)

    from models import ReturnReason
    by_reason = {}
    for r in ReturnReason:
        by_reason[r.value] = sum(1 for i in all_returns if i.reason == r)

    return {
        "total_count": total_count,
        "total_refund": total_refund,
        "pending_refund": pending_refund,
        "by_reason": by_reason
    }


# ============================================================
# PAYMENT — To'lovlar CRUD
# ============================================================

from models import Payment, PaymentType, PaymentMethod, PaymentStatus
from schemas import PaymentCreate


def _update_order_payment_status(db: Session, order: Order) -> None:
    """Buyurtmaning to'lov holatini yangilaydi.
    Qarz to'liq to'lansa — avtomatik arxivga o'tkazadi."""
    agreed = float(order.agreed_amount or order.total_amount or 0)
    paid = sum(float(p.amount or 0) for p in (order.payments or []))

    if paid <= 0:
        order.payment_status = PaymentStatus.UNPAID
        order.is_archived = False
        order.closed_at = None
    elif paid < agreed:
        order.payment_status = PaymentStatus.PARTIAL
        order.is_archived = False
        order.closed_at = None
    else:
        # To'liq to'landi — avtomatik yopish
        order.payment_status = PaymentStatus.PAID
        order.is_archived = True
        if not order.closed_at:
            order.closed_at = datetime.utcnow()


def create_payment(db: Session, payment_data: PaymentCreate) -> Payment:
    """Yangi to'lov qo'shish."""
    order = db.query(Order).filter(Order.id == payment_data.order_id).first()
    if not order:
        raise ValueError("Buyurtma topilmadi")

    # Enum ga aylantirish
    try:
        p_type = PaymentType(payment_data.payment_type)
    except ValueError:
        p_type = PaymentType.PARTIAL

    try:
        p_method = PaymentMethod(payment_data.payment_method)
    except ValueError:
        p_method = PaymentMethod.CASH

    db_payment = Payment(
        order_id=payment_data.order_id,
        amount=payment_data.amount,
        payment_type=p_type,
        payment_method=p_method,
        received_by=payment_data.received_by,
        notes=payment_data.notes
    )
    db.add(db_payment)
    db.flush()

    # Buyurtmani yangilash
    db.refresh(order)
    _update_order_payment_status(db, order)

    # Loyihaning to'langan summasini yangilash
    project = order.project
    if project:
        project.total_paid = sum(
            sum(float(p.amount or 0) for p in (o.payments or []))
            for o in (project.orders or [])
        )

    db.commit()
    db.refresh(db_payment)
    return db_payment


def get_payments(db: Session, order_id: Optional[int] = None) -> List[Payment]:
    """To'lovlar ro'yxati."""
    query = db.query(Payment)
    if order_id:
        query = query.filter(Payment.order_id == order_id)
    return query.order_by(Payment.paid_at.desc()).all()


def delete_payment(db: Session, payment_id: int) -> bool:
    """To'lovni o'chirish."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        return False

    order = payment.order
    db.delete(payment)
    db.flush()

    if order:
        db.refresh(order)
        _update_order_payment_status(db, order)
        project = order.project
        if project:
            project.total_paid = sum(
                sum(float(p.amount or 0) for p in (o.payments or []))
                for o in (project.orders or [])
            )

    db.commit()
    return True


def update_order_agreed_amount(db: Session, order_id: int, agreed_amount: float) -> Optional[Order]:
    """Kelishilgan summani (chegirmadan keyingi narx) yangilash."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return None

    total = float(order.total_amount or 0)
    order.agreed_amount = agreed_amount

    # Chegirma foizini hisoblash
    if total > 0 and agreed_amount < total:
        order.discount_percent = round((total - agreed_amount) / total * 100, 2)
    else:
        order.discount_percent = 0.0

    _update_order_payment_status(db, order)
    db.commit()
    db.refresh(order)
    return order


def get_debt_stats(db: Session) -> dict:
    """Qarzdorlik statistikasi — dashboard uchun."""
    orders = db.query(Order).filter(Order.is_archived == False).all()

    total_agreed = 0.0
    total_paid = 0.0
    debt_orders = []

    for o in orders:
        agreed = float(o.agreed_amount or o.total_amount or 0)
        paid = sum(float(p.amount or 0) for p in (o.payments or []))
        debt = max(agreed - paid, 0)

        total_agreed += agreed
        total_paid += paid

        if debt > 0:
            days_passed = (datetime.utcnow() - o.created_at).days if o.created_at else 0
            debt_orders.append({
                "order_id": o.id,
                "order_number": o.order_number,
                "client_name": o.project.client_name if o.project else "—",
                "project_name": o.project.project_name if o.project else "—",
                "agreed_amount": agreed,
                "paid_amount": paid,
                "debt_amount": debt,
                "payment_status": o.payment_status.value if o.payment_status else "unpaid",
                "days_passed": days_passed,
                "is_overdue": days_passed > 30,
                "created_at": o.created_at.isoformat() if o.created_at else None
            })

    debt_orders.sort(key=lambda x: x["debt_amount"], reverse=True)

    # Bugungi to'lovlar
    today = datetime.utcnow().date()
    today_payments = db.query(Payment).all()
    today_sum = sum(
        float(p.amount or 0) for p in today_payments
        if p.paid_at and p.paid_at.date() == today
    )

    return {
        "total_agreed": total_agreed,
        "total_paid": total_paid,
        "total_debt": total_agreed - total_paid,
        "debt_orders_count": len(debt_orders),
        "overdue_count": sum(1 for d in debt_orders if d["is_overdue"]),
        "today_payments": today_sum,
        "debt_orders": debt_orders[:20]
    }


# ============================================================
# DRAFT — Qoralama buyurtmalar
# ============================================================

def activate_draft_order(db: Session, order_id: int) -> dict:
    """Qoralama buyurtmani jarayonga oladi — ombordan xomashyo yechiladi."""
    import services

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    if order.status != OrderStatus.DRAFT:
        return {"success": False, "message": "Bu buyurtma qoralama emas"}

    # Xomashyo yetarliligini tekshiramiz
    check = services.check_inventory_for_order(db, order)
    if not check["enough"]:
        return {
            "success": False,
            "message": "Xomashyo yetishmayapti!",
            "shortages": check["shortages"]
        }

    # Ombordan penoplast yechamiz
    log = services.deduct_inventory_for_order(db, order)

    # Rejalashtirilgan loy bo'lsa — uni ham yechamiz
    planned_loy = services._get_planned_loy(order)
    if planned_loy > 0:
        loy_log = services.deduct_loy_ingredients(db, order, planned_loy)
        log.extend(loy_log)

    order.status = OrderStatus.IN_PROGRESS
    db.commit()
    db.refresh(order)

    return {
        "success": True,
        "message": "Buyurtma jarayonga olindi!",
        "inventory_log": log
    }


# ============================================================
# BUYURTMANI TAHRIRLASH (ombor farq bo'yicha to'g'rilanadi)
# ============================================================

def update_order_full(db: Session, order_id: int, order_data) -> dict:
    """Buyurtmani to'liq yangilaydi:
    - Detallarni almashtiradi
    - Omborni faqat FARQ miqdorida to'g'rilaydi
    - Buyurtma raqami, to'lovlar, sana saqlanadi
    """
    import services

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    if order.status == OrderStatus.READY:
        return {"success": False, "message": "Tayyor buyurtmani tahrirlab bo'lmaydi"}

    # 1) Eski detallarni snapshot qilamiz (ombor hisobi uchun)
    old_snapshot = [{
        "category": i.category,
        "width": i.width,
        "thickness": i.thickness,
        "length": i.length,
        "quantity": float(i.quantity or 1),
        "unit_price": float(i.unit_price or 0),
        "penoplast_id": i.penoplast_id
    } for i in order.items]

    new_snapshot = [{
        "category": it.category,
        "width": it.width,
        "thickness": it.thickness,
        "length": it.length,
        "quantity": float(it.quantity or 1),
        "unit_price": float(it.unit_price or 0),
        "penoplast_id": getattr(it, 'penoplast_id', None)
    } for it in order_data.items]

    is_draft = order.status == OrderStatus.DRAFT

    # 2) Qoralama bo'lmasa — xomashyo yetishini tekshiramiz
    if not is_draft:
        check = services.check_inventory_diff(db, old_snapshot, new_snapshot)
        if not check["enough"]:
            return {
                "success": False,
                "message": "Xomashyo yetishmayapti!",
                "shortages": check["shortages"]
            }

    # 3) Eski detallarni o'chiramiz
    for i in list(order.items):
        db.delete(i)
    db.flush()

    # 4) Yangi detallarni qo'shamiz
    total_amount = 0
    for item_data in order_data.items:
        item_total = float(item_data.unit_price or 0) * float(item_data.quantity or 1)
        total_amount += item_total
        db.add(OrderItem(
            order_id=order.id,
            name=item_data.name,
            category=item_data.category,
            width=item_data.width,
            thickness=item_data.thickness,
            length=item_data.length,
            quantity=item_data.quantity,
            is_coated=item_data.is_coated,
            recipe_id=order_data.recipe_id,
            penoplast_id=getattr(item_data, 'penoplast_id', None),
            price_per_m3=getattr(item_data, 'price_per_m3', None),
            unit_price=item_data.unit_price,
            total_price=item_total,
            notes=item_data.notes
        ))

    # 5) Buyurtma ma'lumotlarini yangilaymiz
    order.master_id = order_data.master_id
    if getattr(order_data, 'deadline', None):
        order.deadline = order_data.deadline
    order.total_amount = total_amount

    agreed = getattr(order_data, 'agreed_amount', None)
    order.agreed_amount = agreed if agreed else total_amount
    if total_amount > 0 and float(order.agreed_amount) < total_amount:
        order.discount_percent = round(
            (total_amount - float(order.agreed_amount)) / total_amount * 100, 2)
    else:
        order.discount_percent = 0.0

    db.flush()

    # 6) Omborni farq bo'yicha to'g'rilaymiz (qoralama emas bo'lsa)
    inventory_log = []
    if not is_draft:
        inventory_log = services.adjust_inventory_diff(db, old_snapshot, new_snapshot)

    # 7) To'lov holatini qayta hisoblaymiz
    db.refresh(order)
    _update_order_payment_status(db, order)

    db.commit()
    db.refresh(order)

    return {
        "success": True,
        "message": "Buyurtma yangilandi!",
        "inventory_log": inventory_log,
        "total_amount": float(order.total_amount or 0),
        "agreed_amount": float(order.agreed_amount or 0),
        "paid_amount": order.paid_amount,
        "debt_amount": order.debt_amount
    }


def update_order_loy(db: Session, order_id: int, new_loy: float) -> dict:
    """Loy rejasini o'zgartiradi — ombor farq bo'yicha to'g'rilanadi."""
    import services

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    old_loy = services._get_planned_loy(order)

    log = []
    if order.status != OrderStatus.DRAFT:
        log = services.adjust_loy_diff(db, order, old_loy, new_loy)

    services._set_planned_loy(order, new_loy)
    db.commit()

    return {
        "success": True,
        "old_loy": old_loy,
        "new_loy": new_loy,
        "inventory_log": log
    }
