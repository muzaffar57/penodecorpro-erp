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

from models import Project, Order, OrderItem, ProjectStatus, OrderStatus, OrderType, FinishedProduct, StockSource
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
            finished_product_id=getattr(item_data, 'finished_product_id', None),
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

    db.flush()

    # Tayyor mahsulotlardan yechamiz (qoralama bo'lmasa)
    if not is_draft:
        _take_finished_for_order(db, db_order)

    db.commit()
    db.refresh(db_order)
    return db_order


def _fp_item_qty(item) -> float:
    """Detalning tayyor mahsulotdan olinadigan miqdori."""
    cat = (item.category or '').lower()
    if cat == 'profil':
        return float(item.length or 0)
    return float(item.quantity or 0)


def _take_finished_for_order(db: Session, order) -> list:
    """Buyurtmadagi tayyor mahsulot detallarini ombordan yechadi."""
    log = []
    for it in order.items:
        fpid = getattr(it, 'finished_product_id', None)
        if not fpid:
            continue
        qty = _fp_item_qty(it)
        if qty <= 0:
            continue
        fp = db.query(FinishedProduct).filter(FinishedProduct.id == fpid).first()
        if not fp:
            continue
        fp.quantity = max(0, float(fp.quantity or 0) - qty)
        log.append(f"🏭 {fp.name}: -{qty:g} {fp.unit} (tayyor mahsulotdan)")
    if log:
        db.flush()
    return log


def _return_finished_for_order(db: Session, order) -> list:
    """Buyurtma o'chirilganda tayyor mahsulotlarni qaytaradi."""
    log = []
    for it in order.items:
        fpid = getattr(it, 'finished_product_id', None)
        if not fpid:
            continue
        qty = _fp_item_qty(it)
        if qty <= 0:
            continue
        fp = db.query(FinishedProduct).filter(FinishedProduct.id == fpid).first()
        if not fp:
            continue
        fp.quantity = float(fp.quantity or 0) + qty
        log.append(f"🏭 {fp.name}: +{qty:g} {fp.unit} qaytarildi")
    if log:
        db.flush()
    return log


def _adjust_finished_diff(db: Session, old_items, new_items) -> list:
    """Tayyor mahsulot farqini to'g'rilaydi."""
    def _group(items):
        out = {}
        for d in items:
            fpid = d.get('finished_product_id') if isinstance(d, dict) else getattr(d, 'finished_product_id', None)
            if not fpid:
                continue
            cat = (d.get('category') if isinstance(d, dict) else d.category) or ''
            if cat.lower() == 'profil':
                q = float((d.get('length') if isinstance(d, dict) else d.length) or 0)
            else:
                q = float((d.get('quantity') if isinstance(d, dict) else d.quantity) or 0)
            out[fpid] = out.get(fpid, 0.0) + q
        return out

    old_g = _group(old_items)
    new_g = _group(new_items)
    log = []

    for fpid in set(old_g) | set(new_g):
        diff = new_g.get(fpid, 0.0) - old_g.get(fpid, 0.0)
        if abs(diff) < 0.001:
            continue
        fp = db.query(FinishedProduct).filter(FinishedProduct.id == fpid).first()
        if not fp:
            continue
        if diff > 0:
            fp.quantity = max(0, float(fp.quantity or 0) - diff)
            log.append(f"🏭 {fp.name}: -{diff:g} {fp.unit}")
        else:
            fp.quantity = float(fp.quantity or 0) + abs(diff)
            log.append(f"🏭 {fp.name}: +{abs(diff):g} {fp.unit} qaytdi")

    if log:
        db.flush()
    return log


