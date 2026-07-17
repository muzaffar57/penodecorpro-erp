"""
PenoDecorPro ERP — CRUD operatsiyalari
========================================
CRUD = Create (yaratish), Read (o'qish), Update (yangilash), Delete (o'chirish).
Bu fayl bazaga yozish va o'qish funksiyalarini saqlaydi.
"""

from typing import List, Optional, Dict
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
        category=guess_category(item_data.item_name, is_peno),
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


def create_expense_transaction(db: Session, data, performed_by: Optional[str] = None, source: str = "manual"):
    """Yangi xarajat tranzaksiyasini yaratadi. Bu funksiya faqat YANGI ExpenseTransaction
    jadvaliga yozadi — mavjud MonthlyExpense yoki hisob-kitob logikasiga umuman tegmaydi."""
    from models import ExpenseTransaction
    tx = ExpenseTransaction(
        date=data.get("date") or datetime.utcnow(),
        category=data["category"],
        amount=data.get("amount", 0),
        notes=data.get("notes"),
        created_by=performed_by,
        source=source,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def get_expense_transactions(db: Session, year: Optional[int] = None, month: Optional[int] = None,
                              category: Optional[str] = None, limit: int = 200):
    """Xarajat tranzaksiyalari ro'yxati — faqat o'qish."""
    from models import ExpenseTransaction
    from sqlalchemy import extract
    q = db.query(ExpenseTransaction)
    if year:
        q = q.filter(extract('year', ExpenseTransaction.date) == year)
    if month:
        q = q.filter(extract('month', ExpenseTransaction.date) == month)
    if category:
        q = q.filter(ExpenseTransaction.category == category)
    return q.order_by(ExpenseTransaction.date.desc()).limit(limit).all()


def delete_expense_transaction(db: Session, tx_id: int) -> bool:
    from models import ExpenseTransaction
    tx = db.query(ExpenseTransaction).filter(ExpenseTransaction.id == tx_id).first()
    if not tx:
        return False
    db.delete(tx)
    db.commit()
    return True


def get_item_by_name(db: Session, name: str) -> Optional[Inventory]:
    """Nom bo'yicha xomashyoni topadi."""
    return db.query(Inventory).filter(Inventory.item_name == name).first()


def log_movement(db: Session, inventory_id: Optional[int], item_name: str, movement_type: str,
                  quantity: float, unit: Optional[str] = None, reason: Optional[str] = None,
                  order_id: Optional[int] = None, supplier_id: Optional[int] = None,
                  performed_by: Optional[str] = None, notes: Optional[str] = None):
    """Ombor harakati jurnaliga bitta yozuv qo'shadi.

    MUHIM: bu funksiya faqat LOG yozadi — hech qanday hisob-kitobga yoki
    stock_quantity qiymatiga ta'sir qilmaydi. Xato yuz bersa ham asosiy
    amalni to'xtatmaslik uchun try/except bilan o'ralgan."""
    from models import InventoryMovement
    try:
        if quantity is None or quantity == 0:
            return
        db.add(InventoryMovement(
            inventory_id=inventory_id, item_name=item_name, movement_type=movement_type,
            quantity=abs(float(quantity)), unit=unit, reason=reason,
            order_id=order_id, supplier_id=supplier_id,
            performed_by=performed_by, notes=notes
        ))
    except Exception:
        pass


def update_stock(db: Session, item_id: int, quantity_change: float, performed_by: Optional[str] = None, notes: Optional[str] = None) -> Optional[Inventory]:
    """Mahsulot qoldig'ini yangilaydi (musbat = qo'shish, manfiy = ayirish).
    Narxsiz oddiy tuzatish uchun (masalan inventarizatsiya). Xarid uchun
    purchase_stock() dan foydalaning — u narxni ham hisobga oladi."""
    db_item = get_item(db, item_id)
    if not db_item:
        return None
    new_qty = db_item.stock_quantity + quantity_change
    if new_qty < 0:
        new_qty = 0  # Manfiy bo'lmasin
    db_item.stock_quantity = new_qty
    log_movement(
        db, db_item.id, db_item.item_name,
        movement_type="in" if quantity_change > 0 else "out",
        quantity=quantity_change, unit=db_item.unit,
        reason=notes or "Qo'lda tuzatish (inventarizatsiya)", performed_by=performed_by
    )
    db.commit()
    db.refresh(db_item)
    return db_item


def guess_category(item_name: str, is_penoplast: bool = False) -> str:
    """Material nomidan kategoriyani taxmin qiladi.

    3 asosiy guruh:
    1) Penoplast — penoplast xomashyosi
    2) Kimyoviy qo'shimchalar — suyuq/kimyoviy moddalar (akril, pva, zagustitel, penogasitel)
    3) Qattiq qotishmalar — qum, mel, kroshka va shunga o'xshash quruq materiallar
    """
    name = (item_name or '').lower()
    if is_penoplast or 'penoplast' in name or 'penopleks' in name:
        return "Penoplast"
    if any(k in name for k in ['akril', 'pva', 'zagustitel', 'penogasitel', 'texanol', 'biosid', 'hpmc']):
        return "Kimyoviy qo'shimchalar"
    if any(k in name for k in ['qum', 'kroshka', "shag'al", 'mel', 'kvars', 'mikroklasit', 'mikrokalsit']):
        return "Qattiq qotishmalar"
    return "Boshqa"


def purchase_stock(db: Session, item_id: int, quantity: float, price_per_unit: float,
                   purchased_by: str = None, notes: str = None,
                   supplier_id: int = None, is_credit: bool = False,
                   volume_per_unit: float = None):
    """Ombor kirimi — xarid narxi bilan.
    O'rtacha vaznli narx hisoblanadi (eski qoldiq qayta baholanmaydi):

        yangi_narx = (eski_qty × eski_narx + yangi_qty × xarid_narxi) / (eski_qty + yangi_qty)

    Penoplast uchun volume_per_unit (1 blok necha m³) ham partiyadan partiyaga
    farq qilishi mumkin — shu sabab u ham xuddi shu tarzda o'rtacha vaznli hisoblanadi,
    aks holda tan narx/hajm hisob-kitobi noto'g'ri chiqib qoladi.

    is_credit=True bo'lsa — nasiya (keyin to'lash), Supplierga qarz sifatida yoziladi.
    supplier_id — kredit bo'lmasa ham saqlanadi (tarix uchun, "kimdan olganimiz" bilinsin).
    """
    from models import InventoryPurchase

    db_item = get_item(db, item_id)
    if not db_item:
        return None

    old_qty = float(db_item.stock_quantity or 0)
    old_price = float(db_item.price_per_unit or 0)
    old_volume = float(db_item.volume_per_unit or 1.0)

    total_qty = old_qty + quantity
    if total_qty > 0:
        weighted_price = (old_qty * old_price + quantity * price_per_unit) / total_qty
    else:
        weighted_price = price_per_unit

    db_item.stock_quantity = total_qty
    db_item.price_per_unit = round(weighted_price, 2)

    volume_changed = False
    if db_item.is_penoplast and volume_per_unit and volume_per_unit > 0:
        if abs(volume_per_unit - old_volume) > 0.001:
            volume_changed = True
        if total_qty > 0:
            weighted_volume = (old_qty * old_volume + quantity * volume_per_unit) / total_qty
        else:
            weighted_volume = volume_per_unit
        db_item.volume_per_unit = round(weighted_volume, 4)

    if not db_item.category:
        db_item.category = guess_category(db_item.item_name, db_item.is_penoplast)

    purchase = InventoryPurchase(
        inventory_id=db_item.id,
        item_name=db_item.item_name,
        quantity=quantity,
        unit=db_item.unit,
        price_per_unit=price_per_unit,
        total_amount=quantity * price_per_unit,
        purchased_by=purchased_by,
        notes=notes,
        supplier_id=supplier_id,
        is_credit=is_credit,
        category=db_item.category
    )
    db.add(purchase)
    supplier_name = None
    if supplier_id:
        from models import Supplier
        sup = db.query(Supplier).filter(Supplier.id == supplier_id).first()
        supplier_name = sup.name if sup else None
    log_movement(
        db, db_item.id, db_item.item_name, movement_type="in",
        quantity=quantity, unit=db_item.unit,
        reason=f"Yetkazib beruvchi: {supplier_name}" if supplier_name else "Xarid",
        supplier_id=supplier_id, performed_by=purchased_by, notes=notes
    )
    db.commit()
    db.refresh(db_item)

    return {
        "item": db_item,
        "old_price": old_price,
        "new_price": float(db_item.price_per_unit),
        "old_qty": old_qty,
        "purchase_total": quantity * price_per_unit,
        "old_volume": old_volume,
        "new_volume": float(db_item.volume_per_unit),
        "volume_changed": volume_changed
    }


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


def get_recipe_insights(db: Session, recipe_id: int) -> Dict:
    """Retsept uchun qo'shimcha ma'lumot — faqat ko'rsatish uchun, hech narsani o'zgartirmaydi.
    - cost_per_kg: 1 kg tayyor aralashma tannarxi (ombordagi joriy narxlar bo'yicha)
    - used_in: shu retseptni ishlatgan buyurtma detallari (nomi bo'yicha noyob)
    """
    from models import Recipe, Inventory, OrderItem, Order

    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        return {"cost_per_kg": 0, "used_in": []}

    ingredient_map = [
        ("akril", recipe.akril_kg), ("pva", recipe.pva_kg),
        ("kvars qum", recipe.qum_kg), ("travertin qum", recipe.travertin_qum_kg),
        ("kroshka", recipe.kroshka_kg), ("mel", recipe.shtukaturka_kg),
        ("zagustitel", recipe.zagustitel_kg), ("suv", recipe.suv_kg),
        ("penogasitel", recipe.penogasitel_kg),
    ]
    total_cost = 0.0
    for inv_name, kg in ingredient_map:
        if not kg or kg <= 0:
            continue
        inv_item = db.query(Inventory).filter(Inventory.item_name.ilike(f"%{inv_name}%")).first()
        if inv_item and inv_item.price_per_unit:
            total_cost += float(kg) * float(inv_item.price_per_unit)

    batch = float(recipe.batch_size_kg or 1)
    cost_per_kg = total_cost / batch if batch > 0 else 0

    items = db.query(OrderItem.name).join(Order, OrderItem.order_id == Order.id).filter(
        OrderItem.recipe_id == recipe_id
    ).distinct().limit(12).all()
    used_in = [i[0] for i in items]

    return {"cost_per_kg": round(cost_per_kg, 2), "used_in": used_in}


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
                        log_movement(
                            db, inv_item.id, inv_item.item_name, movement_type="out",
                            quantity=qty, unit=inv_item.unit,
                            reason=f"Buyurtma {db_order.order_number}", order_id=db_order.id
                        )

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
    to_stock=True bo'lsa — tayyor mahsulotlar omboriga ham tushadi.
    refund_amount kelmasa (masalan hodim narx ko'rmasdan yozganda) —
    server o'zi tan narx/sotuv narxdan hisoblab qo'yadi."""
    import services

    try:
        reason_enum = ReturnReason(data.reason)
    except ValueError:
        reason_enum = ReturnReason.DEFECT

    order_item = None
    oi_id = getattr(data, 'order_item_id', None)
    if oi_id:
        order_item = db.query(OrderItem).filter(OrderItem.id == oi_id).first()
    if not order_item:
        order_item = db.query(OrderItem).filter(
            OrderItem.order_id == data.order_id,
            OrderItem.name == data.item_name
        ).first()

    refund_amount = float(data.refund_amount or 0)
    if refund_amount <= 0 and order_item:
        ordered = order_item.order_qty_normalized
        if reason_enum == ReturnReason.DEFECT:
            # Brak — tan narx (xomashyo qiymati)
            unit_price = services.get_order_item_unit_cost(db, order_item.order, order_item)
        else:
            # Butun — sotuv narxi
            unit_price = (float(order_item.total_price or 0) / ordered) if ordered else 0
        refund_amount = round(unit_price * float(data.quantity or 0))

    item = ReturnItem(
        order_id=data.order_id,
        item_name=data.item_name,
        quantity=data.quantity,
        unit=data.unit,
        reason=reason_enum,
        refund_amount=refund_amount,
        is_refunded=False,
        notes=data.notes
    )
    db.add(item)
    db.flush()

    # Tayyor mahsulotlar omboriga qo'shamiz (brak bo'lmasa)
    to_stock = getattr(data, 'to_stock', True)
    if to_stock and reason_enum != ReturnReason.DEFECT:
        oi = order_item
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
    """Qaytarishlar statistikasi — jami va shu oy bo'yicha."""
    from datetime import datetime
    from models import ReturnReason

    all_returns = db.query(ReturnItem).all()
    total_count = len(all_returns)
    total_refund = sum(float(r.refund_amount) for r in all_returns)
    pending_refund = sum(float(r.refund_amount) for r in all_returns if not r.is_refunded)

    by_reason = {}
    for r in ReturnReason:
        by_reason[r.value] = sum(1 for i in all_returns if i.reason == r)

    # Brak qiymati — jami va shu oy
    brak_items = [r for r in all_returns if r.reason == ReturnReason.DEFECT]
    brak_total_value = sum(float(r.refund_amount or 0) for r in brak_items)

    now = datetime.utcnow()
    month_brak = [r for r in brak_items if r.returned_at and r.returned_at.year == now.year and r.returned_at.month == now.month]
    brak_month_value = sum(float(r.refund_amount or 0) for r in month_brak)
    brak_month_count = len(month_brak)

    whole_items = [r for r in all_returns if r.reason != ReturnReason.DEFECT]
    month_whole = [r for r in whole_items if r.returned_at and r.returned_at.year == now.year and r.returned_at.month == now.month]

    return {
        "total_count": total_count,
        "total_refund": total_refund,
        "pending_refund": pending_refund,
        "by_reason": by_reason,
        "brak_total_value": round(brak_total_value),
        "brak_total_count": len(brak_items),
        "brak_month_value": round(brak_month_value),
        "brak_month_count": brak_month_count,
        "whole_month_count": len(month_whole),
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
        notes=data.notes,
        transport_carrier=getattr(data, 'transport_carrier', None),
        transport_cost=getattr(data, 'transport_cost', 0) or 0,
        transport_payer=getattr(data, 'transport_payer', 'none') or 'none'
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
        "transport_carrier": d.transport_carrier,
        "transport_cost": float(d.transport_cost or 0),
        "transport_payer": d.transport_payer or "none",
        "company_transport_cost": d.company_transport_cost,
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
    loy_cost = 0.0

    # 1) Penoplastni DARHOL yechamiz
    if volume > 0 and pid:
        p = db.query(Inventory).filter(Inventory.id == pid).first()
        if p:
            vol_per_unit = float(p.volume_per_unit or 1.0)
            blocks = volume / vol_per_unit
            p.stock_quantity = max(0, float(p.stock_quantity) - blocks)
            peno_cost = blocks * float(p.price_per_unit or 0)
            log.append(f"{p.item_name}: -{blocks:.2f} blok")

    # 2) Loyni ham DARHOL yechamiz (bir marta so'raladi)
    loy_kg = float(data.loy_kg or 0)
    if loy_kg > 0:
        from models import Recipe
        recipe = None
        if data.recipe_id:
            recipe = db.query(Recipe).filter(Recipe.id == data.recipe_id).first()
        if not recipe:
            recipe = db.query(Recipe).first()

        loy_info = services.get_loy_cost_per_kg(db, recipe.id if recipe else None)
        loy_cost = loy_kg * float(loy_info.get("cost_per_kg", 0))

        class _FakeOrder:
            def __init__(self, rid):
                class _It:
                    recipe_id = rid
                self.items = [_It()]
        fake = _FakeOrder(recipe.id if recipe else None)
        log.extend(services.deduct_loy_ingredients(db, fake, loy_kg, use_stock=False))

    db.flush()

    total_cost = peno_cost + loy_cost

    # Har safar YANGI yozuv — birlashtirmaymiz (loy sarfi har birida boshqacha)
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
        cost_price=total_cost,
        source=StockSource.PRODUCED,
        penoplast_id=pid,
        volume_m3=volume,
        planned_loy_kg=loy_kg,
        actual_loy_kg=loy_kg,          # Darhol yechilgani uchun aniq
        recipe_id=data.recipe_id,
        production_status=ProductionStatus.IN_PROGRESS,
        created_by=created_by,
        notes=data.notes
    )
    db.add(fp)
    db.commit()
    db.refresh(fp)

    revenue = float(data.unit_price or 0) * qty
    profit = revenue - total_cost
    margin = (profit / revenue * 100) if revenue > 0 else 0

    return {
        "success": True,
        "message": "Ishlab chiqarish boshlandi!",
        "product_id": fp.id,
        "name": fp.name,
        "quantity": float(fp.quantity),
        "unit": fp.unit,
        "volume_m3": round(volume, 4),
        "penoplast_cost": round(peno_cost),
        "loy_cost": round(loy_cost),
        "total_cost": round(total_cost),
        "revenue": round(revenue),
        "profit": round(profit),
        "margin": round(margin, 1),
        "loy_kg": loy_kg,
        "inventory_log": log
    }


def complete_production(db: Session, fp_id: int, actual_loy_kg: float = 0) -> dict:
    """Ishlab chiqarishni yakunlaydi — mahsulot sotuvga tayyor.
    Xomashyo allaqachon yechilgan, bu faqat status o'zgartirish."""
    from models import ProductionStatus

    fp = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()
    if not fp:
        return {"success": False, "message": "Topilmadi"}

    if fp.source != StockSource.PRODUCED:
        return {"success": False, "message": "Faqat ishlab chiqarilgan mahsulot yakunlanadi"}

    if fp.production_status == ProductionStatus.READY:
        return {"success": False, "message": "Bu mahsulot allaqachon tayyor"}

    fp.production_status = ProductionStatus.READY
    fp.finished_production_at = datetime.utcnow()

    db.commit()
    db.refresh(fp)

    qty = float(fp.quantity or 0)
    revenue = float(fp.unit_price or 0) * qty
    total_cost = float(fp.cost_price or 0)
    profit = revenue - total_cost
    margin = (profit / revenue * 100) if revenue > 0 else 0

    # 1 birlik uchun tan narxi — qisman sotilganda foyda hisoblash uchun
    cost_per_unit = (total_cost / qty) if qty > 0 else 0

    return {
        "success": True,
        "message": "Sotuvga tayyor!",
        "product_id": fp.id,
        "name": fp.name,
        "quantity": qty,
        "unit": fp.unit,
        "loy_kg": float(fp.actual_loy_kg or 0),
        "total_cost": round(total_cost),
        "cost_per_unit": round(cost_per_unit),
        "revenue": round(revenue),
        "profit": round(profit),
        "margin": round(margin, 1)
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
        # Loy qaytadi (ishlab chiqarishda darhol yechilgan)
        if fp.actual_loy_kg and fp.actual_loy_kg > 0:
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


def add_to_production(db: Session, fp_id: int, add_qty: float) -> dict:
    """Mavjud tayyor mahsulotga miqdor qo'shadi.
    Penoplast va loy proporsional hisoblanib ombordan yechiladi.

    Masalan: 100 m uchun 1.2 m³ penoplast va 120 kg loy ketgan bo'lsa,
             +50 m qo'shilsa → 0.6 m³ penoplast va 60 kg loy yechiladi.
    """
    import services
    from models import Recipe

    fp = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()
    if not fp:
        return {"success": False, "message": "Topilmadi"}

    if add_qty <= 0:
        return {"success": False, "message": "Miqdor musbat bo'lishi kerak"}

    if fp.source != StockSource.PRODUCED:
        return {"success": False, "message": "Faqat ishlab chiqarilgan mahsulotga qo'shiladi"}

    base_qty = float(fp.quantity or 0)
    if base_qty <= 0:
        return {
            "success": False,
            "message": "Qoldiq 0 — proporsiya hisoblab bo'lmaydi. Yangi ishlab chiqarish yarating."
        }

    # Proporsiya: 1 birlik uchun qancha
    ratio = add_qty / base_qty
    add_volume = float(fp.volume_m3 or 0) * ratio
    add_loy = float(fp.actual_loy_kg or 0) * ratio

    # Xomashyo yetadimi
    shortages = []
    if add_volume > 0 and fp.penoplast_id:
        p = db.query(Inventory).filter(Inventory.id == fp.penoplast_id).first()
        if p:
            vol_per_unit = float(p.volume_per_unit or 1.0)
            blocks = add_volume / vol_per_unit
            if float(p.stock_quantity) < blocks:
                shortages.append(
                    f"{p.item_name}: kerak {blocks:.2f} blok, qoldi {float(p.stock_quantity):.2f} blok"
                )
    if shortages:
        return {"success": False, "message": "Xomashyo yetishmayapti!", "shortages": shortages}

    log = []
    peno_cost = 0.0
    loy_cost = 0.0

    # 1) Penoplast
    if add_volume > 0 and fp.penoplast_id:
        p = db.query(Inventory).filter(Inventory.id == fp.penoplast_id).first()
        if p:
            vol_per_unit = float(p.volume_per_unit or 1.0)
            blocks = add_volume / vol_per_unit
            p.stock_quantity = max(0, float(p.stock_quantity) - blocks)
            peno_cost = blocks * float(p.price_per_unit or 0)
            log.append(f"{p.item_name}: -{blocks:.2f} blok")

    # 2) Loy
    if add_loy > 0:
        recipe = db.query(Recipe).filter(Recipe.id == fp.recipe_id).first() if fp.recipe_id else None
        if not recipe:
            recipe = db.query(Recipe).first()

        loy_info = services.get_loy_cost_per_kg(db, recipe.id if recipe else None)
        loy_cost = add_loy * float(loy_info.get("cost_per_kg", 0))

        class _FakeOrder:
            def __init__(self, rid):
                class _It:
                    recipe_id = rid
                self.items = [_It()]
        fake = _FakeOrder(recipe.id if recipe else None)
        log.extend(services.deduct_loy_ingredients(db, fake, add_loy, use_stock=False))

    # 3) Mahsulotni yangilaymiz
    fp.quantity = base_qty + add_qty
    fp.volume_m3 = float(fp.volume_m3 or 0) + add_volume
    fp.actual_loy_kg = float(fp.actual_loy_kg or 0) + add_loy
    fp.planned_loy_kg = float(fp.planned_loy_kg or 0) + add_loy
    fp.cost_price = float(fp.cost_price or 0) + peno_cost + loy_cost

    db.commit()
    db.refresh(fp)

    return {
        "success": True,
        "message": f"+{add_qty:g} {fp.unit} qo'shildi",
        "product_id": fp.id,
        "name": fp.name,
        "added_qty": add_qty,
        "new_qty": float(fp.quantity),
        "unit": fp.unit,
        "add_volume": round(add_volume, 4),
        "add_loy": round(add_loy, 1),
        "add_cost": round(peno_cost + loy_cost),
        "inventory_log": log
    }


def reduce_production(db: Session, fp_id: int, reduce_qty: float, reason: str = None) -> dict:
    """Tayyor mahsulot miqdorini kamaytiradi (brak/singan).
    Xomashyo omborga QAYTARILMAYDI — tan narxi saqlanadi."""
    fp = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()
    if not fp:
        return {"success": False, "message": "Topilmadi"}

    if reduce_qty <= 0:
        return {"success": False, "message": "Miqdor musbat bo'lishi kerak"}

    current = float(fp.quantity or 0)
    if reduce_qty > current + 0.001:
        return {
            "success": False,
            "message": f"Omborda {current:g} {fp.unit} bor, {reduce_qty:g} ayirib bo'lmaydi"
        }

    fp.quantity = max(0, current - reduce_qty)

    # Izohga yozib qo'yamiz
    note = f"brak: -{reduce_qty:g}{fp.unit}"
    if reason:
        note += f" ({reason})"
    fp.notes = (fp.notes + " · " + note) if fp.notes else note

    db.commit()
    db.refresh(fp)

    # Yo'qotilgan qiymat
    lost_value = reduce_qty * float(fp.unit_price or 0)

    return {
        "success": True,
        "message": f"-{reduce_qty:g} {fp.unit} chiqarildi (brak)",
        "product_id": fp.id,
        "name": fp.name,
        "new_qty": float(fp.quantity),
        "unit": fp.unit,
        "lost_value": round(lost_value)
    }


def get_finished_profit(db: Session, fp_id: int) -> dict:
    """Tayyor mahsulot foydasi — to'liq tafsilot bilan."""
    import services

    fp = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()
    if not fp:
        return {"success": False, "message": "Topilmadi"}

    qty = float(fp.quantity or 0)
    unit_price = float(fp.unit_price or 0)
    revenue = qty * unit_price
    total_cost = float(fp.cost_price or 0)

    # Loy narxi
    loy_cost = 0.0
    loy_per_kg = 0.0
    recipe_name = None
    loy_kg = float(fp.actual_loy_kg or 0)
    if loy_kg > 0:
        info = services.get_loy_cost_per_kg(db, fp.recipe_id)
        loy_per_kg = float(info.get("cost_per_kg", 0))
        loy_cost = loy_kg * loy_per_kg
        recipe_name = info.get("recipe")

    peno_cost = max(total_cost - loy_cost, 0)
    profit = revenue - total_cost
    margin = (profit / revenue * 100) if revenue > 0 else 0

    return {
        "success": True,
        "id": fp.id,
        "name": fp.name,
        "quantity": qty,
        "unit": fp.unit,
        "unit_price": unit_price,
        "revenue": round(revenue),
        "penoplast_cost": round(peno_cost),
        "loy_kg": loy_kg,
        "loy_cost_per_kg": round(loy_per_kg),
        "loy_cost": round(loy_cost),
        "recipe": recipe_name,
        "total_cost": round(total_cost),
        "profit": round(profit),
        "margin": round(margin, 1),
        "cost_per_unit": round(total_cost / qty) if qty > 0 else 0,
        "profit_per_unit": round(profit / qty) if qty > 0 else 0,
        "volume_m3": float(fp.volume_m3 or 0),
        "source": fp.source.value,
        "production_status": fp.production_status.value if fp.production_status else None,
    }


# ============================================================
# INVENTORY PURCHASES — Xarid statistikasi
# ============================================================

def get_purchases(db: Session, limit: int = 100, item_id: int = None) -> List:
    """Xaridlar tarixi."""
    from models import InventoryPurchase
    q = db.query(InventoryPurchase)
    if item_id:
        q = q.filter(InventoryPurchase.inventory_id == item_id)
    return q.order_by(InventoryPurchase.purchased_at.desc()).limit(limit).all()


def get_purchase_stats(db: Session, year: int = None, month: int = None) -> dict:
    """Material bo'yicha xarid statistikasi — Moliya/Dashboard uchun.
    year/month berilmasa — joriy oy."""
    from models import InventoryPurchase
    from datetime import datetime as dt

    now = dt.utcnow()
    year = year or now.year
    month = month or now.month

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
            by_material[key] = {"name": key, "quantity": 0.0, "total": 0.0, "unit": p.unit, "category": p.category or "Boshqa"}
        by_material[key]["quantity"] += float(p.quantity)
        by_material[key]["total"] += float(p.total_amount)
        total += float(p.total_amount)

    items = sorted(by_material.values(), key=lambda x: x["total"], reverse=True)
    for it in items:
        it["avg_price"] = round(it["total"] / it["quantity"]) if it["quantity"] > 0 else 0
        it["total"] = round(it["total"])

    return {
        "year": year,
        "month": month,
        "total_amount": round(total),
        "purchase_count": len(purchases),
        "by_material": items
    }


def get_purchase_stats_range(db: Session, months: int = 6) -> dict:
    """Oxirgi N oy bo'yicha xarid tendensiyasi (dashboard grafik uchun)."""
    from models import InventoryPurchase
    from datetime import datetime as dt

    now = dt.utcnow()
    result = []
    y, m = now.year, now.month
    for _ in range(months):
        start = dt(y, m, 1)
        end = dt(y + 1, 1, 1) if m == 12 else dt(y, m + 1, 1)
        total = db.query(InventoryPurchase).filter(
            InventoryPurchase.purchased_at >= start,
            InventoryPurchase.purchased_at < end
        ).all()
        s = sum(float(p.total_amount) for p in total)
        result.append({"year": y, "month": m, "total": round(s)})
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return {"months": list(reversed(result))}


# ============================================================
# TRANSPORT EXPENSE — Kirish transporti
# ============================================================

from models import TransportExpense
from schemas import TransportExpenseCreate


def create_transport_expense(db: Session, data: TransportExpenseCreate, created_by: str = None) -> TransportExpense:
    """Kirish transporti xarajatini yozadi."""
    exp = TransportExpense(
        amount=data.amount,
        materials_note=data.materials_note,
        created_by=created_by,
        notes=data.notes
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def get_transport_expenses(db: Session, limit: int = 100) -> List[TransportExpense]:
    return db.query(TransportExpense).order_by(TransportExpense.expense_date.desc()).limit(limit).all()


def delete_transport_expense(db: Session, exp_id: int) -> bool:
    exp = db.query(TransportExpense).filter(TransportExpense.id == exp_id).first()
    if not exp:
        return False
    db.delete(exp)
    db.commit()
    return True


def get_transport_stats(db: Session, year: int = None, month: int = None) -> dict:
    """Transport xarajatlari statistikasi (kirish + chiqish) — joriy oy bo'yicha."""
    from models import Delivery
    from datetime import datetime as dt

    now = dt.utcnow()
    year = year or now.year
    month = month or now.month
    start = dt(year, month, 1)
    end = dt(year + 1, 1, 1) if month == 12 else dt(year, month + 1, 1)

    # Kirish transporti
    inbound = db.query(TransportExpense).filter(
        TransportExpense.expense_date >= start,
        TransportExpense.expense_date < end
    ).all()
    inbound_total = sum(float(e.amount) for e in inbound)

    # Chiqish transporti (kompaniya ulushi)
    deliveries = db.query(Delivery).filter(
        Delivery.delivered_at >= start,
        Delivery.delivered_at < end,
        Delivery.transport_cost > 0
    ).all()
    outbound_company = sum(d.company_transport_cost for d in deliveries)
    outbound_client = sum(d.client_transport_cost for d in deliveries)
    outbound_total = sum(float(d.transport_cost or 0) for d in deliveries)

    return {
        "year": year,
        "month": month,
        "inbound_total": round(inbound_total),
        "inbound_count": len(inbound),
        "outbound_total": round(outbound_total),
        "outbound_company": round(outbound_company),
        "outbound_client": round(outbound_client),
        "outbound_count": len(deliveries),
        "grand_total_company": round(inbound_total + outbound_company)
    }


# ============================================================
# EMPLOYEE — Moslashuvchan hodim to'lovi
# ============================================================

from models import Employee, PayType
from schemas import EmployeeCreate, EmployeeUpdate


def create_employee(db: Session, data: EmployeeCreate) -> Employee:
    try:
        pt = PayType(data.pay_type)
    except ValueError:
        pt = PayType.FIXED

    emp = Employee(
        name=data.name.strip(),
        position=data.position,
        pay_type=pt,
        fixed_amount=data.fixed_amount,
        percent_value=data.percent_value,
        per_unit_rate=data.per_unit_rate,
        per_unit_type=data.per_unit_type,
        notes=data.notes
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def get_employees(db: Session, only_active: bool = True) -> List[Employee]:
    q = db.query(Employee)
    if only_active:
        q = q.filter(Employee.is_active == True)
    return q.order_by(Employee.name).all()


def get_employee(db: Session, emp_id: int) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.id == emp_id).first()


def update_employee(db: Session, emp_id: int, data: EmployeeUpdate) -> Optional[Employee]:
    emp = get_employee(db, emp_id)
    if not emp:
        return None
    update_data = data.model_dump(exclude_unset=True)
    if "pay_type" in update_data:
        try:
            update_data["pay_type"] = PayType(update_data["pay_type"])
        except ValueError:
            del update_data["pay_type"]
    for k, v in update_data.items():
        setattr(emp, k, v)
    db.commit()
    db.refresh(emp)
    return emp


def delete_employee(db: Session, emp_id: int) -> bool:
    emp = get_employee(db, emp_id)
    if not emp:
        return False
    db.delete(emp)
    db.commit()
    return True


# ============================================================
# MASTER KPI — Yillik KPI (sotuvdan %, yil oxiri sovg'a)
# ============================================================

def update_master_kpi(db: Session, master_id: int, kpi_percent: float) -> Optional[Master]:
    m = db.query(Master).filter(Master.id == master_id).first()
    if not m:
        return None
    m.kpi_percent = kpi_percent
    db.commit()
    db.refresh(m)
    return m


def get_masters_kpi_report(db: Session, year: int) -> dict:
    """Har usta uchun yillik SOF FOYDA, KPI% va hisoblangan sovg'a."""
    import services
    from models import Order, OrderStatus
    from sqlalchemy import extract

    masters = db.query(Master).filter(Master.is_active == True).all()
    rows = []
    total_gift = 0.0

    for m in masters:
        orders = db.query(Order).filter(
            Order.master_id == m.id,
            Order.status == OrderStatus.READY,
            extract('year', Order.completed_at) == year
        ).all()

        yearly_sales = 0.0
        yearly_profit = 0.0
        for o in orders:
            yearly_sales += float(o.total_amount or 0)
            try:
                profit_data = services.calculate_order_profit(db, o.id)
                yearly_profit += float(profit_data.get("foyda", 0))
            except Exception:
                pass

        gift = yearly_profit * (m.kpi_percent or 0) / 100
        total_gift += gift

        rows.append({
            "id": m.id,
            "name": m.name,
            "kpi_percent": m.kpi_percent or 0,
            "yearly_sales": round(yearly_sales),
            "yearly_profit": round(yearly_profit),
            "orders_count": len(orders),
            "gift_amount": round(gift)
        })

    rows.sort(key=lambda x: x["gift_amount"], reverse=True)
    return {"year": year, "masters": rows, "total_gift": round(total_gift)}


# ============================================================
# SUPPLIER — Yetkazib beruvchilar va nasiya qarzi
# ============================================================

from models import Supplier, SupplierPayment, InventoryPurchase
from schemas import SupplierCreate, SupplierUpdate, SupplierPaymentCreate


def create_supplier(db: Session, data: SupplierCreate) -> Supplier:
    s = Supplier(name=data.name.strip(), phone=data.phone, notes=data.notes)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def get_suppliers(db: Session, only_active: bool = True) -> List[Supplier]:
    q = db.query(Supplier)
    if only_active:
        q = q.filter(Supplier.is_active == True)
    return q.order_by(Supplier.name).all()


def get_supplier(db: Session, supplier_id: int) -> Optional[Supplier]:
    return db.query(Supplier).filter(Supplier.id == supplier_id).first()


def update_supplier(db: Session, supplier_id: int, data: SupplierUpdate) -> Optional[Supplier]:
    s = get_supplier(db, supplier_id)
    if not s:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


def delete_supplier(db: Session, supplier_id: int, force: bool = False) -> dict:
    """Yetkazib beruvchini o'chiradi.
    Qarzi bo'lsa force=True bo'lmaguncha o'chirmaydi (xato qaytaradi).
    force=True bo'lsa — tarixi (xaridlar, to'lovlar) bilan birga butunlay o'chadi."""
    s = get_supplier(db, supplier_id)
    if not s:
        return {"success": False, "message": "Topilmadi"}

    debt_info = get_supplier_debt(db, supplier_id)
    if debt_info["debt"] > 0 and not force:
        return {
            "success": False,
            "message": f"Bu yetkazib beruvchida {debt_info['debt']:,.0f} so'm qarz bor".replace(",", " "),
            "has_debt": True,
            "debt": debt_info["debt"]
        }

    # Bog'liq xaridlarni supplier_id=NULL qilamiz (tarixi Omborxonada saqlanib qoladi,
    # lekin endi hech kimga bog'lanmaydi) — to'lovlarni esa o'chiramiz (faqat shu supplierga tegishli)
    db.query(InventoryPurchase).filter(InventoryPurchase.supplier_id == supplier_id).update(
        {"supplier_id": None}
    )
    db.query(SupplierPayment).filter(SupplierPayment.supplier_id == supplier_id).delete()

    db.delete(s)
    db.commit()
    return {"success": True}


def get_supplier_debt(db: Session, supplier_id: int) -> dict:
    """Yetkazib beruvchiga qancha qarzdorlik bor."""
    purchases = db.query(InventoryPurchase).filter(
        InventoryPurchase.supplier_id == supplier_id,
        InventoryPurchase.is_credit == True
    ).all()
    payments = db.query(SupplierPayment).filter(SupplierPayment.supplier_id == supplier_id).all()

    total_credit = sum(float(p.total_amount) for p in purchases)
    total_paid = sum(float(p.amount) for p in payments)
    debt = max(0, total_credit - total_paid)

    return {
        "total_credit": round(total_credit),
        "total_paid": round(total_paid),
        "debt": round(debt),
        "purchase_count": len(purchases)
    }


def get_suppliers_with_debt(db: Session) -> List[dict]:
    """Barcha yetkazib beruvchilar va ularning qarzdorligi + oxirgi xarid, oylik statistika."""
    from datetime import datetime as dt

    now = dt.utcnow()
    suppliers = get_suppliers(db, only_active=True)
    result = []
    for s in suppliers:
        debt_info = get_supplier_debt(db, s.id)

        all_purchases = db.query(InventoryPurchase).filter(
            InventoryPurchase.supplier_id == s.id
        ).order_by(InventoryPurchase.purchased_at.desc()).all()

        last_purchase_at = all_purchases[0].purchased_at.isoformat() if all_purchases else None

        month_purchases = [p for p in all_purchases
                           if p.purchased_at and p.purchased_at.year == now.year
                           and p.purchased_at.month == now.month]
        month_total = sum(float(p.total_amount) for p in month_purchases)

        result.append({
            "id": s.id,
            "name": s.name,
            "phone": s.phone,
            "notes": s.notes,
            "last_purchase_at": last_purchase_at,
            "month_count": len(month_purchases),
            "month_total": round(month_total),
            **debt_info
        })
    result.sort(key=lambda x: x["debt"], reverse=True)
    return result


def update_purchase(db: Session, purchase_id: int, data: dict) -> Optional[InventoryPurchase]:
    """Xarid yozuvini tahrirlaydi.
    DIQQAT: ombordagi joriy miqdor/o'rtacha narxni orqaga qaytarib hisoblamaydi —
    faqat tarixiy yozuv va qarz hisobi (u har safar yangidan hisoblanadi) to'g'rilanadi."""
    p = db.query(InventoryPurchase).filter(InventoryPurchase.id == purchase_id).first()
    if not p:
        return None

    if "quantity" in data and data["quantity"] is not None:
        p.quantity = data["quantity"]
    if "price_per_unit" in data and data["price_per_unit"] is not None:
        p.price_per_unit = data["price_per_unit"]
    if "is_credit" in data and data["is_credit"] is not None:
        p.is_credit = data["is_credit"]
    if "notes" in data:
        p.notes = data["notes"]

    p.total_amount = float(p.quantity) * float(p.price_per_unit)

    db.commit()
    db.refresh(p)
    return p


def delete_purchase(db: Session, purchase_id: int) -> bool:
    """Xarid yozuvini o'chiradi.
    DIQQAT: ombordagi joriy miqdor/o'rtacha narxni orqaga qaytarib hisoblamaydi."""
    p = db.query(InventoryPurchase).filter(InventoryPurchase.id == purchase_id).first()
    if not p:
        return False
    db.delete(p)
    db.commit()
    return True


def create_supplier_payment(db: Session, data: SupplierPaymentCreate, paid_by: str = None) -> SupplierPayment:
    """Yetkazib beruvchiga to'lov — bir nechta xaridni birdaniga yopishi mumkin."""
    p = SupplierPayment(
        supplier_id=data.supplier_id,
        amount=data.amount,
        paid_by=paid_by,
        notes=data.notes
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def get_supplier_history(db: Session, supplier_id: int, start_date=None, end_date=None) -> dict:
    """Yetkazib beruvchining xaridlar va to'lovlar tarixi.
    start_date/end_date berilsa — faqat shu oraliqdagi xaridlar qaytariladi
    (to'lovlar va umumiy qarz har doim to'liq hisoblanadi)."""
    q = db.query(InventoryPurchase).filter(InventoryPurchase.supplier_id == supplier_id)
    if start_date:
        q = q.filter(InventoryPurchase.purchased_at >= start_date)
    if end_date:
        from datetime import timedelta
        q = q.filter(InventoryPurchase.purchased_at < end_date + timedelta(days=1))
    purchases = q.order_by(InventoryPurchase.purchased_at.desc()).all()

    payments = db.query(SupplierPayment).filter(
        SupplierPayment.supplier_id == supplier_id
    ).order_by(SupplierPayment.paid_at.desc()).all()

    debt_info = get_supplier_debt(db, supplier_id)

    return {
        **debt_info,
        "purchases": [{
            "id": p.id,
            "item_name": p.item_name,
            "quantity": float(p.quantity),
            "unit": p.unit,
            "price_per_unit": float(p.price_per_unit),
            "total_amount": float(p.total_amount),
            "is_credit": p.is_credit,
            "category": p.category or "Boshqa",
            "purchased_at": p.purchased_at.isoformat() if p.purchased_at else None,
            "purchased_by": p.purchased_by,
            "notes": p.notes
        } for p in purchases],
        "payments": [{
            "id": pay.id,
            "amount": float(pay.amount),
            "paid_at": pay.paid_at.isoformat() if pay.paid_at else None,
            "paid_by": pay.paid_by,
            "notes": pay.notes
        } for pay in payments]
    }


def delete_supplier_payment(db: Session, payment_id: int) -> bool:
    p = db.query(SupplierPayment).filter(SupplierPayment.id == payment_id).first()
    if not p:
        return False
    db.delete(p)
    db.commit()
    return True
