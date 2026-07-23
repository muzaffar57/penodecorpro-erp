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
    WAREHOUSE = "warehouse"


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


class ReturnReason(PyEnum):
    DEFECT = "Brak"
    EXCESS = "Ortiqcha"
    WRONG_SIZE = "Notog'ri o'lcham"
    CUSTOMER_REQUEST = "Mijoz iltimosi"


class StockSource(PyEnum):
    """Tayyor mahsulot qayerdan keldi."""
    PRODUCED = "produced"    # Ishlab chiqarilgan
    RETURNED = "returned"    # Buyurtmadan qaytgan


class ProductionStatus(PyEnum):
    """Ishlab chiqarish jarayoni holati."""
    IN_PROGRESS = "in_progress"   # Kesilmoqda/qoplanmoqda
    READY = "ready"                # Tayyor — loy sarfi aniqlangan


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
    kpi_percent = Column(Float, default=0.0)   # Yillik KPI % — yillik sotuvdan, yil oxiri sovg'a uchun
    is_active = Column(Boolean, default=True)
    hire_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    region = Column(String(50), nullable=True)  # Faqat UI/tahlil uchun — hisob-kitobga ta'siri yo'q

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
    category = Column(String(50), nullable=True)  # Penoplast / Qumlar / Kimyoviy moddalar / Boshqa
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = Column(Text, nullable=True)
    image_url = Column(String(255), nullable=True)  # Faqat UI uchun — hisob-kitobga ta'siri yo'q
    serp_ratio_per_m2 = Column(Float, nullable=True)  # Bazalt uchun: 1 m² bazaltga necha m² serpiyanka
    kley_ratio_per_m2 = Column(Float, nullable=True)  # Bazalt uchun: 1 m² bazaltga necha kg kley
    is_deleted = Column(Boolean, default=False)  # "O'chirilgan" — lekin eski buyurtma/harakat tarixi uchun saqlanadi

    def __repr__(self):
        return f"<Inventory {self.item_name}: {self.stock_quantity} {self.unit}>"


# ============================================================
# 4. RECIPE
# ============================================================

