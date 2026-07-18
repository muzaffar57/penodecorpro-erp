"""
PenoDecorPro ERP — Pydantic sxemalari
======================================
Pydantic sxemalar — bu ma'lumot formatlari.
Ular API ga keladigan va chiqadigan ma'lumotlarni tekshiradi.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================
# MASTER (Usta)
# ============================================================

class MasterCreate(BaseModel):
    """Yangi usta qo'shish uchun ma'lumot formati."""
    name: str = Field(..., min_length=2, max_length=100, description="Usta ismi")
    phone: str = Field(..., min_length=7, max_length=20, description="Telefon raqami")
    cashback_percent: float = Field(default=0.0, ge=0, le=100, description="KPI foizi (0-100)")
    telegram_id: Optional[str] = None
    region: Optional[str] = None
    notes: Optional[str] = None


class MasterRead(BaseModel):
    """Ustalarni ko'rish uchun ma'lumot formati."""
    id: int
    name: str
    phone: str
    telegram_id: Optional[str] = None
    cashback_percent: float
    kpi_percent: Optional[float] = 0
    is_active: bool
    hire_date: datetime
    region: Optional[str] = None
    notes: Optional[str] = None

    # SQLAlchemy ob'ektlarini qabul qilish
    model_config = {"from_attributes": True}


class MasterUpdate(BaseModel):
    """Mavjud ustani yangilash uchun (barcha maydonlar ixtiyoriy)."""
    name: Optional[str] = None
    phone: Optional[str] = None
    cashback_percent: Optional[float] = None
    kpi_percent: Optional[float] = None
    telegram_id: Optional[str] = None
    is_active: Optional[bool] = None
    region: Optional[str] = None
    notes: Optional[str] = None


# ============================================================
# INVENTORY (Omborxona)
# ============================================================

class InventoryCreate(BaseModel):
    """Yangi xomashyo qo'shish uchun."""
    item_name: str = Field(..., min_length=2, max_length=100)
    stock_quantity: float = Field(default=0.0, ge=0)
    unit: str = Field(..., description="O'lchov birligi: kg, litr, dona, m")
    min_stock: float = Field(default=0.0, ge=0)
    price_per_unit: Optional[float] = None
    volume_per_unit: float = Field(default=1.0, gt=0, description="Blok hajmi (m³)")
    is_penoplast: bool = Field(default=False, description="Penoplast (plotnost) turimi")
    is_default_penoplast: bool = Field(default=False, description="Asosiy plotnost")
    category: Optional[str] = None
    notes: Optional[str] = None


class InventoryRead(BaseModel):
    """Xomashyoni ko'rish uchun."""
    id: int
    item_name: str
    stock_quantity: float
    unit: str
    min_stock: float
    price_per_unit: Optional[float] = None
    volume_per_unit: float = 1.0
    is_penoplast: bool = False
    is_default_penoplast: bool = False
    category: Optional[str] = None
    last_updated: datetime
    notes: Optional[str] = None
    image_url: Optional[str] = None

    model_config = {"from_attributes": True}


class InventoryUpdate(BaseModel):
    """Xomashyoni yangilash uchun."""
    item_name: Optional[str] = None
    stock_quantity: Optional[float] = None
    unit: Optional[str] = None
    min_stock: Optional[float] = None
    price_per_unit: Optional[float] = None
    volume_per_unit: Optional[float] = None
    is_penoplast: Optional[bool] = None
    is_default_penoplast: Optional[bool] = None
    category: Optional[str] = None
    notes: Optional[str] = None


class StockChange(BaseModel):
    """Qoldiqni o'zgartirish (qo'shish/ayirish)."""
    quantity_change: float = Field(..., description="Musbat = qo'shish, manfiy = ayirish")
    reason: Optional[str] = None


class StockPurchase(BaseModel):
    """Ombor kirimi — xarid narxi bilan (o'rtacha vaznli narx hisoblanadi)."""
    quantity: float = Field(..., gt=0, description="Necha birlik kirim qilindi")
    price_per_unit: float = Field(..., gt=0, description="Shu xariddagi 1 birlik narxi")
    notes: Optional[str] = None
    supplier_id: Optional[int] = None
    is_credit: bool = Field(default=False, description="Nasiya (keyin to'lash) bilan olindimi — server hisoblaydi")
    paid_now: float = Field(default=0, ge=0, description="Xarid vaqtida hoziroq to'langan summa")
    transport_cost: float = Field(default=0, ge=0)
    transport_payer: str = Field(default="none", description="none/self/supplier")
    volume_per_unit: Optional[float] = Field(default=None, gt=0, description="Penoplast uchun: 1 blok necha m³")


