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
    notes: Optional[str] = None


class MasterRead(BaseModel):
    """Ustalarni ko'rish uchun ma'lumot formati."""
    id: int
    name: str
    phone: str
    telegram_id: Optional[str] = None
    cashback_percent: float
    is_active: bool
    hire_date: datetime
    notes: Optional[str] = None

    # SQLAlchemy ob'ektlarini qabul qilish
    model_config = {"from_attributes": True}


class MasterUpdate(BaseModel):
    """Mavjud ustani yangilash uchun (barcha maydonlar ixtiyoriy)."""
    name: Optional[str] = None
    phone: Optional[str] = None
    cashback_percent: Optional[float] = None
    telegram_id: Optional[str] = None
    is_active: Optional[bool] = None
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
    last_updated: datetime
    notes: Optional[str] = None

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
    notes: Optional[str] = None


class StockChange(BaseModel):
    """Qoldiqni o'zgartirish (qo'shish/ayirish)."""
    quantity_change: float = Field(..., description="Musbat = qo'shish, manfiy = ayirish")
    reason: Optional[str] = None


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
    notes: Optional[str] = None


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
    notes: Optional[str] = None
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
    items: List[DeliveryItemRead] = []
    model_config = {"from_attributes": True}


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