class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)  # Endi ISTALGAN nom bo'lishi mumkin

    batch_size_kg = Column(Float, default=150.0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)  # Faqat UI uchun — tahrirlanganda yangilanadi
    image_url = Column(String(255), nullable=True)  # Faqat UI uchun — hisob-kitobga ta'siri yo'q

    ingredients = relationship("RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Recipe {self.name}>"


class RecipeIngredient(Base):
    """Retsept tarkibidagi bitta qo'shimcha — Omborxonadagi ISTALGAN
    materialga bog'lanadi (endi qattiq yozilgan ro'yxat emas).
    quantity_kg — shu qo'shimchadan Recipe.batch_size_kg uchun kerak miqdor (kg)."""
    __tablename__ = "recipe_ingredients"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=False, index=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False, index=True)
    quantity_kg = Column(Float, nullable=False, default=0.0)

    recipe = relationship("Recipe", back_populates="ingredients")
    inventory = relationship("Inventory")

    @property
    def item_name(self):
        return self.inventory.item_name if self.inventory else "—"

    @property
    def unit(self):
        return self.inventory.unit if self.inventory else "kg"

    def __repr__(self):
        return f"<RecipeIngredient {self.item_name}: {self.quantity_kg}kg>"


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
    image_url = Column(String(255), nullable=True)  # Loyiha rasmi (ixtiyoriy)
    is_deleted = Column(Boolean, default=False)  # "O'chirilgan" — lekin tiklash uchun saqlanadi

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

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    project = relationship("Project", back_populates="orders")

    order_type = Column(Enum(OrderType), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.NEW, nullable=False)

    total_amount = Column(Numeric(12, 2), default=0)      # Jami summa (chegirmasiz)
    agreed_amount = Column(Numeric(12, 2), default=0)      # Kelishilgan summa (chegirmadan keyin)
    discount_percent = Column(Float, default=0.0)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.UNPAID, nullable=False)
    is_archived = Column(Boolean, default=False)           # Arxivga o'tdimi (to'lov to'liq yopilganda)
    is_deleted = Column(Boolean, default=False)             # "O'chirilgan" — lekin KPI/hisobot uchun saqlanadi

    master_id = Column(Integer, ForeignKey("masters.id"), nullable=True, index=True)
    master = relationship("Master", back_populates="orders")

    created_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)            # Qarz yopilgan sana

    notes = Column(Text, nullable=True)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    returns = relationship("ReturnItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")
    deliveries = relationship("Delivery", back_populates="order", cascade="all, delete-orphan")
    attachments = relationship("OrderAttachment", back_populates="order", cascade="all, delete-orphan")

    @property
    def delivery_percent(self):
        """Yetkazish foizi (0-100)."""
        items = self.items or []
        if not items:
            return 0.0
        total_ordered = 0.0
        total_delivered = 0.0
        for it in items:
            ordered = it.order_qty_normalized
            if ordered <= 0:
                continue
            total_ordered += ordered
            total_delivered += min(it.delivered_qty, ordered)
        if total_ordered <= 0:
            return 0.0
        return round(total_delivered / total_ordered * 100, 1)

    @property
    def is_fully_delivered(self):
        """Hamma detal to'liq berildimi."""
        items = self.items or []
        if not items:
            return False
        for it in items:
            if it.remaining_qty > 0.001:
                return False
        return True

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
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)

    name = Column(String(150), nullable=False)
    category = Column(String(50), nullable=True)

    width = Column(Float, nullable=True)
    thickness = Column(Float, nullable=True)
    length = Column(Float, nullable=True)
    quantity = Column(Float, default=1.0)

    is_coated = Column(Boolean, default=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=True, index=True)
    recipe = relationship("Recipe")

    penoplast_id = Column(Integer, ForeignKey("inventory.id"), nullable=True, index=True)  # Qaysi plotnost
    penoplast = relationship("Inventory")
    price_per_m3 = Column(Numeric(12, 2), nullable=True)  # Shu detal uchun 1 m³ narxi

    # Tayyor mahsulotdan olingan bo'lsa — xomashyo hisoblanmaydi
    finished_product_id = Column(Integer, ForeignKey("finished_products.id"), nullable=True, index=True)
    finished_product = relationship("FinishedProduct")

    unit_price = Column(Numeric(12, 2), default=0)
    total_price = Column(Numeric(12, 2), default=0)

    image_url = Column(String(255), nullable=True)  # Mahsulot rasmi (ixtiyoriy, hisob-kitobga ta'sir qilmaydi)

    notes = Column(Text, nullable=True)

    order = relationship("Order", back_populates="items")
    deliveries = relationship("DeliveryItem", back_populates="order_item", cascade="all, delete-orphan")

    @property
    def order_qty_normalized(self):
        """Buyurtmadagi miqdor — profil uzunlik, panel metr, blok CHIQQAN metr,
        termopanel kvadrat metr, dona dona."""
        cat = (self.category or '').lower()
        if cat == 'profil':
            return float(self.length or 0)
        if cat == 'blok':
            return float(self.quantity or 0)   # Blokdan chiqqan metr — mijozga shu yetkaziladi
        return float(self.quantity or 0)

    @property
    def delivery_unit(self):
        """O'lchov birligi — profil, panel va blok metrda (mijozga metr bo'yicha yetkaziladi),
        termopanel kvadrat metrda, qolgani donada."""
        cat = (self.category or '').lower()
        if cat in ('profil', 'panel', 'blok'):
            return 'metr'
        if cat == 'termopanel':
            return 'm²'
        return 'dona'

    @property
    def delivered_qty(self):
        """Jami yetkazilgan miqdor."""
        return sum(float(d.quantity or 0) for d in (self.deliveries or []))

    @property
    def remaining_qty(self):
        """Qolgan miqdor."""
        return max(self.order_qty_normalized - self.delivered_qty, 0)

    def __repr__(self):
        return f"<OrderItem {self.name} x{self.quantity}>"