class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    phone: Optional[str] = None
    notes: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class SupplierPaymentCreate(BaseModel):
    supplier_id: int
    amount: float = Field(..., gt=0)
    notes: Optional[str] = None


class PurchaseUpdate(BaseModel):
    """Xarid yozuvini tahrirlash — faqat berilgan maydonlar o'zgaradi."""
    quantity: Optional[float] = Field(default=None, gt=0)
    price_per_unit: Optional[float] = Field(default=None, gt=0)
    is_credit: Optional[bool] = None
    notes: Optional[str] = None


class PurchaseRead(BaseModel):
    id: int
    inventory_id: int
    item_name: str
    quantity: float
    unit: Optional[str] = None
    price_per_unit: float
    total_amount: float
    purchased_at: datetime
    purchased_by: Optional[str] = None
    notes: Optional[str] = None
    model_config = {"from_attributes": True}


# ============================================================
# RECIPE (Retseptlar)
# ============================================================

class RecipeCreate(BaseModel):
    """Yangi retsept qo'shish uchun."""
    name: str = Field(..., description="Kvars yoki Oq Marmar")
    akril_kg: float = Field(default=0.0, ge=0)
    pva_kg: float = Field(default=0.0, ge=0)
    qum_kg: float = Field(default=0.0, ge=0)
    travertin_qum_kg: float = Field(default=0.0, ge=0)
    kroshka_kg: float = Field(default=0.0, ge=0)
    penogasitel_kg: float = Field(default=0.0, ge=0)
    shtukaturka_kg: float = Field(default=0.0, ge=0)
    zagustitel_kg: float = Field(default=0.0, ge=0)
    suv_kg: float = Field(default=0.0, ge=0)
    biotsid_ml: float = Field(default=0.0, ge=0)
    batch_size_kg: float = Field(default=150.0, gt=0)
    notes: Optional[str] = None


class RecipeRead(BaseModel):
    """Retseptni ko'rish uchun."""
    id: int
    name: str
    akril_kg: float
    pva_kg: float
    qum_kg: float
    travertin_qum_kg: float = 0.0
    kroshka_kg: float
    penogasitel_kg: float
    shtukaturka_kg: float
    zagustitel_kg: float = 0.0
    suv_kg: float
    biotsid_ml: float
    batch_size_kg: float
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    image_url: Optional[str] = None

    model_config = {"from_attributes": True}


# ============================================================
# PROJECT (Loyihalar)
# ============================================================

class ProjectCreate(BaseModel):
    project_name: str = Field(..., min_length=2, max_length=200)
    client_name: str = Field(..., min_length=2, max_length=100)
    client_phone: Optional[str] = None
    client_address: Optional[str] = None
    description: Optional[str] = None
    total_budget: Optional[float] = 0
    notes: Optional[str] = None


class ProjectRead(BaseModel):
    id: int
    project_number: Optional[str] = None
    project_name: str
    client_name: str
    client_phone: Optional[str] = None
    status: str
    total_budget: Optional[float] = 0
    total_paid: Optional[float] = 0
    start_date: datetime
    model_config = {"from_attributes": True}


# ============================================================
# ORDER (Buyurtmalar)
# ============================================================

class OrderItemCreate(BaseModel):
    name: str = Field(..., min_length=2)
    category: Optional[str] = None
    width: Optional[float] = None
    thickness: Optional[float] = None
    length: Optional[float] = None
    quantity: float = Field(default=1.0, gt=0)
    is_coated: bool = True
    unit_price: float = Field(default=0, ge=0)
    penoplast_id: Optional[int] = None
    price_per_m3: Optional[float] = None
    finished_product_id: Optional[int] = None
    image_url: Optional[str] = None
    notes: Optional[str] = None
    # Termopanel (Bazalt) uchun — category='termopanel' bo'lganda ishlatiladi
    bazalt_item_id: Optional[int] = None
    serpiyanka_item_id: Optional[int] = None
    kley_kg: Optional[float] = None
    termo_loy_kg: Optional[float] = None


class OrderCreate(BaseModel):
    project_id: int
    order_type: str = Field(default="product", description="service yoki product")
    master_id: Optional[int] = None
    recipe_id: Optional[int] = None
    items: List[OrderItemCreate] = []
    agreed_amount: Optional[float] = None
    is_draft: bool = False
    deadline: Optional[datetime] = None
    notes: Optional[str] = None


