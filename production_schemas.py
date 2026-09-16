"""
PenoDecorPro ERP — Production/MRP uchun Pydantic sxemalar (DTO)
==================================================================
mavjud schemas.py'dagi uslubga mos: har bir jadval uchun alohida
Create/Read (kerak bo'lsa Update) klasslar, model_config bilan ORM
rejimi yoqilgan.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================
# PRODUCT TYPE
# ============================================================

class ProductTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="Masalan: Travertin, Kafel kley")
    unit: str = Field(..., min_length=1, max_length=20, description="dona / m² / kg / litr")
    input_template: str = Field(..., description="quantity_only / dimensional_3d / area_2d / weight_volume / flexible_unit")
    pricing_formula: str = Field(..., description="volume_based / area_based / fixed_price / unit_based")
    fixed_unit_price: Optional[float] = Field(default=None, ge=0, description="Faqat pricing_formula=fixed_price bo'lsa")
    notes: Optional[str] = None


class ProductTypeRead(BaseModel):
    id: int
    company_id: int
    name: str
    unit: str
    input_template: str
    pricing_formula: str
    fixed_unit_price: Optional[float] = None
    is_active: bool
    created_at: datetime
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


# ============================================================
# BOM ITEM
# ============================================================

class BOMItemCreate(BaseModel):
    inventory_id: int
    component_type: str = Field(default="raw_material", description="raw_material / packaging")
    quantity: float = Field(..., gt=0, description="BOM.batch_quantity uchun kerak miqdor")
    scrap_factor_percent: float = Field(default=0.0, ge=0, le=100)
    is_optional: bool = False
    fixed_cost_per_unit: Optional[float] = Field(default=None, ge=0)
    percentage_cost: Optional[float] = Field(default=None, ge=0, le=1000)
    notes: Optional[str] = None


class BOMItemRead(BaseModel):
    id: int
    inventory_id: int
    item_name: str
    unit: str
    component_type: str
    quantity: float
    scrap_factor_percent: float
    is_optional: bool
    fixed_cost_per_unit: Optional[float] = None
    percentage_cost: Optional[float] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


# ============================================================
# BOM
# ============================================================

class BOMCreate(BaseModel):
    product_type_id: int
    variant_name: str = Field(default="Standart", max_length=100)
    batch_quantity: float = Field(..., gt=0)
    notes: Optional[str] = None
    items: List[BOMItemCreate] = Field(default_factory=list)


class BOMRead(BaseModel):
    id: int
    company_id: int
    product_type_id: int
    variant_name: str
    batch_quantity: float
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    notes: Optional[str] = None
    items: List[BOMItemRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ============================================================
# PRODUCTION ORDER
# ============================================================

class ProductionOrderCreate(BaseModel):
    """DRAFT holatida yaratish uchun. Hali hech qanday ombor
    tekshiruvi/band qilish sodir bo'lmaydi."""
    product_type_id: int
    bom_id: int
    quantity: float = Field(..., gt=0)
    source_type: str = Field(..., description="customer_order / warehouse_stock")
    source_order_id: Optional[int] = Field(default=None, description="Faqat source_type=customer_order bo'lsa")
    selected_optional_bom_item_ids: List[int] = Field(default_factory=list, description="Tanlangan ixtiyoriy komponentlar (masalan Qoplama)")
    notes: Optional[str] = None


class ProductionOrderSnapshotLine(BaseModel):
    """recipe_snapshot_json ichidagi bitta qatorning shakli — faqat
    JAVOB (response) uchun, saqlashda xuddi shu tuzilish JSON qilib
    yoziladi."""
    inventory_id: int
    item_name: str
    unit: str
    component_type: str
    is_optional: bool
    included: bool
    base_quantity: float
    scrap_factor_percent: float
    effective_quantity_per_batch: float
    total_quantity_needed: float
    unit_price_at_time: float
    line_cost: float


class ProductionOrderRead(BaseModel):
    id: int
    company_id: int
    product_type_id: int
    bom_id: int
    source_type: str
    source_order_id: Optional[int] = None
    quantity: float
    status: str
    total_material_cost: Optional[float] = None
    total_extra_cost: Optional[float] = None
    total_cost: Optional[float] = None
    created_by: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    notes: Optional[str] = None
    recipe_snapshot: List[ProductionOrderSnapshotLine] = Field(default_factory=list, description="recipe_snapshot_json'dan parse qilingan")

    model_config = {"from_attributes": True}


class StockValidationIssue(BaseModel):
    """start_production_order chaqirilganda, agar biror xomashyo
    yetarli bo'lmasa — shu shaklda qaytariladi (yumshoq yoki qattiq
    rejimning ikkalasida ham, farqi faqat davom etish-etmasligida)."""
    inventory_id: int
    item_name: str
    unit: str
    required_quantity: float
    available_quantity: float
    shortage: float


class StartProductionResult(BaseModel):
    """DRAFT -> IN_PROGRESS o'tishning natijasi."""
    production_order: ProductionOrderRead
    stock_warnings: List[StockValidationIssue] = Field(default_factory=list, description="allow_negative_stock=True bo'lganda ham ko'rsatiladi — ogohlantirish sifatida")