# ============================================================
# 8. RETURN ITEM — Qaytarilgan mahsulotlar
# ============================================================

class ReturnItem(Base):
    """Buyurtmadan qaytarilgan mahsulotlar (brak yoki ortiqcha)."""
    __tablename__ = "return_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)

    item_name = Column(String(150), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(20), default="dona")
    reason = Column(Enum(ReturnReason), nullable=False)

    refund_amount = Column(Numeric(12, 2), default=0)
    is_refunded = Column(Boolean, default=False)

    notes = Column(Text, nullable=True)
    returned_at = Column(DateTime, default=datetime.utcnow)
    image_url = Column(String(255), nullable=True)  # Mahsulot rasmi (ixtiyoriy)
    coating_applied = Column(Boolean, default=False)  # Brak bo'lganda loy allaqachon tortilganmi

    order = relationship("Order", back_populates="returns")

    def __repr__(self):
        return f"<Return {self.item_name} x{self.quantity} ({self.reason.value})>"


# ============================================================
# 9. INVENTORY PURCHASE — Xomashyo xaridlari jurnali
# ============================================================

class InventoryMovement(Base):
    """Ombor harakatlari jurnali — har bir kirim va chiqim alohida yozuv sifatida.
    Faqat ma'lumot uchun (log) — hisob-kitob va inventar logikasiga hech qanday ta'siri yo'q."""
    __tablename__ = "inventory_movements"

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=True, index=True)
    item_name = Column(String(150), nullable=False)

    movement_type = Column(String(10), nullable=False)  # "in" yoki "out"
    quantity = Column(Float, nullable=False)
    unit = Column(String(20), nullable=True)

    reason = Column(String(200), nullable=True)   # masalan "Yetkazib beruvchi: ABC" yoki "Buyurtma ORD-001-3"
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True, index=True)

    performed_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    inventory = relationship("Inventory")
    order = relationship("Order")
    supplier = relationship("Supplier")


class InventoryPurchase(Base):
    """Har bir ombor kirimi (xarid) — narxi bilan birga saqlanadi."""
    __tablename__ = "inventory_purchases"

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False, index=True)
    inventory = relationship("Inventory")

    item_name = Column(String(150), nullable=False)   # Xarid vaqtidagi nom (tarix uchun)
    quantity = Column(Float, nullable=False)            # Necha kg/dona/litr
    unit = Column(String(20), nullable=True)
    price_per_unit = Column(Numeric(12, 2), nullable=False)  # Shu xariddagi narx
    total_amount = Column(Numeric(12, 2), nullable=False)    # quantity × price_per_unit

    purchased_at = Column(DateTime, default=datetime.utcnow)
    purchased_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    # Nasiya (kredit) bilan olingan bo'lsa
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True, index=True)
    supplier = relationship("Supplier", back_populates="purchases")
    payment_due_date = Column(DateTime, nullable=True)  # Qarzni qachongacha to'lash kerak
    is_credit = Column(Boolean, default=False)
    category = Column(String(50), nullable=True)  # Xarid vaqtidagi kategoriya (tarix uchun saqlanadi)

    def __repr__(self):
        return f"<InventoryPurchase {self.item_name} {self.quantity}>"


# ============================================================
# 8b. EMPLOYEE — Moslashuvchan hodim to'lovi
# ============================================================

class PayType(PyEnum):
    """Hodim to'lov turi — korxonaga qarab har xil bo'lishi mumkin."""
    FIXED = "fixed"                          # Doimiy oylik
    PERCENT_SALES = "percent_sales"          # Sotuvdan foiz
    PERCENT_PROFIT = "percent_profit"        # Foydadan foiz
    PER_UNIT = "per_unit"                    # Har birlik uchun (blok/metr/dona)
    FIXED_PLUS_COATING = "fixed_plus_coating"  # Doimiy oylik + qoplangan metr/dona uchun qo'shimcha