def check_finished_for_order(db: Session, items) -> dict:
    """Tayyor mahsulot yetadimi — tekshiradi."""
    shortages = []
    need = {}

    for it in items:
        fpid = getattr(it, 'finished_product_id', None)
        if not fpid:
            continue
        cat = (it.category or '').lower()
        qty = float(it.length or 0) if cat == 'profil' else float(it.quantity or 0)
        if qty <= 0:
            continue
        need[fpid] = need.get(fpid, 0.0) + qty

    for fpid, qty in need.items():
        fp = db.query(FinishedProduct).filter(FinishedProduct.id == fpid).first()
        if not fp:
            shortages.append("Tayyor mahsulot topilmadi")
            continue
        if float(fp.quantity or 0) < qty - 0.001:
            shortages.append(
                f"🏭 {fp.name}: omborda {float(fp.quantity):g} {fp.unit}, kerak {qty:g} {fp.unit}"
            )

    return {"enough": len(shortages) == 0, "shortages": shortages}


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

    # Topshirilgandan kam qilib bo'lmaydi
    delivered = db_item.delivered_qty
    if delivered > 0.001:
        cat = (item_data.get('category') or db_item.category or '').lower()
        new_qty = float(item_data.get('length') or db_item.length or 0) if cat == 'profil' \
                  else float(item_data.get('quantity') or db_item.quantity or 0)
        if new_qty < delivered - 0.001:
            return None

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
    """Detal o'chirish — xomashyo omborga qaytariladi.
    Topshirilgan detalni o'chirib bo'lmaydi."""
    import services

    db_item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not db_item:
        return False

    # Topshirilgan bo'lsa — o'chirib bo'lmaydi
    if db_item.delivered_qty > 0.001:
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
    """Yangi qaytarishni bazaga qo'shadi.
    to_stock=True bo'lsa — tayyor mahsulotlar omboriga ham tushadi."""
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
    db.flush()

    # Tayyor mahsulotlar omboriga qo'shamiz (brak bo'lmasa)
    to_stock = getattr(data, 'to_stock', True)
    if to_stock and reason_enum != ReturnReason.DEFECT:
        oi = None
        oi_id = getattr(data, 'order_item_id', None)
        if oi_id:
            oi = db.query(OrderItem).filter(OrderItem.id == oi_id).first()
        if not oi:
            # Nom bo'yicha topamiz
            oi = db.query(OrderItem).filter(
                OrderItem.order_id == data.order_id,
                OrderItem.name == data.item_name
            ).first()

        if oi:
            fp = add_returned_to_stock(
                db, oi, float(data.quantity), reason_enum.value,
                order_id=data.order_id,
                notes=f"{data.notes or ''}".strip() or None
            )
            if fp:
                print(f"✓ Tayyor mahsulotlar omboriga: {fp.name} +{data.quantity} {fp.unit}")

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


