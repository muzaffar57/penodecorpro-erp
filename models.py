"""
PenoDecorPro ERP — Ma'lumotlar bazasi modellari (v2)
=====================================================
Project (Loyiha) va ReturnItem (Qaytarish) qo'shildi.

Mantiq:
- Project = mijozning butun loyihasi (masalan: "Falonchi hovli fasadi")
- Order = loyiha ichidagi alohida buyurtma
- OrderItem = buyurtma ichidagi alohida detal
- ReturnItem = qaytarilgan mahsulotlar (brak yoki ortiqcha)
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Enum, Text, Numeric
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


# ============================================================
# ENUM lar
# ============================================================

class UserRole(PyEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    MASTER = "master"
    ACCOUNTANT = "accountant"


class ProjectStatus(PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderStatus(PyEnum):
    DRAFT = "draft"
    NEW = "new"
    IN_PROGRESS = "in_progress"
    COATING = "coating"
    READY = "ready"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class OrderType(PyEnum):
    SERVICE = "service"
    PRODUCT = "product"


class RecipeType(PyEnum):
    QUARTZ = "Kvars"
    MARBLE = "Oq Marmar"


class ReturnReason(PyEnum):
    DEFECT = "Brak"
    EXCESS = "Ortiqcha"
    WRONG_SIZE = "Notog'ri o'lcham"
    CUSTOMER_REQUEST = "Mijoz iltimosi"


class PaymentType(PyEnum):
    """To'lov turi."""
    ZAKLAT = "zaklat"        # Oldindan to'lov
    PARTIAL = "partial"      # Qisman to'lov
    FINAL = "final"          # Yakuniy to'lov


class PaymentMethod(PyEnum):
    """To'lov usuli."""
    CASH = "naqd"
    CARD = "plastik"
    TRANSFER = "o'tkazma"


class PaymentStatus(PyEnum):
    """Buyurtma to'lov holati."""
    UNPAID = "unpaid"        # To'lanmagan
    PARTIAL = "partial"      # Qisman to'langan
    PAID = "paid"            # To'liq to'langan


# ============================================================
# 1. USER
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.MANAGER)
    full_name = Column(String(100))
    telegram_id = Column(String(50), unique=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.username} ({self.role.value})>"


# ============================================================
# 2. MASTER
# ============================================================

class Master(Base):
    __tablename__ = "masters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    telegram_id = Column(String(50), unique=True, nullable=True)
    cashback_percent = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    hire_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)

    orders = relationship("Order", back_populates="master")

    def __repr__(self):
        return f"<Master {self.name} ({self.cashback_percent}%)>"


# ============================================================
# 3. INVENTORY
# ============================================================

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String(100), nullable=False, unique=True, index=True)
    stock_quantity = Column(Float, default=0.0)
    unit = Column(String(20), nullable=False)
    min_stock = Column(Float, default=0.0)
    price_per_unit = Column(Numeric(12, 2), nullable=True)
    volume_per_unit = Column(Float, default=1.0)  # m³ — penoplast blok hajmi
    is_penoplast = Column(Boolean, default=False)  # Penoplast (plotnost) turimi
    is_default_penoplast = Column(Boolean, default=False)  # Asosiy plotnost
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Inventory {self.item_name}: {self.stock_quantity} {self.unit}>"


# ============================================================
# 4. RECIPE
# ============================================================