class Employee(Base):
    """Hodim — moslashuvchan to'lov tizimi bilan.
    Har korxona xodimga turlicha haq to'lashi mumkin (SaaS uchun)."""
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    position = Column(String(100), nullable=True)   # Lavozimi: "Kesuvchi", "Qoplovchi" va h.k.

    pay_type = Column(Enum(PayType), default=PayType.FIXED, nullable=False)

    fixed_amount = Column(Numeric(12, 2), default=0)      # FIXED uchun
    percent_value = Column(Float, default=0.0)             # PERCENT_SALES / PERCENT_PROFIT uchun
    per_unit_rate = Column(Numeric(12, 2), default=0)      # PER_UNIT uchun — 1 birlik narxi
    per_unit_type = Column(String(20), default="blok")     # blok / metr / dona

    is_active = Column(Boolean, default=True)
    hire_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)  # "O'chirilgan" — lekin tiklash uchun saqlanadi

    # Hodimning o'z paneliga kirishi uchun (ixtiyoriy — admin belgilaydi)
    phone = Column(String(20), nullable=True, unique=True)
    pin_hash = Column(String(64), nullable=True)

    advance_requests = relationship("AdvanceRequest", back_populates="employee", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Employee {self.name} ({self.pay_type.value})>"


class CashTransaction(Base):
    """Kassa balansiga QO'LDA (admin tomonidan aniq belgilangan) ta'sir
    qiluvchi harakatlar — boshlang'ich balans, Usta KPI to'landi, Ehson
    to'landi. Boshqa kirim/chiqim (mijoz to'lovi, xomashyo xaridi va h.k.)
    — mavjud jadvallardan (Payment, InventoryPurchase va h.k.) to'g'ridan-
    to'g'ri hisoblanadi, bu yerga yozilmaydi."""
    __tablename__ = "cash_transactions"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(30), nullable=False)  # "boshlangich" / "usta_kpi" / "ehson"
    amount = Column(Numeric(12, 2), nullable=False)  # ijobiy=kirim, manfiy=chiqim
    notes = Column(Text, nullable=True)
    performed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CompanySetting(Base):
    """Korxona darajasidagi sozlamalar — kalit/qiymat (masalan Ehson foizi).
    Kelajakda boshqa umumiy sozlamalar ham shu yerga qo'shilishi mumkin."""
    __tablename__ = "company_settings"

    key = Column(String(50), primary_key=True)
    value = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserSession(Base):
    """Foydalanuvchi (admin/menejer/omborchi va h.k.) tizimga kirish sessiyasi —
    bazada saqlanadi (xotirada emas), shuning uchun server qayta ishga
    tushsa ham (Railway uyqu/uyg'onish, deploy) — foydalanuvchilar
    TIZIMDAN CHIQARILMAYDI."""
    __tablename__ = "user_sessions"

    token = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmployeeSession(Base):
    """Xodim (/hodim panel) sessiyasi — bazada saqlanadi, xuddi UserSession kabi."""
    __tablename__ = "employee_sessions"

    token = Column(String(64), primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    """Muhim amallar tarixi — audit uchun (o'chirish/tiklash/yaratish/tahrirlash)."""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(30), nullable=False)          # "deleted" / "restored" / "created" / "updated" / va h.k.
    entity_type = Column(String(30), nullable=False)      # "order" / "project" / va h.k.
    entity_id = Column(Integer, nullable=False)
    entity_label = Column(String(200), nullable=True)     # masalan "ORD-001-1" yoki "PRJ-001 — Hovli fasad"
    old_value = Column(Text, nullable=True)                # o'zgargan maydon(lar)ning eski qiymati (matn/JSON)
    new_value = Column(Text, nullable=True)                # yangi qiymati
    performed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ActivityLog {self.action} {self.entity_type}#{self.entity_id}>"