class OrderItemRead(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    width: Optional[float] = None
    thickness: Optional[float] = None
    length: Optional[float] = None
    quantity: float
    is_coated: bool
    unit_price: float
    total_price: float
    penoplast_id: Optional[int] = None
    penoplast_name: Optional[str] = None
    price_per_m3: Optional[float] = None
    finished_product_id: Optional[int] = None
    image_url: Optional[str] = None
    notes: Optional[str] = None
    model_config = {"from_attributes": True}


class ExpenseTransactionCreate(BaseModel):
    date: Optional[datetime] = None
    category: str
    amount: float = Field(..., ge=0)
    notes: Optional[str] = None


class ExpenseTransactionRead(BaseModel):
    id: int
    date: datetime
    category: str
    amount: float
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    source: str = "manual"
    model_config = {"from_attributes": True}


class InventoryMovementRead(BaseModel):
    id: int
    inventory_id: Optional[int] = None
    item_name: str
    movement_type: str
    quantity: float
    unit: Optional[str] = None
    reason: Optional[str] = None
    order_id: Optional[int] = None
    supplier_id: Optional[int] = None
    performed_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class OrderAttachmentRead(BaseModel):
    id: int
    order_id: int
    file_url: str
    file_name: Optional[str] = None
    uploaded_at: datetime
    uploaded_by: Optional[str] = None
    model_config = {"from_attributes": True}


# ============================================================
# FINISHED PRODUCT (Tayyor mahsulotlar)
# ============================================================

class ProduceCreate(BaseModel):
    """Tayyor mahsulot ishlab chiqarish."""
    name: str = Field(..., min_length=2, max_length=150)
    category: str = Field(default="profil", description="profil / panel / dona")
    width: Optional[float] = None
    thickness: Optional[float] = None
    length: Optional[float] = None      # profil uchun — necha metr
    quantity: Optional[float] = None    # panel/dona uchun — necha dona
    is_coated: bool = True
    penoplast_id: Optional[int] = None
    price_per_m3: Optional[float] = None
    unit_price: float = Field(default=0, ge=0, description="Sotuv narxi (1 metr / 1 dona)")
    unit_price_for_volume: Optional[float] = Field(default=None, description="Dona uchun: 1 dona tan narxi (hajm hisobi)")
    loy_kg: float = Field(default=0, ge=0)
    recipe_id: Optional[int] = None
    notes: Optional[str] = None


class TermopanelProduceCreate(BaseModel):
    """Bazalt asosidagi termopanel ishlab chiqarish (kvadrat metr bo'yicha)."""
    name: str = Field(..., min_length=2, max_length=150)
    required_m2: float = Field(..., gt=0, description="Kerakli kvadrat metr")
    bazalt_item_id: int
    serpiyanka_item_id: int
    kley_kg: float = Field(default=0, ge=0)
    recipe_id: Optional[int] = None
    loy_kg: float = Field(default=0, ge=0)
    unit_price: float = Field(default=0, ge=0, description="Sotuv narxi (1 kvadrat metr uchun)")
    notes: Optional[str] = None


class FinishedProductRead(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    width: Optional[float] = None
    thickness: Optional[float] = None
    is_coated: bool = True
    quantity: float
    unit: str
    unit_price: float
    cost_price: Optional[float] = 0
    source: str
    from_order_id: Optional[int] = None
    return_reason: Optional[str] = None
    volume_m3: Optional[float] = 0
    planned_loy_kg: Optional[float] = 0
    actual_loy_kg: Optional[float] = None
    production_status: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None
    notes: Optional[str] = None
    model_config = {"from_attributes": True}


class ProduceComplete(BaseModel):
    """Ishlab chiqarishni yakunlash (status o'zgartirish)."""
    actual_loy_kg: float = Field(default=0, ge=0, description="Ishlatilmaydi — moslik uchun")


class StockAdjust(BaseModel):
    """Tayyor mahsulot miqdorini o'zgartirish (+ qo'shish / − brak)."""
    quantity: float = Field(..., gt=0)
    reason: Optional[str] = None


class FinishedProductUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    notes: Optional[str] = None


# ============================================================
# DELIVERY (Yetkazishlar)
# ============================================================

class DeliveryItemCreate(BaseModel):
    order_item_id: int
    quantity: float = Field(..., gt=0)


class DeliveryCreate(BaseModel):
    order_id: int
    items: List[DeliveryItemCreate] = []
    received_by: Optional[str] = None
    notes: Optional[str] = None
    transport_carrier: Optional[str] = None
    transport_cost: float = Field(default=0, ge=0)
    transport_payer: str = Field(default="none", description="none/client/company/split")
    payment_amount: Optional[float] = Field(default=None, ge=0, description="Shu yukka bog'liq to'lov (ixtiyoriy)")
    payment_method: Optional[str] = Field(default="naqd", description="naqd/plastik/o'tkazma")


class DeliveryItemRead(BaseModel):
    id: int
    order_item_id: int
    quantity: float
    unit: str
    item_name: Optional[str] = None
    model_config = {"from_attributes": True}


class DeliveryRead(BaseModel):
    id: int
    order_id: int
    delivery_number: Optional[str] = None
    delivered_at: datetime
    delivered_by: Optional[str] = None
    received_by: Optional[str] = None
    notes: Optional[str] = None
    transport_carrier: Optional[str] = None
    transport_cost: Optional[float] = 0
    transport_payer: Optional[str] = "none"
    items: List[DeliveryItemRead] = []
    model_config = {"from_attributes": True}


class EmployeeCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    position: Optional[str] = None
    pay_type: str = Field(..., description="fixed/percent_sales/percent_profit/per_unit")
    fixed_amount: float = Field(default=0, ge=0)
    percent_value: float = Field(default=0, ge=0, le=100)
    per_unit_rate: float = Field(default=0, ge=0)
    per_unit_type: str = Field(default="blok", description="blok/metr/dona")
    notes: Optional[str] = None


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    position: Optional[str] = None
    pay_type: Optional[str] = None
    fixed_amount: Optional[float] = None
    percent_value: Optional[float] = None
    per_unit_rate: Optional[float] = None
    per_unit_type: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class EmployeeRead(BaseModel):
    id: int
    name: str
    position: Optional[str] = None
    pay_type: str
    fixed_amount: float
    percent_value: float
    per_unit_rate: float
    per_unit_type: str
    is_active: bool
    notes: Optional[str] = None
    model_config = {"from_attributes": True}


class MasterKpiUpdate(BaseModel):
    kpi_percent: float = Field(..., ge=0, le=100)


class TransportExpenseCreate(BaseModel):
    """Kirish transporti — xomashyo olib kelish xarajati."""
    amount: float = Field(..., gt=0)
    materials_note: Optional[str] = None
    notes: Optional[str] = None


class PaymentCreate(BaseModel):
    """Yangi to'lov qo'shish."""
    order_id: int
    amount: float = Field(..., gt=0, description="To'lov summasi")
    payment_type: str = Field(default="partial", description="zaklat / partial / final")
    payment_method: str = Field(default="naqd", description="naqd / plastik / o'tkazma")
    received_by: Optional[str] = None
    notes: Optional[str] = None


class PaymentRead(BaseModel):
    """To'lovni ko'rish."""
    id: int
    order_id: int
    amount: float
    payment_type: str
    payment_method: str
    paid_at: datetime
    received_by: Optional[str] = None
    notes: Optional[str] = None
    model_config = {"from_attributes": True}


class OrderRead(BaseModel):
    id: int
    order_number: Optional[str] = None
    project_id: int
    order_type: str
    status: str
    total_amount: float
    agreed_amount: Optional[float] = 0
    discount_percent: Optional[float] = 0
    payment_status: Optional[str] = "unpaid"
    paid_amount: Optional[float] = 0
    debt_amount: Optional[float] = 0
    is_archived: Optional[bool] = False
    master_id: Optional[int] = None
    created_at: datetime
    deadline: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    items: List[OrderItemRead] = []
    payments: List[PaymentRead] = []
    model_config = {"from_attributes": True}


class OrderAgreedUpdate(BaseModel):
    """Kelishilgan summani yangilash."""
    agreed_amount: float = Field(..., ge=0)


class ProjectUpdate(BaseModel):
    """Loyihani yangilash uchun."""
    project_name: Optional[str] = None
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    client_address: Optional[str] = None
    description: Optional[str] = None
    total_budget: Optional[float] = None
    total_paid: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None


# ============================================================
# RETURN ITEM schemas
# ============================================================

class ReturnItemCreate(BaseModel):
    order_id: int
    item_name: str
    quantity: float
    unit: str = "dona"
    reason: str
    refund_amount: float = 0
    to_stock: bool = Field(default=True, description="Tayyor mahsulotlar omboriga qo'shilsinmi")
    order_item_id: Optional[int] = None
    notes: Optional[str] = None

class ReturnItemRead(BaseModel):
    id: int
    order_id: int
    item_name: str
    quantity: float
    unit: str
    reason: str
    refund_amount: float
    is_refunded: bool
    notes: Optional[str] = None
    returned_at: datetime
    model_config = {"from_attributes": True}