def get_delivery_stats(db: Session) -> dict:
    """Yetkazish statistikasi — dashboard uchun."""
    orders = db.query(Order).filter(
        Order.status.notin_([OrderStatus.DRAFT, OrderStatus.CANCELLED])
    ).all()

    partial = []
    not_started = 0
    fully = 0

    for o in orders:
        pct = o.delivery_percent
        if pct >= 100:
            fully += 1
        elif pct > 0:
            partial.append({
                "order_id": o.id,
                "order_number": o.order_number,
                "client_name": o.project.client_name if o.project else "—",
                "percent": pct,
                "items_pending": sum(1 for i in o.items if i.remaining_qty > 0.001),
                "debt_amount": o.debt_amount
            })
        else:
            not_started += 1

    partial.sort(key=lambda x: x["percent"], reverse=True)

    return {
        "fully_delivered": fully,
        "partial_count": len(partial),
        "not_started": not_started,
        "partial_orders": partial[:15]
    }


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

    # Tayyor mahsulotlarni yechamiz
    log.extend(_take_finished_for_order(db, order))

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
        "penoplast_id": i.penoplast_id,
        "price_per_m3": float(i.price_per_m3) if i.price_per_m3 else None,
        "finished_product_id": i.finished_product_id
    } for i in order.items]

    new_snapshot = [{
        "category": it.category,
        "width": it.width,
        "thickness": it.thickness,
        "length": it.length,
        "quantity": float(it.quantity or 1),
        "unit_price": float(it.unit_price or 0),
        "penoplast_id": getattr(it, 'penoplast_id', None),
        "price_per_m3": getattr(it, 'price_per_m3', None),
        "finished_product_id": getattr(it, 'finished_product_id', None)
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

    # 3) TOPSHIRISH TEKSHIRUVI — topshirilgandan kam qilib bo'lmaydi
    old_items = list(order.items)
    delivery_errors = []

    def _qty_of(it_data):
        """Yangi detal miqdori (profil — metr, qolganlar — dona)."""
        cat = (it_data.category or '').lower()
        if cat == 'profil':
            return float(it_data.length or 0)
        return float(it_data.quantity or 0)

    # Eski detallarni yangilar bilan moslashtiramiz (nom + tur bo'yicha)
    matched = {}       # old_item.id -> new_item_data
    used_new = set()

    for oi in old_items:
        key = ((oi.name or '').strip().lower(), (oi.category or '').lower())
        for idx, nd in enumerate(order_data.items):
            if idx in used_new:
                continue
            nkey = ((nd.name or '').strip().lower(), (nd.category or '').lower())
            if key == nkey:
                matched[oi.id] = nd
                used_new.add(idx)
                break

    # Tekshiramiz
    for oi in old_items:
        delivered = oi.delivered_qty
        if delivered <= 0.001:
            continue          # topshirilmagan — hech qanday cheklov yo'q

        nd = matched.get(oi.id)
        if nd is None:
            delivery_errors.append(
                f"«{oi.name}» — {delivered:g} {oi.delivery_unit} topshirilgan, o'chirib bo'lmaydi"
            )
            continue

        new_qty = _qty_of(nd)
        if new_qty < delivered - 0.001:
            delivery_errors.append(
                f"«{oi.name}» — {delivered:g} {oi.delivery_unit} topshirilgan, "
                f"{new_qty:g} qilib bo'lmaydi (kamida {delivered:g})"
            )

    if delivery_errors:
        return {
            "success": False,
            "message": "Topshirilgan miqdordan kam qilib bo'lmaydi!",
            "shortages": delivery_errors
        }

    # 4) Detallarni yangilaymiz — topshirilganlarini SAQLAB
    total_amount = 0
    keep_ids = set()

    for oi in old_items:
        nd = matched.get(oi.id)
        if nd is None:
            # Yangi ro'yxatda yo'q — o'chiramiz (topshirilmagani tekshirildi)
            db.delete(oi)
            continue

        item_total = float(nd.unit_price or 0) * float(nd.quantity or 1)
        total_amount += item_total

        oi.width = nd.width
        oi.thickness = nd.thickness
        oi.length = nd.length
        oi.quantity = nd.quantity
        oi.is_coated = nd.is_coated
        oi.recipe_id = order_data.recipe_id
        oi.penoplast_id = getattr(nd, 'penoplast_id', None)
        oi.price_per_m3 = getattr(nd, 'price_per_m3', None)
        oi.finished_product_id = getattr(nd, 'finished_product_id', None)
        oi.unit_price = nd.unit_price
        oi.total_price = item_total
        oi.notes = nd.notes
        keep_ids.add(oi.id)

    # Yangi qo'shilgan detallar
    for idx, nd in enumerate(order_data.items):
        if idx in used_new:
            continue
        item_total = float(nd.unit_price or 0) * float(nd.quantity or 1)
        total_amount += item_total
        db.add(OrderItem(
            order_id=order.id,
            name=nd.name,
            category=nd.category,
            width=nd.width,
            thickness=nd.thickness,
            length=nd.length,
            quantity=nd.quantity,
            is_coated=nd.is_coated,
            recipe_id=order_data.recipe_id,
            penoplast_id=getattr(nd, 'penoplast_id', None),
            price_per_m3=getattr(nd, 'price_per_m3', None),
            finished_product_id=getattr(nd, 'finished_product_id', None),
            unit_price=nd.unit_price,
            total_price=item_total,
            notes=nd.notes
        ))

    # 5) Buyurtma ma'lumotlarini yangilaymiz
    order.master_id = order_data.master_id
    if getattr(order_data, 'deadline', None):
        order.deadline = order_data.deadline

    old_total = float(order.total_amount or 0)
    old_discount_pct = float(order.discount_percent or 0)
    order.total_amount = total_amount

    agreed = getattr(order_data, 'agreed_amount', None)

    if agreed:
        # Xodim qo'lda summa kiritdi — shuni olamiz
        order.agreed_amount = agreed
    elif old_discount_pct > 0 and abs(total_amount - old_total) > 0.01:
        # Jami o'zgardi, chegirma foizi saqlanadi
        order.agreed_amount = round(total_amount * (1 - old_discount_pct / 100))
    else:
        order.agreed_amount = total_amount

    # Chegirma foizini qayta hisoblaymiz
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
        # Tayyor mahsulot farqi
        inventory_log.extend(_adjust_finished_diff(db, old_snapshot, new_snapshot))

    # 7) To'lov holatini qayta hisoblaymiz
    db.refresh(order)
    _update_order_payment_status(db, order)

    # 8) Yetkazish holatini qayta hisoblaymiz
    #    (miqdor oshsa "Yetkazildi" dan qaytadi, kamaysa aksincha)
    if order.deliveries:
        if order.is_fully_delivered:
            if order.status not in (OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.DRAFT):
                order.status = OrderStatus.DELIVERED
        elif order.status == OrderStatus.DELIVERED:
            order.status = OrderStatus.IN_PROGRESS

    db.commit()
    db.refresh(order)

    return {
        "success": True,
        "message": "Buyurtma yangilandi!",
        "inventory_log": inventory_log,
        "delivery_percent": order.delivery_percent,
        "total_amount": float(order.total_amount or 0),
        "agreed_amount": float(order.agreed_amount or 0),
        "discount_percent": float(order.discount_percent or 0),
        "paid_amount": order.paid_amount,
        "debt_amount": order.debt_amount,
        "price_changed": {
            "old_total": old_total,
            "new_total": total_amount,
            "old_discount_pct": old_discount_pct,
            "new_discount_pct": float(order.discount_percent or 0),
            "auto_applied": (not agreed and old_discount_pct > 0 and abs(total_amount - old_total) > 0.01)
        }
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


# ============================================================
# DELIVERY — Yetkazishlar
# ============================================================

from models import Delivery, DeliveryItem
from schemas import DeliveryCreate


def create_delivery(db: Session, data: DeliveryCreate, delivered_by: str = None) -> dict:
    """Yangi yetkazish qo'shadi.
    Ombor tegilmaydi — bu faqat mijozga topshirish hisobi."""
    order = db.query(Order).filter(Order.id == data.order_id).first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    if order.status == OrderStatus.DRAFT:
        return {"success": False, "message": "Qoralama buyurtmani yetkazib bo'lmaydi"}

    if not data.items:
        return {"success": False, "message": "Kamida bitta detal kiriting"}

    # Tekshirish: qoldiqdan ko'p berilmasin
    errors = []
    valid_items = []
    for di in data.items:
        if di.quantity <= 0:
            continue
        oi = db.query(OrderItem).filter(
            OrderItem.id == di.order_item_id,
            OrderItem.order_id == order.id
        ).first()
        if not oi:
            continue
        remaining = oi.remaining_qty
        if di.quantity > remaining + 0.001:
            errors.append(
                f"{oi.name}: {di.quantity:g} {oi.delivery_unit} berilmoqchi, "
                f"lekin qoldi {remaining:g} {oi.delivery_unit}"
            )
            continue
        valid_items.append((oi, di.quantity))

    if errors:
        return {"success": False, "message": "Qoldiqdan ko'p berib bo'lmaydi!", "shortages": errors}

    if not valid_items:
        return {"success": False, "message": "Yetkazish uchun miqdor kiritilmagan"}

    # Yetkazish raqami: ORD-010-1/Y-2
    seq = db.query(Delivery).filter(Delivery.order_id == order.id).count() + 1
    delivery_number = f"{order.order_number}/Y-{seq}"

    db_delivery = Delivery(
        order_id=order.id,
        delivery_number=delivery_number,
        delivered_by=delivered_by,
        received_by=data.received_by,
        notes=data.notes
    )
    db.add(db_delivery)
    db.flush()

    for oi, qty in valid_items:
        db.add(DeliveryItem(
            delivery_id=db_delivery.id,
            order_item_id=oi.id,
            quantity=qty,
            unit=oi.delivery_unit
        ))

    db.flush()
    db.refresh(order)

    # Hammasi berilgan bo'lsa — status
    fully = order.is_fully_delivered
    if fully and order.status not in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        order.status = OrderStatus.DELIVERED
        if not order.completed_at:
            order.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(db_delivery)
    db.refresh(order)

    return {
        "success": True,
        "message": "Yetkazish saqlandi!",
        "delivery_id": db_delivery.id,
        "delivery_number": delivery_number,
        "delivery_percent": order.delivery_percent,
        "is_fully_delivered": fully,
        "order_status": order.status.value
    }


def get_deliveries(db: Session, order_id: int) -> List[Delivery]:
    """Buyurtmaning yetkazishlari."""
    return db.query(Delivery).filter(
        Delivery.order_id == order_id
    ).order_by(Delivery.delivered_at.desc()).all()


def get_delivery(db: Session, delivery_id: int) -> Optional[Delivery]:
    return db.query(Delivery).filter(Delivery.id == delivery_id).first()


def delete_delivery(db: Session, delivery_id: int) -> bool:
    """Yetkazishni o'chirish."""
    d = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not d:
        return False
    order = d.order
    db.delete(d)
    db.flush()

    # Status qayta hisoblanadi
    if order:
        db.refresh(order)
        if not order.is_fully_delivered and order.status == OrderStatus.DELIVERED:
            order.status = OrderStatus.READY

    db.commit()
    return True


def get_delivery_status(db: Session, order_id: int) -> dict:
    """Buyurtmaning yetkazish holati — har detal bo'yicha."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"error": "Buyurtma topilmadi"}

    items = []
    for it in order.items:
        ordered = it.order_qty_normalized
        delivered = it.delivered_qty
        items.append({
            "id": it.id,
            "name": it.name,
            "category": it.category,
            "unit": it.delivery_unit,
            "ordered": round(ordered, 2),
            "delivered": round(delivered, 2),
            "remaining": round(max(ordered - delivered, 0), 2),
            "percent": round(delivered / ordered * 100, 1) if ordered > 0 else 0,
            "is_done": (ordered - delivered) <= 0.001
        })

    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "client_name": order.project.client_name if order.project else None,
        "delivery_percent": order.delivery_percent,
        "is_fully_delivered": order.is_fully_delivered,
        "status": order.status.value,
        "items": items,
        "deliveries": [_delivery_dict(d) for d in
                       sorted(order.deliveries, key=lambda x: x.delivered_at or datetime.min, reverse=True)]
    }


def _delivery_dict(d) -> dict:
    """Yetkazishni dict ga aylantiradi — summasi bilan."""
    items = []
    dsum = 0.0
    for di in d.items:
        oi = di.order_item
        if not oi:
            continue
        ordered = oi.order_qty_normalized
        total_price = float(oi.total_price or 0)
        unit_p = (total_price / ordered) if ordered > 0 else 0.0
        line_sum = unit_p * float(di.quantity or 0)
        dsum += line_sum
        items.append({
            "order_item_id": di.order_item_id,
            "item_name": oi.name,
            "quantity": float(di.quantity),
            "unit": di.unit,
            "unit_price": round(unit_p),
            "sum": round(line_sum)
        })

    return {
        "id": d.id,
        "delivery_number": d.delivery_number,
        "short_number": (d.delivery_number or "").split('/')[-1],
        "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
        "delivered_by": d.delivered_by,
        "received_by": d.received_by,
        "notes": d.notes,
        "total_sum": round(dsum),
        "items": items
    }


# ============================================================
# FINISHED PRODUCT — Tayyor mahsulotlar ombori
# ============================================================

from models import FinishedProduct, StockSource
from schemas import ProduceCreate


def _fp_unit(category: str) -> str:
    """Profil va panel — metr, qolgani — dona."""
    return 'metr' if (category or '').lower() in ('profil', 'panel') else 'dona'


def _fp_qty(data) -> float:
    """Ishlab chiqarilayotgan miqdor."""
    cat = (data.category or '').lower()
    if cat == 'profil':
        return float(data.length or 0)
    return float(data.quantity or 0)


def produce_finished_product(db: Session, data: ProduceCreate, created_by: str = None) -> dict:
    """Ishlab chiqarish boshlanadi:
    - Penoplast DARHOL ombordan yechiladi (kesish boshlanadi)
    - Loy REJA sifatida saqlanadi — "Tayyor" bosilganda aniq miqdor yechiladi
    - Har ishlab chiqarish alohida yozuv — birlashtirilmaydi (loy hisobi aniq bo'lishi uchun)
    """
    import services
    from models import ProductionStatus

    qty = _fp_qty(data)
    if qty <= 0:
        return {"success": False, "message": "Miqdor kiritilmagan"}

    # Hajmni hisoblaymiz
    class _Tmp:
        pass
    tmp = _Tmp()
    tmp.category = data.category
    tmp.width = data.width
    tmp.thickness = data.thickness
    tmp.length = data.length
    tmp.quantity = data.quantity or 1
    tmp.unit_price = getattr(data, 'unit_price_for_volume', None) or data.unit_price
    tmp.penoplast_id = data.penoplast_id
    tmp.price_per_m3 = data.price_per_m3
    tmp.finished_product_id = None

    default_p = services.get_default_penoplast(db)
    volume = services._item_volume_m3(db, tmp, default_p)

    pid = data.penoplast_id or (default_p.id if default_p else None)

    # Penoplast yetadimi
    shortages = []
    if volume > 0 and pid:
        p = db.query(Inventory).filter(Inventory.id == pid).first()
        if p:
            vol_per_unit = float(p.volume_per_unit or 1.0)
            blocks = volume / vol_per_unit
            if float(p.stock_quantity) < blocks:
                shortages.append(
                    f"{p.item_name}: kerak {blocks:.1f} blok, qoldi {float(p.stock_quantity):.1f} blok"
                )
    if shortages:
        return {"success": False, "message": "Xomashyo yetishmayapti!", "shortages": shortages}

    log = []
    peno_cost = 0.0

    # Penoplastni DARHOL yechamiz
    if volume > 0 and pid:
        p = db.query(Inventory).filter(Inventory.id == pid).first()
        if p:
            vol_per_unit = float(p.volume_per_unit or 1.0)
            blocks = volume / vol_per_unit
            p.stock_quantity = max(0, float(p.stock_quantity) - blocks)
            peno_cost = blocks * float(p.price_per_unit or 0)
            log.append(f"{p.item_name}: -{blocks:.2f} blok")

    db.flush()

    # Har safar YANGI yozuv — bir xili bo'lsa ham birlashtirmaymiz,
    # chunki loy sarfi har birida boshqacha bo'lishi mumkin
    unit = _fp_unit(data.category)
    fp = FinishedProduct(
        name=data.name.strip(),
        category=data.category,
        width=data.width,
        thickness=data.thickness,
        is_coated=data.is_coated,
        quantity=qty,
        unit=unit,
        unit_price=data.unit_price,
        cost_price=peno_cost,
        source=StockSource.PRODUCED,
        penoplast_id=pid,
        volume_m3=volume,
        planned_loy_kg=data.loy_kg or 0,
        actual_loy_kg=None,
        recipe_id=data.recipe_id,
        production_status=ProductionStatus.IN_PROGRESS,
        created_by=created_by,
        notes=data.notes
    )
    db.add(fp)
    db.commit()
    db.refresh(fp)

    return {
        "success": True,
        "message": "Ishlab chiqarish boshlandi! Tayyor bo'lgach 'Tayyor' tugmasini bosing.",
        "product_id": fp.id,
        "name": fp.name,
        "quantity": float(fp.quantity),
        "unit": fp.unit,
        "volume_m3": round(volume, 4),
        "penoplast_cost": round(peno_cost),
        "planned_loy_kg": data.loy_kg or 0,
        "inventory_log": log
    }


def complete_production(db: Session, fp_id: int, actual_loy_kg: float) -> dict:
    """Ishlab chiqarishni yakunlaydi — haqiqiy loy sarfini yechadi."""
    import services
    from models import ProductionStatus

    fp = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()
    if not fp:
        return {"success": False, "message": "Topilmadi"}

    if fp.source != StockSource.PRODUCED:
        return {"success": False, "message": "Faqat ishlab chiqarilgan mahsulot yakunlanadi"}

    if fp.production_status == ProductionStatus.READY:
        return {"success": False, "message": "Bu mahsulot allaqachon tayyor deb belgilangan"}

    log = []
    loy_cost = 0.0

    if actual_loy_kg > 0:
        from models import Recipe
        recipe = db.query(Recipe).filter(Recipe.id == fp.recipe_id).first() if fp.recipe_id else None
        if not recipe:
            recipe = db.query(Recipe).first()

        loy_info = services.get_loy_cost_per_kg(db, recipe.id if recipe else None)
        loy_cost = actual_loy_kg * float(loy_info.get("cost_per_kg", 0))

        class _FakeOrder:
            def __init__(self, rid):
                class _It:
                    recipe_id = rid
                self.items = [_It()]
        fake = _FakeOrder(recipe.id if recipe else None)
        log.extend(services.deduct_loy_ingredients(db, fake, actual_loy_kg, use_stock=False))

    fp.actual_loy_kg = actual_loy_kg
    fp.cost_price = float(fp.cost_price or 0) + loy_cost
    fp.production_status = ProductionStatus.READY
    fp.finished_production_at = datetime.utcnow()

    db.commit()
    db.refresh(fp)

    revenue = float(fp.unit_price or 0) * float(fp.quantity or 0)
    total_cost = float(fp.cost_price or 0)
    profit = revenue - total_cost
    margin = (profit / revenue * 100) if revenue > 0 else 0

    return {
        "success": True,
        "message": "Tayyor deb belgilandi!",
        "product_id": fp.id,
        "name": fp.name,
        "planned_loy_kg": fp.planned_loy_kg,
        "actual_loy_kg": actual_loy_kg,
        "loy_cost": round(loy_cost),
        "total_cost": round(total_cost),
        "revenue": round(revenue),
        "profit": round(profit),
        "margin": round(margin, 1),
        "inventory_log": log
    }


def get_finished_products(db: Session, source: Optional[str] = None, only_available: bool = False) -> List[FinishedProduct]:
    """Tayyor mahsulotlar ro'yxati."""
    q = db.query(FinishedProduct)
    if source:
        try:
            q = q.filter(FinishedProduct.source == StockSource(source))
        except ValueError:
            pass
    if only_available:
        q = q.filter(FinishedProduct.quantity > 0)
    return q.order_by(FinishedProduct.source, FinishedProduct.name).all()


def get_finished_product(db: Session, fp_id: int) -> Optional[FinishedProduct]:
    return db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()


def update_finished_product(db: Session, fp_id: int, data: dict) -> Optional[FinishedProduct]:
    fp = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()
    if not fp:
        return None
    for k, v in data.items():
        if v is not None and hasattr(fp, k):
            setattr(fp, k, v)
    db.commit()
    db.refresh(fp)
    return fp


def delete_finished_product(db: Session, fp_id: int, return_to_stock: bool = False) -> bool:
    """Tayyor mahsulotni o'chirish.
    return_to_stock=True bo'lsa — xomashyo omborga qaytariladi."""
    import services
    from models import ProductionStatus

    fp = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()
    if not fp:
        return False

    if return_to_stock and fp.source == StockSource.PRODUCED:
        # Penoplast qaytadi
        if fp.penoplast_id and fp.volume_m3:
            p = db.query(Inventory).filter(Inventory.id == fp.penoplast_id).first()
            if p:
                vol_per_unit = float(p.volume_per_unit or 1.0)
                p.stock_quantity = float(p.stock_quantity) + (float(fp.volume_m3) / vol_per_unit)
        # Loy qaytadi — faqat "Tayyor" bo'lgan bo'lsa (haqiqiy sarf ma'lum)
        if fp.production_status == ProductionStatus.READY and fp.actual_loy_kg and fp.actual_loy_kg > 0:
            class _FakeOrder:
                def __init__(self, rid):
                    class _It:
                        recipe_id = rid
                    self.items = [_It()]
            services.return_loy_ingredients(db, _FakeOrder(fp.recipe_id), float(fp.actual_loy_kg))

    db.delete(fp)
    db.commit()
    return True


def add_returned_to_stock(db: Session, order_item, quantity: float, reason: str,
                          order_id: int = None, notes: str = None) -> Optional[FinishedProduct]:
    """Buyurtmadan qaytgan detalni tayyor mahsulotlar omboriga qo'shadi.
    Narx — buyurtmadagi narx."""
    if quantity <= 0 or not order_item:
        return None

    ordered = order_item.order_qty_normalized
    total_price = float(order_item.total_price or 0)
    unit_p = (total_price / ordered) if ordered > 0 else 0.0
    unit = order_item.delivery_unit

    # Bir xili bo'lsa birlashtiramiz
    existing = db.query(FinishedProduct).filter(
        FinishedProduct.name == order_item.name,
        FinishedProduct.source == StockSource.RETURNED,
        FinishedProduct.width == order_item.width,
        FinishedProduct.thickness == order_item.thickness,
        FinishedProduct.is_coated == order_item.is_coated,
        FinishedProduct.unit_price == unit_p,
    ).first()

    if existing:
        existing.quantity = float(existing.quantity or 0) + quantity
        db.commit()
        db.refresh(existing)
        return existing

    fp = FinishedProduct(
        name=order_item.name,
        category=order_item.category,
        width=order_item.width,
        thickness=order_item.thickness,
        is_coated=order_item.is_coated,
        quantity=quantity,
        unit=unit,
        unit_price=unit_p,
        cost_price=0,
        source=StockSource.RETURNED,
        from_order_id=order_id or order_item.order_id,
        return_reason=reason,
        penoplast_id=order_item.penoplast_id,
        notes=notes
    )
    db.add(fp)
    db.commit()
    db.refresh(fp)
    return fp


def search_finished_products(db: Session, query: str) -> List[dict]:
    """Nom bo'yicha tayyor mahsulot qidirish — buyurtmada taklif uchun."""
    q = (query or '').strip()
    if len(q) < 2:
        return []

    items = db.query(FinishedProduct).filter(
        FinishedProduct.quantity > 0,
        FinishedProduct.name.ilike(f"%{q}%")
    ).order_by(FinishedProduct.name).limit(10).all()

    return [{
        "id": fp.id,
        "name": fp.name,
        "category": fp.category,
        "width": fp.width,
        "thickness": fp.thickness,
        "is_coated": fp.is_coated,
        "quantity": float(fp.quantity),
        "unit": fp.unit,
        "unit_price": float(fp.unit_price or 0),
        "source": fp.source.value,
        "source_label": "♻️ Qaytgan" if fp.source == StockSource.RETURNED else "🏭 Tayyor",
        "notes": fp.notes,
    } for fp in items]


def take_from_finished_stock(db: Session, fp_id: int, quantity: float) -> dict:
    """Tayyor mahsulotdan miqdor olish (buyurtmaga)."""
    fp = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()
    if not fp:
        return {"success": False, "message": "Tayyor mahsulot topilmadi"}

    available = float(fp.quantity or 0)
    if quantity > available + 0.001:
        return {
            "success": False,
            "message": f"{fp.name}: omborda {available:g} {fp.unit} bor, {quantity:g} olib bo'lmaydi"
        }

    fp.quantity = available - quantity
    db.commit()
    return {"success": True, "remaining": float(fp.quantity)}


def return_to_finished_stock(db: Session, fp_id: int, quantity: float) -> bool:
    """Tayyor mahsulotga qaytarish (buyurtma o'chirilganda)."""
    fp = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()
    if not fp:
        return False
    fp.quantity = float(fp.quantity or 0) + quantity
    db.commit()
    return True


def get_finished_stats(db: Session) -> dict:
    """Tayyor mahsulotlar statistikasi."""
    from models import ProductionStatus

    items = db.query(FinishedProduct).filter(FinishedProduct.quantity > 0).all()

    produced = [i for i in items if i.source == StockSource.PRODUCED]
    returned = [i for i in items if i.source == StockSource.RETURNED]
    in_progress = [i for i in produced if i.production_status == ProductionStatus.IN_PROGRESS]

    def _val(lst):
        return sum(float(i.quantity or 0) * float(i.unit_price or 0) for i in lst)

    return {
        "produced_count": len(produced),
        "returned_count": len(returned),
        "in_progress_count": len(in_progress),
        "produced_value": round(_val(produced)),
        "returned_value": round(_val(returned)),
        "total_value": round(_val(items)),
    }
