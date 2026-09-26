"""
PenoDecorPro ERP — Production/MRP uchun Pydantic sxemalar (DTO)
==================================================================
mavjud schemas.py'dagi uslubga mos: har bir jadval uchun alohida
Create/Read (kerak bo'lsa Update) klasslar, model_config bilan ORM
rejimi yoqilgan.
"""

from datetime import datetime
from typing import Annotated, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


# kech93 (8-band) — KIRISH (Create) sxemalari QAT'IY: bu IKKINCHI to'siq.
# Birinchisi — marshrutdagi `crud._clean_val` (o'qiladigan matn bilan 400;
# `production.html` 422 ro'yxatini "[object Object]" deb ko'rsatardi).
# HAQIQIY PostgreSQL 16 da O'LCHANGAN (`work/probe8.py`, `work/probe8b.py`):
# "lax" sxema `true` → 1, "yes" → True, "1" → 1 ga JIM o'girardi, noma'lum
# kalitlar (`company_id`, `is_active`, `status`) jim tashlanardi, tanlov
# maydonlariga ixtiyoriy matn yozilardi, `Infinity` retsept partiyasi BAZAGA
# tushardi, 1e20 narx / 2**31 id → 500.
_QATIY = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
_ID = Annotated[int, Field(ge=1, le=2_147_483_647)]
_PUL_MAX = 9_999_999_999.99        # Numeric(12,2)
_SON_MAX = 1_000_000_000_000.0     # Float miqdorlar — crud._UPD_SON_CHEGARA bilan bir xil
_MATN_MAX = 10_000                 # Text — crud._UPD_MATN_CHEGARA bilan bir xil
_QATOR_MAX = 500                   # crud._RETSEPT_QATOR_MAX
# Tanlov qiymatlari — production_models dagi enum qiymatlari bilan AYNAN
# (test `test_tana_qatiy` H bo'limi tenglikni tekshiradi).
_KIRITISH_SHABLONI = Literal["quantity_only", "dimensional_3d", "area_2d",
                             "weight_volume", "flexible_unit"]
_NARX_FORMULASI = Literal["volume_based", "area_based", "fixed_price", "unit_based"]
_KOMPONENT_TURI = Literal["raw_material", "packaging"]
_MANBA_TURI = Literal["customer_order", "warehouse_stock"]


# ============================================================
# PRODUCT TYPE
# ============================================================

class ProductTypeCreate(BaseModel):
    model_config = _QATIY
    name: str = Field(..., min_length=1, max_length=150, description="Masalan: Travertin, Kafel kley")
    unit: str = Field(..., min_length=1, max_length=20, description="dona / m² / kg / litr")
    input_template: _KIRITISH_SHABLONI = Field(..., description="quantity_only / dimensional_3d / area_2d / weight_volume / flexible_unit")
    pricing_formula: _NARX_FORMULASI = Field(..., description="volume_based / area_based / fixed_price / unit_based")
    fixed_unit_price: Optional[float] = Field(default=None, ge=0, le=_PUL_MAX, description="Faqat pricing_formula=fixed_price bo'lsa")
    # 11.0-band — qoplama. `supports_coating=True` bo'lsa, buyurtmada shu
    # mahsulot uchun "Qoplama" tugmasi chiqadi va narx koeffitsiyentga
    # ko'paytiriladi. Koeffitsiyent har korxonada har xil (2 / 2.5 / ...).
    supports_coating: bool = False
    coating_price_multiplier: Optional[float] = Field(
        default=None, gt=0, le=100,
        description="Qoplamali narx koeffitsiyenti, masalan 2 yoki 2.5")
    notes: Optional[str] = Field(default=None, max_length=_MATN_MAX)

    @model_validator(mode="after")
    def _qoplama_tekshir(self):
        """Qoplama yoqilgan bo'lsa, koeffitsiyent SHART.

        Jimgina 2.0 qo'yib qo'yish xavfli: 2.5 ishlatadigan korxona
        buni sezmay qolishi va narx jimgina noto'g'ri chiqishi mumkin.
        Shuning uchun aniq so'raladi."""
        if self.supports_coating and self.coating_price_multiplier is None:
            raise ValueError(
                "Qoplama yoqilgan — qoplama narx koeffitsiyentini kiriting "
                "(masalan 2 yoki 2.5)")
        return self


class ProductTypeRead(BaseModel):
    id: int
    company_id: int
    name: str
    unit: str
    input_template: str
    pricing_formula: str
    fixed_unit_price: Optional[float] = None
    supports_coating: bool = False
    coating_price_multiplier: Optional[float] = None
    is_active: bool
    created_at: datetime
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