class LoginHistory(Base):
    """Tizimga kirish urinishlari tarixi — muvaffaqiyatli va muvaffaqiyatsiz."""
    __tablename__ = "login_history"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False)
    success = Column(Boolean, nullable=False)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<LoginHistory {self.username} success={self.success}>"


class ErrorLog(Base):
    """Backend xatoliklari — avtomatik yozib boriladi (diagnostika uchun)."""
    __tablename__ = "error_logs"

    id = Column(Integer, primary_key=True, index=True)
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    endpoint = Column(String(255), nullable=True)
    method = Column(String(10), nullable=True)
    performed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ErrorLog {self.endpoint} {self.created_at}>"


class AdvanceRequestStatus(str, PyEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class AdvanceRequest(Base):
    """Hodim o'zi 'avans oldim' deb yozib qo'yadigan so'rov — admin
    tasdiqlagandan keyingina haqiqiy EmployeeAdvance sifatida hisoblanadi."""
    __tablename__ = "advance_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    requested_date = Column(DateTime, nullable=False)     # "qachon oldim" — hodim yozgan sana
    notes = Column(Text, nullable=True)

    status = Column(Enum(AdvanceRequestStatus), default=AdvanceRequestStatus.PENDING, nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
    confirmed_by = Column(String(100), nullable=True)

    employee = relationship("Employee", back_populates="advance_requests")

    def __repr__(self):
        return f"<AdvanceRequest {self.employee_id} {self.amount} ({self.status.value})>"



class EmployeeAdvance(Base):
    """Hodimga oy davomida berilgan avans (oldindan pul).
    Oy oxirida hisoblangan oylikdan shu summalar ayriladi."""
    __tablename__ = "employee_advances"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    given_by = Column(String(100), nullable=True)

    employee = relationship("Employee", backref="advances")

    def __repr__(self):
        return f"<EmployeeAdvance {self.employee_id}: {self.amount}>"


class RecurringObligation(Base):
    """Har oy takrorlanadigan majburiy xarajat (Arenda, Soliq, Transport,
    Kommunal va ISTALGAN boshqa kategoriya) uchun 'har oy qancha
    to'lanishi KERAK' maqsadini saqlaydi. Admin buni sozlaydi (istalgan
    yangi kategoriya qo'sha oladi), tizim esa har oy buni haqiqiy
    to'lovlar (ExpenseTransaction, shu kategoriyada) bilan solishtirib,
    avtomatik qarz/ogohlantirish chiqaradi."""
    __tablename__ = "recurring_obligations"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(30), unique=True, nullable=False)  # ExpenseTransaction.category bilan bir xil bo'lishi kerak
    label = Column(String(60), nullable=False)  # "Arenda (arendator)", "Transport"
    icon = Column(String(10), default="📦")
    monthly_target = Column(Numeric(12, 2), default=0)  # Har oy qancha to'lanishi kerak
    due_day = Column(Integer, default=5)  # Oyning nechinchi kunigacha to'lanishi kerak (masalan 5 — har oy 5-sanagacha)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<RecurringObligation {self.label}: {self.monthly_target}/oy>"


# ============================================================
# 9c. SUPPLIER — Yetkazib beruvchilar va nasiya qarzi
# ============================================================

class Supplier(Base):
    """Yetkazib beruvchi — xomashyo sotib olinadigan tomon."""
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    phone = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    purchases = relationship("InventoryPurchase", back_populates="supplier")
    payments = relationship("SupplierPayment", back_populates="supplier", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Supplier {self.name}>"


class SupplierPayment(Base):
    """Yetkazib beruvchiga qilingan to'lov (nasiya qarzini yopish uchun)."""
    __tablename__ = "supplier_payments"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False, index=True)
    supplier = relationship("Supplier", back_populates="payments")

    amount = Column(Numeric(12, 2), nullable=False)
    paid_at = Column(DateTime, default=datetime.utcnow)
    paid_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    def __repr__(self):
        return f"<SupplierPayment {self.amount}>"


# ============================================================
# 9b. TRANSPORT EXPENSE — Kirish transporti (xomashyo tashish)
# ============================================================

class TransportExpense(Base):
    """Xomashyo olib kelish uchun transport xarajati (bir mashina, bir necha material)."""
    __tablename__ = "transport_expenses"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    materials_note = Column(String(255), nullable=True)   # "Akril, Kroshka, Mel uchun"
    expense_date = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    def __repr__(self):
        return f"<TransportExpense {self.amount}>"


# ============================================================
# 10. FINISHED PRODUCT — Tayyor mahsulotlar ombori
# ============================================================

class FinishedProduct(Base):
    """Tayyor mahsulot: ishlab chiqarilgan yoki buyurtmadan qaytgan."""
    __tablename__ = "finished_products"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(150), nullable=False, index=True)
    category = Column(String(50), nullable=True)     # profil / panel / dona

    width = Column(Float, nullable=True)
    thickness = Column(Float, nullable=True)
    is_coated = Column(Boolean, default=True)

    quantity = Column(Float, default=0.0)            # Qoldiq (metr yoki dona)
    unit = Column(String(20), default="metr")

    unit_price = Column(Numeric(12, 2), default=0)   # Sotuv narxi (1 metr / 1 dona)
    cost_price = Column(Numeric(12, 2), default=0)   # Tan narxi (jami)

    source = Column(Enum(StockSource), default=StockSource.PRODUCED, nullable=False)

    # Qaytgan bo'lsa — qaysi buyurtmadan
    from_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    from_order = relationship("Order")
    return_reason = Column(String(50), nullable=True)

    # Ishlab chiqarilgan bo'lsa — sarflangan xomashyo
    penoplast_id = Column(Integer, ForeignKey("inventory.id"), nullable=True, index=True)
    penoplast = relationship("Inventory")
    volume_m3 = Column(Float, default=0.0)          # Penoplast hajmi (darhol yechiladi)
    planned_loy_kg = Column(Float, default=0.0)      # Reja qilingan loy
    actual_loy_kg = Column(Float, nullable=True)     # Haqiqiy sarflangan loy ("Tayyor" bosilganda)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=True, index=True)
    recipe = relationship("Recipe")

    production_status = Column(Enum(ProductionStatus), default=ProductionStatus.IN_PROGRESS, nullable=False)
    finished_production_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    image_url = Column(String(255), nullable=True)  # Faqat UI uchun — hisob-kitobga ta'siri yo'q

    @property
    def loy_kg(self):
        """Qaysi loy qiymati aniq — haqiqiysi bo'lsa shuni, bo'lmasa reja."""
        return self.actual_loy_kg if self.actual_loy_kg is not None else self.planned_loy_kg

    def __repr__(self):
        return f"<FinishedProduct {self.name} {self.quantity}{self.unit}>"