class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Enum(RecipeType), nullable=False, unique=True)

    akril_kg = Column(Float, default=0.0)
    pva_kg = Column(Float, default=0.0)
    qum_kg = Column(Float, default=0.0)          # Kvars qum
    travertin_qum_kg = Column(Float, default=0.0) # Travertin qum
    kroshka_kg = Column(Float, default=0.0)
    penogasitel_kg = Column(Float, default=0.0)
    shtukaturka_kg = Column(Float, default=0.0)  # Mel
    zagustitel_kg = Column(Float, default=0.0)   # Zagustitel
    suv_kg = Column(Float, default=0.0)
    biotsid_ml = Column(Float, default=0.0)

    batch_size_kg = Column(Float, default=150.0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Recipe {self.name.value}>"


# ============================================================
# 5. PROJECT — Mijoz loyihasi
# ============================================================

class Project(Base):
    """Mijozning butun loyihasi.
    Bir loyihada bir nechta order bo'lishi mumkin."""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    project_number = Column(String(20), unique=True, index=True)  # PRJ-001
    client_name = Column(String(100), nullable=False)
    client_phone = Column(String(20), nullable=True)
    client_address = Column(Text, nullable=True)

    project_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    status = Column(Enum(ProjectStatus), default=ProjectStatus.DRAFT, nullable=False)

    total_budget = Column(Numeric(12, 2), default=0)
    total_paid = Column(Numeric(12, 2), default=0)

    start_date = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    notes = Column(Text, nullable=True)

    orders = relationship("Order", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project #{self.project_number} — {self.project_name}>"


# ============================================================
# 6. ORDER — Loyiha ichidagi sub-order
# ============================================================

class Order(Base):
    """Loyiha ichidagi alohida buyurtma."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(20), unique=True, index=True)

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    project = relationship("Project", back_populates="orders")

    order_type = Column(Enum(OrderType), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.NEW, nullable=False)

    total_amount = Column(Numeric(12, 2), default=0)      # Jami summa (chegirmasiz)
    agreed_amount = Column(Numeric(12, 2), default=0)      # Kelishilgan summa (chegirmadan keyin)
    discount_percent = Column(Float, default=0.0)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.UNPAID, nullable=False)
    is_archived = Column(Boolean, default=False)           # Arxivga o'tdimi

    master_id = Column(Integer, ForeignKey("masters.id"), nullable=True)
    master = relationship("Master", back_populates="orders")

    created_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)            # Qarz yopilgan sana

    notes = Column(Text, nullable=True)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    returns = relationship("ReturnItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")

    @property
    def paid_amount(self):
        """To'langan jami summa."""
        return sum(float(p.amount or 0) for p in (self.payments or []))

    @property
    def debt_amount(self):
        """Qarz qoldi."""
        agreed = float(self.agreed_amount or self.total_amount or 0)
        return max(agreed - self.paid_amount, 0)

    def __repr__(self):
        return f"<Order #{self.order_number} (Project #{self.project_id})>"


# ============================================================
# 7. ORDER ITEM
# ============================================================

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)

    name = Column(String(150), nullable=False)
    category = Column(String(50), nullable=True)

    width = Column(Float, nullable=True)
    thickness = Column(Float, nullable=True)
    length = Column(Float, nullable=True)
    quantity = Column(Float, default=1.0)

    is_coated = Column(Boolean, default=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=True)
    recipe = relationship("Recipe")

    penoplast_id = Column(Integer, ForeignKey("inventory.id"), nullable=True)  # Qaysi plotnost
    penoplast = relationship("Inventory")
    price_per_m3 = Column(Numeric(12, 2), nullable=True)  # Shu detal uchun 1 m³ narxi

    unit_price = Column(Numeric(12, 2), default=0)
    total_price = Column(Numeric(12, 2), default=0)

    notes = Column(Text, nullable=True)

    order = relationship("Order", back_populates="items")

    def __repr__(self):
        return f"<OrderItem {self.name} x{self.quantity}>"


# ============================================================
# 8. RETURN ITEM — Qaytarilgan mahsulotlar
# ============================================================

class ReturnItem(Base):
    """Buyurtmadan qaytarilgan mahsulotlar (brak yoki ortiqcha)."""
    __tablename__ = "return_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)

    item_name = Column(String(150), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(20), default="dona")
    reason = Column(Enum(ReturnReason), nullable=False)

    refund_amount = Column(Numeric(12, 2), default=0)
    is_refunded = Column(Boolean, default=False)

    notes = Column(Text, nullable=True)
    returned_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="returns")

    def __repr__(self):
        return f"<Return {self.item_name} x{self.quantity} ({self.reason.value})>"


# ============================================================
# 9. PAYMENT — To'lovlar tarixi
# ============================================================

class Payment(Base):
    """Buyurtma bo'yicha to'lovlar tarixi.
    Bir buyurtmaga bir necha marta to'lash mumkin."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)

    amount = Column(Numeric(12, 2), nullable=False)
    payment_type = Column(Enum(PaymentType), default=PaymentType.PARTIAL, nullable=False)
    payment_method = Column(Enum(PaymentMethod), default=PaymentMethod.CASH, nullable=False)

    paid_at = Column(DateTime, default=datetime.utcnow)
    received_by = Column(String(100), nullable=True)   # Kim qabul qildi
    notes = Column(Text, nullable=True)

    order = relationship("Order", back_populates="payments")

    def __repr__(self):
        return f"<Payment {self.amount} ({self.payment_type.value})>"


# ============================================================
# 10. MONTHLY EXPENSE — Oylik xarajatlar
# ============================================================

class MonthlyExpense(Base):
    """Oylik xarajatlar: arenda, elektr, tushlik, hodim oyliqlari."""
    __tablename__ = "monthly_expenses"

    id         = Column(Integer, primary_key=True, index=True)
    year       = Column(Integer, nullable=False)   # 2026
    month      = Column(Integer, nullable=False)   # 1-12

    # Doimiy xarajatlar
    arenda     = Column(Numeric(12, 2), default=0)
    elektr     = Column(Numeric(12, 2), default=0)
    tushlik    = Column(Numeric(12, 2), default=0)

    # Hodimlar oyliqi (3 ta doimiy hodim)
    hodim1_ism    = Column(String(100), default="Hodim 1")
    hodim1_oylik  = Column(Numeric(12, 2), default=0)

    hodim2_ism    = Column(String(100), default="Hodim 2")
    hodim2_oylik  = Column(Numeric(12, 2), default=0)

    hodim3_ism    = Column(String(100), default="Hodim 3")
    hodim3_oylik  = Column(Numeric(12, 2), default=0)

    # Qoplamachi hodim bonus (1000 so'm × m²) — avtomatik hisoblanadi
    qoplamachi_ism    = Column(String(100), default="Qoplamachi")
    qoplamachi_bonus  = Column(Numeric(12, 2), default=0)
    qoplamachi_oylik  = Column(Numeric(12, 2), default=0)

    notes      = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MonthlyExpense {self.year}/{self.month}>"


# ============================================================
# Helper funksiyalar
# ============================================================

def create_all_tables(engine):
    Base.metadata.create_all(bind=engine)


def drop_all_tables(engine):
    Base.metadata.drop_all(bind=engine)