# ============================================================
# BOM ITEM
# ============================================================

class BOMItemCreate(BaseModel):
    model_config = _QATIY
    inventory_id: _ID
    component_type: _KOMPONENT_TURI = Field(default="raw_material", description="raw_material / packaging")
    quantity: float = Field(..., gt=0, le=_SON_MAX, description="BOM.batch_quantity uchun kerak miqdor")
    scrap_factor_percent: float = Field(default=0.0, ge=0, le=100)
    is_optional: bool = False
    # 11.0-band — shu ixtiyoriy qator aynan QOPLAMA uchunmi. Faqat
    # `is_optional=True` bo'lganda ma'noga ega.
    is_coating: bool = False
    fixed_cost_per_unit: Optional[float] = Field(default=None, ge=0, le=_PUL_MAX)
    percentage_cost: Optional[float] = Field(default=None, ge=0, le=1000)
    notes: Optional[str] = Field(default=None, max_length=_MATN_MAX)


class BOMItemRead(BaseModel):
    id: int
    inventory_id: int
    item_name: str
    unit: str
    component_type: str
    quantity: float
    scrap_factor_percent: float
    is_optional: bool
    is_coating: bool = False
    fixed_cost_per_unit: Optional[float] = None
    percentage_cost: Optional[float] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


# ============================================================
# BOM
# ============================================================

class BOMCreate(BaseModel):
    model_config = _QATIY
    product_type_id: _ID
    variant_name: str = Field(default="Standart", max_length=100)
    batch_quantity: float = Field(..., gt=0, le=_SON_MAX)
    notes: Optional[str] = Field(default=None, max_length=_MATN_MAX)
    items: List[BOMItemCreate] = Field(..., min_length=1, max_length=_QATOR_MAX)


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
    model_config = _QATIY
    product_type_id: _ID
    bom_id: _ID
    quantity: float = Field(..., gt=0, le=_SON_MAX)
    source_type: _MANBA_TURI = Field(..., description="customer_order / warehouse_stock")
    source_order_id: Optional[_ID] = Field(default=None, description="Faqat source_type=customer_order bo'lsa")
    source_order_item_id: Optional[_ID] = Field(default=None, description="Aniq QAYSI buyurtma-detalini to'ldirish uchun — rezervatsiya shu orqali ishlaydi")
    selected_optional_bom_item_ids: List[_ID] = Field(default_factory=list, max_length=_QATOR_MAX, description="Tanlangan ixtiyoriy komponentlar (masalan Qoplama)")
    notes: Optional[str] = Field(default=None, max_length=_MATN_MAX)


class ProductionOrderSnapshotLine(BaseModel):
    """recipe_snapshot_json ichidagi bitta qatorning shakli — faqat
    JAVOB (response) uchun, saqlashda xuddi shu tuzilish JSON qilib
    yoziladi.

    2026-09-16: qoida #1 (Unit Conversion) uchun qo'shilgan maydonlar —
    `unit`/`total_quantity_needed` RETSEPT birligida (masalan gramm),
    `stock_unit`/`total_quantity_needed_stock_unit` OMBOR birligida
    (masalan qop) — HAQIQIY ayirish/tannarx shu ikkinchisi bilan
    hisoblanadi. `conversion_factor_at_time` — konversiya koeffitsienti
    ham SHU PAYTDA suratga olinadi (immutability, qoida #2 bilan bir xil
    printsip: material kartochkasi keyin o'zgarsa ham, bu buyurtma
    o'zgarmaydi)."""
    inventory_id: int
    item_name: str
    unit: str
    stock_unit: str
    conversion_factor_at_time: Optional[float] = None
    component_type: str
    is_optional: bool
    included: bool
    base_quantity: float
    scrap_factor_percent: float
    effective_quantity_per_batch: float
    total_quantity_needed: float
    total_quantity_needed_stock_unit: float
    unit_price_at_time: float
    line_cost: float
    # kech94 (122-band): qo'shimcha xarajat ham suratga olinadi (yakunlash shu
    # qiymatlardan va faqat kiritilgan qatorlardan hisoblaydi). Eski suratda yo'q — None.
    fixed_cost_per_unit: Optional[float] = None
    percentage_cost: Optional[float] = None


class ProductionOrderRead(BaseModel):
    id: int
    company_id: int
    product_type_id: int
    bom_id: int
    source_type: str
    source_order_id: Optional[int] = None
    source_order_item_id: Optional[int] = None
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