# ============================================================
# 11. DELIVERY — Yetkazishlar (bosqichma-bosqich topshirish)
# ============================================================

class Delivery(Base):
    """Buyurtma bo'yicha bir marta yetkazish (bir mashina / bir borish)."""
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)

    delivery_number = Column(String(30), index=True)   # ORD-010-1/Y-2
    delivered_at = Column(DateTime, default=datetime.utcnow)
    delivered_by = Column(String(100), nullable=True)  # Kim topshirdi
    received_by = Column(String(100), nullable=True)   # Kim qabul qildi
    notes = Column(Text, nullable=True)

    # Transport (yetkazib berish)
    transport_carrier = Column(String(150), nullable=True)     # "ABC Transport" / "Mijoz o'zi"
    transport_cost = Column(Numeric(12, 2), default=0)
    transport_payer = Column(String(20), default="none")       # none / client / company / split

    @property
    def company_transport_cost(self):
        """Kompaniya to'laydigan qism."""
        cost = float(self.transport_cost or 0)
        if self.transport_payer == "company":
            return cost
        if self.transport_payer == "split":
            return round(cost / 2)
        return 0.0

    @property
    def client_transport_cost(self):
        """Mijoz to'laydigan qism."""
        cost = float(self.transport_cost or 0)
        if self.transport_payer == "client":
            return cost
        if self.transport_payer == "split":
            return cost - round(cost / 2)
        return 0.0

    order = relationship("Order", back_populates="deliveries")
    items = relationship("DeliveryItem", back_populates="delivery", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Delivery {self.delivery_number}>"


class DeliveryItem(Base):
    """Yetkazishdagi bitta detal miqdori."""
    __tablename__ = "delivery_items"

    id = Column(Integer, primary_key=True, index=True)
    delivery_id = Column(Integer, ForeignKey("deliveries.id"), nullable=False, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=False, index=True)

    quantity = Column(Float, nullable=False)   # Shu safar berilgan miqdor
    unit = Column(String(20), default="dona")  # metr / dona

    delivery = relationship("Delivery", back_populates="items")
    order_item = relationship("OrderItem", back_populates="deliveries")

    def __repr__(self):
        return f"<DeliveryItem {self.quantity}>"


# ============================================================
# 12. PAYMENT — To'lovlar tarixi
# ============================================================

class Payment(Base):
    """Buyurtma bo'yicha to'lovlar tarixi.
    Bir buyurtmaga bir necha marta to'lash mumkin."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    delivery_id = Column(Integer, ForeignKey("deliveries.id"), nullable=True, index=True)  # Qaysi yukka bog'liq (ixtiyoriy)

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
# 12b. ORDER ATTACHMENT — Buyurtmaga biriktirilgan fayl/rasmlar
# ============================================================

class OrderAttachment(Base):
    """Buyurtmaga biriktirilgan umumiy fayl yoki rasmlar (obyekt fotosi, hujjat va h.k.).
    Hisob-kitobga hech qanday ta'siri yo'q — faqat ma'lumot uchun."""
    __tablename__ = "order_attachments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)

    file_url = Column(String(255), nullable=False)
    file_name = Column(String(150), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    uploaded_by = Column(String(100), nullable=True)

    order = relationship("Order", back_populates="attachments")


# ============================================================
# 13. MONTHLY EXPENSE — Oylik xarajatlar
# ============================================================

class ExpenseTransaction(Base):
    """Har bir xarajatni ALOHIDA tranzaksiya sifatida saqlaydi (SaaS arxitekturasi uchun).

    MUHIM: bu jadval MonthlyExpense'ni ALMASHTIRMAYDI — ikkalasi parallel ishlaydi.
    Oylik hisobot (get_monthly_report) avval shu jadvaldan tranzaksiyalarni qidiradi;
    agar topilmasa (eski oylar), MonthlyExpense'dan o'qishda davom etadi — to'liq
    orqaga moslik saqlanadi.
    """
    __tablename__ = "expense_transactions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False, default=datetime.utcnow)
    category = Column(String(30), nullable=False)  # arenda / elektr / tushlik / soliqlar / boshqa
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    notes = Column(Text, nullable=True)

    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 'monthly_form' — Moliya sahifasidagi oylik forma orqali avtomatik yaratilgan
    # 'manual'       — kelajakda alohida "xarajat qo'shish" orqali qo'lda kiritilgan
    source = Column(String(20), default="manual")

    def __repr__(self):
        return f"<ExpenseTransaction {self.category}: {self.amount}>"


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
    soliqlar   = Column(Numeric(12, 2), default=0)  # Qo'lda kiritiladi (yagona/ijtimoiy va h.k. jami)

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
