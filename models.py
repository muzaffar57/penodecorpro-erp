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

from datetime import datetime, timedelta


def _uzb_now():
    """O'zbekiston vaqti (UTC+5) — faqat 'Tizim jurnallari' kabi, faqat
    inson o'qishi uchun mo'ljallangan yozuvlarda ishlatiladi (biznes
    hisob-kitoblarida emas, ular hamon UTC bilan ishlaydi)."""
    return datetime.utcnow() + timedelta(hours=5)
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Enum, Text, Numeric, text as sa_text, UniqueConstraint
)
from sqlalchemy import event
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.orm import Session as SASession
from sqlalchemy.orm.attributes import get_history

Base = declarative_base()


# ============================================================
# PUL — tiyin aniqligi va "qarz yo'q" chegarasi (kech92, 119-band)
# ============================================================
# HAQIQIY PostgreSQL 16 va SQLite da O'LCHANGAN (`work/probe119.py`, asl kod =
# zip 85): to'langan summa `float` lar yig'indisi sifatida hisoblanardi va
# kelishilgan summa bilan QAT'IY (`paid < agreed`) solishtirilardi:
#   * tiyinli qaytarishlar (3 × −166 517.15) yoki tiyinli to'lovlar
#     (2 674.60 + 1 236.47 = 3 911.07) dan keyin to'langan = 3911.0699999999997
#     — qarz 4.5e-13, holat "qisman", buyurtma arxivga O'TMASDI;
#   * UI yo'li: kelishilgan 461 538.40, mijoz ko'rinib turgan qarzni
#     (`formatNum` — butun so'm) 461 538 to'laydi → qarz 0.40000000002, holat
#     "qisman", dashboard qarzdorlar ro'yxatida, 30 kundan keyin "qarzdor"
#     ogohlantirishi; "chegirmaga yozish" esa 0.5 so'mdan kichik qoldiqni
#     yozmaydi (BERK KO'CHA); kelishilgan .75 da ko'rinib turgan qarz
#     (461 539) to'lansa — "qarzdan 0 so'mga ko'p" degan tasdiq (409).
# Tizimdagi mavjud qoida — 0.5 so'mdan kichik qoldiq "qarz yo'q" (qarzdorlar
# sahifasi va hisobot `> 0.5`, "chegirmaga yozish" `> 0.5`, majburiyatlar
# `<= 0.5`), UI esa qarzni butun so'mda ko'rsatadi va butun so'm qabul qiladi.
# Endi buyurtma qarzi / holati / ortiqcha to'lov tekshiruvi ham AYNAN shu
# qoidada: yig'indi va ayirma tiyinga yaxlitlanadi (bazadagi `Numeric(12,2)`
# kabi — HALF_UP), qoldiq `QARZ_BARDOSH` dan oshmasa — qarz 0.
QARZ_BARDOSH = 0.5


def pul_tiyin(v) -> float:
    """Pul qiymati — 2 xonaga HALF_UP (bazadagi `Numeric(12,2)` va
    `crud._pul2` bilan AYNAN). Manfiy nol (−0.0) qaytmaydi."""
    from decimal import Decimal, ROUND_HALF_UP
    return float(Decimal(repr(float(v or 0))).quantize(Decimal("0.01"),
                                                       rounding=ROUND_HALF_UP)) + 0.0


def pul_tiyin_yigindi(qiymatlar) -> float:
    """Pul qiymatlari yig'indisi — `Decimal` da ANIQ qo'shiladi (float
    shovqini to'planmaydi), natija tiyinga yaxlitlanadi."""
    from decimal import Decimal, ROUND_HALF_UP
    jami = Decimal("0")
    for v in qiymatlar:
        jami += Decimal(repr(float(v or 0)))
    return float(jami.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) + 0.0


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

    __table_args__ = (
        UniqueConstraint("company_id", "telegram_id",
                         name="uq_user_company_telegram"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # 2026-09-18 — SaaS ko'p-tenantlilik, 1-QADAM (poydevor).
    # Butun tizimda "bu so'rov qaysi korxonaniki?" degan savolga javob
    # beradigan YAGONA manba shu ustun: foydalanuvchi login qiladi ->
    # uning company_id si aniqlanadi -> qolgan hamma so'rov shu bo'yicha
    # filtrlanadi (keyingi bosqichlarda, jadval-jadval qo'shiladi).
    #
    # MUHIM: bu ustunni bazaga saas_migration.py (1-qadam) qo'shadi —
    # backfill, indeks, tashqi kalit va NOT NULL bilan birga. Kod ANA
    # SHUNDAN KEYIN yangilanadi. Agar yangi muhitda (masalan `main`)
    # migratsiya ishlatilmasdan shu kod joylashtirilsa, `users` jadvalida
    # ustun bo'lmagani uchun login ishlamaydi — shuning uchun HAR BIR
    # muhitda avval migratsiya, keyin kod.
    #
    # Bazada ustunda vaqtinchalik DEFAULT 1 bor (o'tish davri uchun).
    # U keyingi bosqichda, barcha yozuv nuqtalari company_id ni aniq
    # yuboradigan bo'lgandan keyin OLIB TASHLANADI — aks holda unutilgan
    # company_id jimgina 1-korxonaga tushib qoladi (ma'lumot sizib chiqishi).
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)

    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.MANAGER)
    full_name = Column(String(100))
    # 2026-09-19 — Faza 5: `Master.telegram_id` bilan bir xil sabab —
    # bir odam ikki korxonada foydalanuvchi bo'la olishi kerak.
    telegram_id = Column(String(50), nullable=True, index=True)
    # 2026-09-19 — Faza 3: PLATFORMA admini (SaaS egasi).
    # `admin_only` — bu KORXONA admini; har bir mijozning admini shu
    # huquqqa ega. Platforma darajasidagi amallar (Telegram bot sozlamasi,
    # global zaxira yuborish) esa faqat shu bayroqqa ega foydalanuvchiga
    # ochiq bo'lishi kerak.
    is_platform_admin = Column(Boolean, default=False, nullable=False,
                               server_default=sa_text("false"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.username} ({self.role.value})>"


# ============================================================
# 2. MASTER
# ============================================================

class Master(Base):
    __tablename__ = "masters"

    # 2026-09-18 — W2b: bu cheklov endi KORXONA ICHIDA yagona.
    # Ilgari butun tizim bo'yicha yagona edi, ya'ni ikkinchi korxona
    # bir xil qiymatni umuman qo'sha olmasdi. Nomi bazadagi indeks
    # nomi bilan AYNAN bir xil bo'lishi shart.
    __table_args__ = (
        UniqueConstraint("company_id", "telegram_id",
                         name="uq_master_company_telegram"),
        UniqueConstraint("company_id", "phone",
                         name="uq_masters_company_phone"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G2.
    # Bazaga saas_migration.py (W2G2) qo'shadi. Kod ANA SHUNDAN KEYIN
    # yangilanadi — har bir muhitda avval migratsiya, keyin kod.
    # server_default SHART: usiz SQLAlchemy ustunni INSERT'ga NULL qilib
    # qo'shib yuboradi va NOT NULL buziladi (G1 da shu xato chiqqan edi).
    # Vaqtinchalik; barcha yozuv nuqtalari company_id ni aniq yuboradigan
    # bo'lgach, baza DEFAULT'i bilan birga olib tashlanadi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    # 2026-09-19 — Faza 3 (Telegram): ilgari `unique=True` edi, ya'ni
    # bitta Telegram hisobi butun tizimda FAQAT BITTA usta bo'la olardi.
    # SaaS uchun bu noto'g'ri: bir usta ikki korxonada ishlashi mumkin.
    # Endi cheklov `(company_id, telegram_id)` juftligi bo'yicha — pastdagi
    # `__table_args__` da.
    telegram_id = Column(String(50), nullable=True, index=True)
    cashback_percent = Column(Float, default=0.0)
    kpi_percent = Column(Float, default=0.0)   # Yillik KPI % — yillik sotuvdan, yil oxiri sovg'a uchun
    is_active = Column(Boolean, default=True)
    hire_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    region = Column(String(50), nullable=True)  # Faqat UI/tahlil uchun — hisob-kitobga ta'siri yo'q

    orders = relationship("Order", back_populates="master")

    def __repr__(self):
        return f"<Master {self.name} ({self.cashback_percent}%)>"


class MasterGift(Base):
    """Ustalar uchun "Sovg'alar" bosqichlari — botda, yillik yig'ilgan
    KPI (foyda foizi) miqdoriga qarab, qaysi sovg'aga yetilgani va
    keyingisiga necha % qolgani ko'rsatiladi. Aniq so'm miqdori ustaga
    HECH QACHON ko'rsatilmaydi — faqat progress."""
    __tablename__ = "master_gifts"

    id = Column(Integer, primary_key=True, index=True)

    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G2.
    # Bazaga saas_migration.py (W2G2) qo'shadi. Kod ANA SHUNDAN KEYIN
    # yangilanadi — har bir muhitda avval migratsiya, keyin kod.
    # server_default SHART: usiz SQLAlchemy ustunni INSERT'ga NULL qilib
    # qo'shib yuboradi va NOT NULL buziladi (G1 da shu xato chiqqan edi).
    # Vaqtinchalik; barcha yozuv nuqtalari company_id ni aniq yuboradigan
    # bo'lgach, baza DEFAULT'i bilan birga olib tashlanadi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    name = Column(String(100), nullable=False)
    kpi_threshold = Column(Float, nullable=False)   # shu sovg'a uchun kerakli yillik KPI (so'm)
    sort_order = Column(Integer, default=0)
    image_url = Column(String(255), nullable=True)   # botda ko'rsatiladigan surat
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MasterGift {self.name} ({self.kpi_threshold})>"


class MasterGiftRedemption(Base):
    """Ustaga QO'LGA BERILGAN sovg'alar tarixi. Bitta sovg'a "berildi" deb
    belgilanganda, uning qiymati ustaning yig'ilgan KPI hisobidan AYIRILADI
    — shunda u keyingi sovg'aga qarab, YANGIDAN hisoblana boshlaydi
    (2026-08-28, foydalanuvchi so'rovi bo'yicha).

    ESLATMA (2026-09-12): bu — ESKI, yillik/foyda-asosidagi sovg'a tizimi.
    Yangi ishlar uchun pastdagi GiftPeriod / MasterGiftPeriodRedemption
    (savdo-summasi asosidagi, davriy) tizimidan foydalaning. Eski tizim
    hozircha o'chirilmagan (tarix saqlanishi uchun), lekin botda endi
    ishlatilmaydi."""
    __tablename__ = "master_gift_redemptions"

    id = Column(Integer, primary_key=True, index=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False, index=True)
    gift_id = Column(Integer, ForeignKey("master_gifts.id"), nullable=False)
    gift_name = Column(String(100), nullable=False)   # nusxa — sovg'a keyin o'chirilsa ham tarix saqlansin
    kpi_value = Column(Float, nullable=False)          # nusxa — sovg'a narxi keyin o'zgarsa ham tarix saqlansin
    redeemed_at = Column(DateTime, default=datetime.utcnow)
    redeemed_by = Column(String(100), nullable=True)   # qaysi admin belgilagani

    def __repr__(self):
        return f"<MasterGiftRedemption master={self.master_id} gift={self.gift_name}>"


class GiftPeriod(Base):
    """Davriy sovg'a kampaniyasi (2026-09, foydalanuvchi so'rovi bo'yicha —
    doimiy emas, yiliga taxminan 2 marta ochiladi/yopiladi). Faol bo'lganda,
    BARCHA faol ustalarning SAVDO SUMMASI (foyda emas) alohida hisoblanadi
    va bosqichlarga (GiftPeriodTier) solishtiriladi. Bir vaqtning o'zida
    faqat bitta davr faol bo'lishi mumkin (crud.open_gift_period tekshiradi).
    Davr davomidagi buyurtmalar/sotuvlar oddiy keshbek (Bonuslarim)
    hisobidan chiqarib tashlanadi — ikki marta hisoblanmasligi uchun."""
    __tablename__ = "gift_periods"

    id = Column(Integer, primary_key=True, index=True)

    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G2.
    # Bazaga saas_migration.py (W2G2) qo'shadi. Kod ANA SHUNDAN KEYIN
    # yangilanadi — har bir muhitda avval migratsiya, keyin kod.
    # server_default SHART: usiz SQLAlchemy ustunni INSERT'ga NULL qilib
    # qo'shib yuboradi va NOT NULL buziladi (G1 da shu xato chiqqan edi).
    # Vaqtinchalik; barcha yozuv nuqtalari company_id ni aniq yuboradigan
    # bo'lgach, baza DEFAULT'i bilan birga olib tashlanadi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    created_by = Column(String(100), nullable=True)

    tiers = relationship("GiftPeriodTier", backref="period", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<GiftPeriod #{self.id} active={self.is_active}>"


class GiftPeriodTier(Base):
    """Bitta sovg'a davri ichidagi bosqich: 'X so'mlik savdoga — Y sovg'a'.
    threshold_amount — RESET'dan keyingi (checkpoint'dan keyingi) yangi
    savdo summasi, jami yig'indi emas."""
    __tablename__ = "gift_period_tiers"

    id = Column(Integer, primary_key=True, index=True)
    # 2026-09-19 — Faza 3: model qo'riqchisi (`_TENANT_RULES`) ota yozuvda
    # `company_id` ustunini qidiradi; bu jadvalda u yo'q edi, shuning uchun
    # `MasterGiftPeriodRedemption.tier_id` zanjiri tekshirilmay qolardi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    period_id = Column(Integer, ForeignKey("gift_periods.id"), nullable=False, index=True)
    gift_name = Column(String(100), nullable=False)
    threshold_amount = Column(Numeric(12, 2), nullable=False)
    sort_order = Column(Integer, default=0)

    def __repr__(self):
        return f"<GiftPeriodTier {self.gift_name} ({self.threshold_amount})>"


class MasterGiftPeriodRedemption(Base):
    """Davr ichida ustaga QO'LGA BERILGAN sovg'alar tarixi — bitta davrda
    bir nechta marta bo'lishi mumkin (har safar berilganda, ustaning
    hisoblagichi RESET bo'ladi, keyingi bosqich uchun yangidan boshlanadi).

    kind='gift' — admin tomonidan qo'lda "Berildi" deb belgilangan yozuv.
    kind='cashback_conversion' — davr YOPILGANDA, ustaning reset'dan keyingi
    ULGURMAGAN (hech bir bosqichga yetmagan yoki yetib ulgurmagan) qoldiq
    savdosi avtomatik keshbekka aylantirilgani haqidagi yozuv (tier_id=None,
    profit_amount — keshbekka qo'shilgan aniq summa)."""
    __tablename__ = "master_gift_period_redemptions"

    id = Column(Integer, primary_key=True, index=True)
    period_id = Column(Integer, ForeignKey("gift_periods.id"), nullable=False, index=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False, index=True)
    tier_id = Column(Integer, ForeignKey("gift_period_tiers.id"), nullable=True)
    gift_name = Column(String(100), nullable=False)
    sales_amount = Column(Numeric(12, 2), nullable=False)
    profit_amount = Column(Numeric(12, 2), nullable=True)
    kind = Column(String(20), default="gift", nullable=False)
    redeemed_at = Column(DateTime, default=datetime.utcnow)
    redeemed_by = Column(String(100), nullable=True)

    def __repr__(self):
        return f"<MasterGiftPeriodRedemption {self.gift_name} ({self.kind})>"


class GiftPeriodParticipant(Base):
    """Agar davr ochilganda ADMIN aniq ustalarni tanlagan bo'lsa (hammasi
    emas), ular shu yerda saqlanadi. Bitta davr uchun bu yerda HECH QANDAY
    yozuv bo'lmasa — demak o'sha davrda BARCHA faol ustalar ishtirok etadi
    (standart holat, 2026-09-12gacha yagona xatti-harakat edi)."""
    __tablename__ = "gift_period_participants"

    id = Column(Integer, primary_key=True, index=True)
    period_id = Column(Integer, ForeignKey("gift_periods.id"), nullable=False, index=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False, index=True)

    def __repr__(self):
        return f"<GiftPeriodParticipant period={self.period_id} master={self.master_id}>"


# ============================================================
# 3. INVENTORY
# ============================================================

class Inventory(Base):
    __tablename__ = "inventory"

    # 2026-09-18 — W2b: bu cheklov endi KORXONA ICHIDA yagona.
    # Ilgari butun tizim bo'yicha yagona edi, ya'ni ikkinchi korxona
    # bir xil qiymatni umuman qo'sha olmasdi. Nomi bazadagi indeks
    # nomi bilan AYNAN bir xil bo'lishi shart.
    __table_args__ = (
        UniqueConstraint("company_id", "item_name",
                         name="uq_inventory_company_item_name"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G1.
    # Bazaga saas_migration.py (W2G1) qo'shadi: backfill, indeks, tashqi
    # kalit va NOT NULL bilan birga. Kod ANA SHUNDAN KEYIN yangilanadi —
    # har bir muhitda avval migratsiya, keyin kod.
    # Ustunda hozircha vaqtinchalik DEFAULT 1 bor; u barcha yozuv
    # nuqtalari company_id ni aniq yuboradigan bo'lgach olib tashlanadi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    item_name = Column(String(100), nullable=False, index=True)
    stock_quantity = Column(Float, default=0.0)
    unit = Column(String(20), nullable=False)
    min_stock = Column(Float, default=0.0)
    price_per_unit = Column(Numeric(12, 2), nullable=True)
    volume_per_unit = Column(Float, default=1.0)  # Umumiy: 1 birlik (blok/rulon/qop) qancha (m³/m²/kg) — Penoplast blok hajmi, Serpiyanka rulon, GIPS qop og'irligi (kg) va h.k. uchun
    is_penoplast = Column(Boolean, default=False)  # Penoplast (plotnost) turimi
    is_default_penoplast = Column(Boolean, default=False)  # Asosiy plotnost
    category = Column(String(50), nullable=True)  # Penoplast / Qumlar / Kimyoviy moddalar / Boshqa
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = Column(Text, nullable=True)
    image_url = Column(String(255), nullable=True)  # Faqat UI uchun — hisob-kitobga ta'siri yo'q
    serp_ratio_per_m2 = Column(Float, nullable=True)  # Bazalt uchun: 1 m² bazaltga necha m² serpiyanka
    kley_ratio_per_m2 = Column(Float, nullable=True)  # Bazalt uchun: 1 m² bazaltga necha kg kley
    is_deleted = Column(Boolean, default=False)  # "O'chirilgan" — lekin eski buyurtma/harakat tarixi uchun saqlanadi

    # 2026-09-16: Dinamik Production/MRP moduli uchun — BIRLIK KONVERSIYASI.
    # Muammo: xomashyo RETSEPTDA mayda birlikda (masalan gramm, ml) yozilishi
    # kerak bo'lishi mumkin, lekin OMBORDA yirik birlikda (tonna, qop-50kg,
    # bochka-200L) saqlanadi. Ikkalasi ham NULL bo'lsa — eski (2026-09-16
    # gacha bo'lgan) xatti-harakat: retsept ham ombor birligi (`unit`)da
    # yoziladi, konversiya YO'Q. Faqat Production moduli o'qiydi — qolgan
    # butun tizim (Order/Recipe/FinishedProduct) bu ikki ustunga umuman
    # tegmaydi va ularsiz avvalgidek ishlashda davom etadi.
    base_unit = Column(String(20), nullable=True)  # Retseptda ishlatiladigan MAYDA birlik — masalan "g", "ml". Bo'sh bo'lsa, retsept ham shu materialning `unit` birligida yoziladi.
    conversion_factor = Column(Float, nullable=True)  # 1 dona `unit` (ombor birligi) necha dona `base_unit`ga teng. Masalan: unit="qop", base_unit="g", conversion_factor=50000 (1 qop = 50000 gramm). Faqat base_unit to'ldirilganda ishlatiladi.

    def __repr__(self):
        return f"<Inventory {self.item_name}: {self.stock_quantity} {self.unit}>"


# ============================================================
# 4. RECIPE
# ============================================================

class Recipe(Base):
    __tablename__ = "recipes"

    # 2026-09-18 — W2b: bu cheklov endi KORXONA ICHIDA yagona.
    # Ilgari butun tizim bo'yicha yagona edi, ya'ni ikkinchi korxona
    # bir xil qiymatni umuman qo'sha olmasdi. Nomi bazadagi indeks
    # nomi bilan AYNAN bir xil bo'lishi shart.
    __table_args__ = (
        UniqueConstraint("company_id", "name",
                         name="uq_recipes_company_name"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G1.
    # Bazaga saas_migration.py (W2G1) qo'shadi: backfill, indeks, tashqi
    # kalit va NOT NULL bilan birga. Kod ANA SHUNDAN KEYIN yangilanadi —
    # har bir muhitda avval migratsiya, keyin kod.
    # Ustunda hozircha vaqtinchalik DEFAULT 1 bor; u barcha yozuv
    # nuqtalari company_id ni aniq yuboradigan bo'lgach olib tashlanadi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    name = Column(String(100), nullable=False)  # Endi ISTALGAN nom bo'lishi mumkin

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

    # 2026-09-18 — W2b: bu cheklov endi KORXONA ICHIDA yagona.
    # Ilgari butun tizim bo'yicha yagona edi, ya'ni ikkinchi korxona
    # bir xil qiymatni umuman qo'sha olmasdi. Nomi bazadagi indeks
    # nomi bilan AYNAN bir xil bo'lishi shart.
    __table_args__ = (
        UniqueConstraint("company_id", "project_number",
                         name="uq_projects_company_project_number"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G1.
    # Bazaga saas_migration.py (W2G1) qo'shadi: backfill, indeks, tashqi
    # kalit va NOT NULL bilan birga. Kod ANA SHUNDAN KEYIN yangilanadi —
    # har bir muhitda avval migratsiya, keyin kod.
    # Ustunda hozircha vaqtinchalik DEFAULT 1 bor; u barcha yozuv
    # nuqtalari company_id ni aniq yuboradigan bo'lgach olib tashlanadi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    project_number = Column(String(20), index=True)  # PRJ-001
    client_name = Column(String(100), nullable=False)
    client_phone = Column(String(20), nullable=True)
    client_address = Column(Text, nullable=True)

    project_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    status = Column(Enum(ProjectStatus), default=ProjectStatus.DRAFT, nullable=False)

    total_budget = Column(Numeric(12, 2), default=0)
    total_paid = Column(Numeric(12, 2), default=0)
    # kech86 (100-band, QAROR "A"): loyihada BERILGAN eng katta buyurtma tartib raqami (ORD-051-<N>).
    # Raqam HECH QACHON qayta berilmaydi — o'chirilgan buyurtmaning raqami ham band qoladi. NULL — hali
    # hisoblanmagan (`main._migrate_buyurtma_raqam_hisoblagich` yoki birinchi buyurtma to'ldiradi).
    # `default=` ATAYLAB YO'Q (sync_missing_columns eski qatorlarga 0 yozib, jurnal hisobini o'tkazib yuborardi).
    oxirgi_buyurtma_seq = Column(Integer, nullable=True)

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

    # 2026-09-18 — W3b: buyurtma raqami endi KORXONA ICHIDA yagona.
    # Nomi bazadagi indeks nomi bilan AYNAN bir xil bo'lishi shart.
    __table_args__ = (
        UniqueConstraint("company_id", "order_number",
                         name="uq_orders_company_order_number"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # 2026-09-18 — SaaS ko'p-tenantlilik, 3-to'lqin.
    # DIQQAT: bu ustunning qiymati 1 EMAS, buyurtmaning O'Z LOYIHASIDAN
    # olinadi (crud.create_order). Bazadagi DEFAULT 1 faqat o'tish davri
    # uchun zaxira — unga TAYANIB BO'LMAYDI: sinovda 2-korxona loyihasiga
    # yaratilgan buyurtma DEFAULT tufayli 1-korxonaga tushib qolgan edi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    order_number = Column(String(20), index=True)

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
    is_pinned = Column(Boolean, default=False)              # "Pin qilingan" — muhim buyurtmalar ro'yxati tepasida (2026-09-13)
    # kech77 (95-band, K77-1): buyurtma o'chirilganda buyurtma LOYI bo'yicha HAQIQATDA qo'llangan miqdor (kg):
    # musbat — omborga QAYTGAN, manfiy — qo'shimcha YECHILGAN (hodim rejadan ko'p ishlatilgan deb yozganda), 0 — hech
    # narsa. `crud.restore_order` AYNAN shuni teskari qiladi. NULL — kech77 dan OLDIN o'chirilgan (yoki hali
    # o'chirilmagan) buyurtma: tiklash eski qoida bilan (reja × qolgan ulush) — o'shanda UI miqdor so'ramasdi.
    ochirishda_loy_kg = Column(Float, nullable=True)
    # kech82 (102-band, QAROR "A"): buyurtma LOYI qayerdan olingani (retsept bo'yicha, JSON):
    # {"r": {"<retsept_id>": {"z": tayyor loy zaxirasidan, "x": xom ingredientlardan}}, "o": {...}} — "r" ushlab
    # turilgan loy, "o" — o'chirish nima qilgani (+ qaytgan, − qo'shimcha yechilgan; tiklash AYNAN teskarisi).
    # Loy qaytganda avval xom qism, qolgani zaxiraga (`services` dagi "BUYURTMA LOYI OLINGAN JOYIGA QAYTADI").
    # NULL — migratsiyadan OLDINGI buyurtma: eski qoida (qaytish xomga, tiklash xomdan).
    loy_manba_json = Column(Text, nullable=True)
    # kech86 (QAROR "A" yuk xatiga ham): shu buyurtmada BERILGAN eng katta yuk xati tartib raqami (…/Y-<N>).
    # Yuk xati o'chirilsa ham raqami qayta berilmaydi. NULL — hali yuk yo'q yoki eski buyurtma (mavjud yuklardan
    # hisoblanadi). `default=` ATAYLAB YO'Q.
    oxirgi_yuk_seq = Column(Integer, nullable=True)
    stock_returned = Column(Boolean, default=False)         # O'chirilganda ombor QAYTARILGANMI — takroriy (tiklab-qayta o'chirilganda ikki marta) qaytarib yubormaslik uchun

    master_id = Column(Integer, ForeignKey("masters.id"), nullable=True, index=True)
    master = relationship("Master", back_populates="orders")

    created_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)            # Qarz yopilgan sana

    notes = Column(Text, nullable=True)

    # GIPS — asosiy xomashyo miqdori (Loy kabi: boshida taxminiy, "Tayyor"
    # bosilganda haqiqiy). Alohida ustunlarda saqlanadi (notes matni ichiga
    # "belgi" qilib yozish EMAS) — shunday qilib boshqa belgilar (masalan
    # [WRITEOFF:...]) bilan to'qnashib, o'qishda xato bermaydi.
    planned_gips_kg = Column(Float, nullable=True)
    actual_gips_kg = Column(Float, nullable=True)
    actual_loy_kg = Column(Float, nullable=True)  # Haqiqiy Loy (qoplama) miqdori — "Tayyor" bosilganda kiritiladi
    planned_loy_kg = Column(Float, nullable=True)  # Rejalashtirilgan Loy (qoplama) — buyurtma yaratilganda/tahrirlashda
    # kech58 (K58-1 / K58-2 / K58-3, 43-band): buyurtmaning UMUMIY qoplama loyi qaysi retseptdan
    # yechilgan / yechiladi. FAQAT kech58 dan keyin YARATILGAN buyurtmaga yoziladi (foydalanuvchi
    # qarori: eski buyurtmalar foydasi o'zgarmaydi); eski (NULL) — avvalgi qoida AYNAN
    # (`services.buyurtma_qoplama_retsept_nomzodlari`). Retsept o'chirilsa — NULL (PG).
    qoplama_retsept_id = Column(Integer, ForeignKey("recipes.id", ondelete="SET NULL"),
                                nullable=True, index=True)
    base_price = Column(Numeric(12, 2), nullable=True)  # "1 m³ asosiy narxi" — hodim kiritgan, tahrirlashda tiklanishi uchun
    gips_inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=True)  # Aniq qaysi Gips xomashyosi ishlatilgani

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    returns = relationship("ReturnItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")
    deliveries = relationship("Delivery", back_populates="order", cascade="all, delete-orphan")
    attachments = relationship("OrderAttachment", back_populates="order", cascade="all, delete-orphan")
    gips_additives = relationship("OrderGipsAdditive", back_populates="order", cascade="all, delete-orphan")

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
        """To'langan jami summa — tiyin aniqligida (kech92, 119-band: `float`
        yig'indisi 448.54999999998836 berardi, to'g'risi 448.55). To'lov
        bo'lmasa — 0 (avvalgidek)."""
        tolovlar = self.payments or []
        if not tolovlar:
            return 0
        return pul_tiyin_yigindi(p.amount for p in tolovlar)

    @property
    def kelishilgan_summa(self):
        """Kelishilgan summa (float).

        kech42 (K42-1, O'LCHANGAN): 0 — HAQIQIY qiymat (to'liq qaytarilib pul
        qaytarilgan yoki qarzi to'liq kechirilgan buyurtma). Ilgari hamma joyda
        `agreed_amount or total_amount` yozilgan edi — 0 "kiritilmagan" deb
        olinib, o'rniga JAMI summa chiqardi: to'lanmagan, to'liq qaytarilgan
        buyurtmada qarz 1 000 000 (asli 0) ko'rinardi. Faqat bo'sh (NULL)
        bo'lsa jami summa olinadi."""
        if self.agreed_amount is not None:
            return float(self.agreed_amount)
        return float(self.total_amount or 0)

    @property
    def debt_amount(self):
        """Qarz qoldi — tiyin aniqligida; `QARZ_BARDOSH` (0.5 so'm) dan
        oshmaydigan qoldiq — qarz YO'Q (kech92, 119-band; UI qarzni butun
        so'mda ko'rsatadi va butun so'm qabul qiladi). Qiymat shakli
        avvalgidek: to'liq to'langan — 0.0, ortiqcha to'langan — 0."""
        qoldiq = pul_tiyin(self.kelishilgan_summa - self.paid_amount)
        if qoldiq > QARZ_BARDOSH:
            return qoldiq
        return 0.0 if qoldiq >= 0 else 0

    def __repr__(self):
        return f"<Order #{self.order_number} (Project #{self.project_id})>"


class OrderGipsAdditive(Base):
    """Gips buyurtmasiga qo'shiladigan ixtiyoriy xomashyo (po'lat sim,
    fibra tola, serpiyanka, penoplast granula va h.k.) — erkin, Omborxonadan
    ISTALGAN materialni tanlab qo'shish mumkin (qattiq ro'yxat emas).
    Har biri — Loy kabi: boshida taxminiy (planned_qty), "Tayyor" bosilganda
    haqiqiy (actual_qty) miqdor bilan to'ldiriladi."""
    __tablename__ = "order_gips_additives"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False, index=True)

    planned_qty = Column(Float, nullable=False, default=0.0)
    actual_qty = Column(Float, nullable=True)
    unit = Column(String(20), nullable=True)  # kg / metr / dona — inventory'dan olingan, ko'rsatish uchun

    order = relationship("Order", back_populates="gips_additives")
    inventory = relationship("Inventory")

    def __repr__(self):
        return f"<OrderGipsAdditive order={self.order_id} inv={self.inventory_id}>"


# ============================================================
# 7. ORDER ITEM
# ============================================================

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    # 2026-09-18 — SaaS ko'p-tenantlilik, 4-to'lqin.
    # Qiymat MIJOZDAN QABUL QILINMAYDI. U har doim ota-yozuvdan olinadi —
    # models.py oxiridagi `_tenant_guard` hodisasi buni avtomatik bajaradi
    # va ota bilan mos kelmasa yozuvni RAD ETADI.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)

    name = Column(String(150), nullable=False)
    category = Column(String(50), nullable=True)

    width = Column(Float, nullable=True)
    thickness = Column(Float, nullable=True)
    length = Column(Float, nullable=True)
    quantity = Column(Float, default=1.0)
    gips_unit = Column(String(10), nullable=True)  # GIPS uchun: metr / dona / m2 (foydalanuvchi tanlaydi)

    is_coated = Column(Boolean, default=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=True, index=True)
    recipe = relationship("Recipe")

    penoplast_id = Column(Integer, ForeignKey("inventory.id"), nullable=True, index=True)  # Qaysi plotnost
    penoplast = relationship("Inventory")
    price_per_m3 = Column(Numeric(12, 2), nullable=True)  # Shu detal uchun 1 m³ narxi

    # Tayyor mahsulotdan olingan bo'lsa — xomashyo hisoblanmaydi
    finished_product_id = Column(Integer, ForeignKey("finished_products.id"), nullable=True, index=True)
    # 2026-09-17: foreign_keys ANIQ ko'rsatildi — chunki endi FinishedProduct
    # tarafida ham OrderItem'ga qarab turuvchi YANGI FK bor
    # (reserved_for_order_item_id, rezervatsiya uchun), shuning uchun
    # SQLAlchemy ikkita jadval orasidagi FK yo'lini avtomatik aniqlay olmaydi.
    finished_product = relationship("FinishedProduct", foreign_keys=[finished_product_id])

    unit_price = Column(Numeric(12, 2), default=0)
    total_price = Column(Numeric(12, 2), default=0)
    # "Donali" turi uchun — hajm (ombordan yechiladigan miqdor) shu
    # narxdan hisoblanadi, unit_price'dan EMAS. Shunday qilib, sotuv
    # narxini (unit_price) keyinroq o'zgartirsangiz ham (masalan
    # qimmatroq sotish uchun), haqiqiy ombordan yechiladigan hajm
    # o'zgarib qolmaydi — "qulflangan" bo'lib qoladi.
    unit_price_for_volume = Column(Numeric(12, 2), nullable=True)

    image_url = Column(String(255), nullable=True)  # Mahsulot rasmi (ixtiyoriy, hisob-kitobga ta'sir qilmaydi)

    notes = Column(Text, nullable=True)

    # 2026-09-16: Production/MRP orqali yaratilgan DINAMIK mahsulot turi
    # tanlangan bo'lsa (category='mrp_product'), shu yerga bog'lanadi.
    # Alohida jadval YO'Q — Production/MRP moduli natijasi ham xuddi shu
    # Inventory/FinishedProduct omboriga tushadi (pastdagi izohga qarang).
    product_type_id = Column(Integer, ForeignKey("product_types.id"), nullable=True, index=True)
    # 2026-09-18: `delivery_unit` shu orqali mahsulot turining O'Z birligini
    # (kg/litr/m²/qop...) oladi. Matn ko'rinishidagi nom ishlatilgan —
    # ProductType `production_models.py`da, lekin SQLAlchemy uni kech
    # (barcha modellar yuklangach) hal qiladi, shuning uchun bu yerda
    # import qilish SHART EMAS (models.py↔production_models.py orasida
    # aylanma import bo'lib qolmasligi uchun ataylab shunday).
    #
    # MUHIM — `lazy="joined"` ISHLATIB BO'LMAYDI (sinovda aniqlangan
    # haqiqiy xato): u har bir OrderItem so'roviga LEFT OUTER JOIN
    # qo'shadi, `production_service.start_production_order()` esa shu
    # jadvalni `.with_for_update()` bilan QULFLAYDI — PostgreSQL bunga
    # yo'l qo'ymaydi: "FOR UPDATE cannot be applied to the nullable side
    # of an outer join". Shuning uchun standart (lazy="select") qoladi:
    # ProductType faqat HAQIQATAN kerak bo'lganda (delivery_unit
    # chaqirilganda) alohida so'rov bilan olinadi.
    product_type = relationship("ProductType")

    order = relationship("Order", back_populates="items")
    deliveries = relationship("DeliveryItem", back_populates="order_item", cascade="all, delete-orphan")

    # Ichki qo'shimcha detallar (masalan karniz ichidagi rebristo/qo'shimcha
    # profil) — xuddi shu xomashyodan (parent bilan bir xil penoplast_id),
    # lekin o'z hajmi/narxi bilan. Yuk xatida ALOHIDA qator sifatida
    # CHIQMAYDI — hajmi asosiy detal hajmiga, narxi asosiy detal narxiga
    # QO'SHIB hisoblanadi (2026-09 — "qo'shimcha detal" so'rovi bo'yicha).
    sub_details = relationship(
        "OrderItemSubDetail",
        back_populates="order_item",
        cascade="all, delete-orphan",
        order_by="OrderItemSubDetail.id"
    )

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
        termopanel kvadrat metrda, GIPS — o'zi tanlangan birlik (metr/dona/m²),
        loy sotish — kg, MRP mahsuloti — o'z mahsulot turining birligi,
        qolgani donada."""
        cat = (self.category or '').lower()
        if cat in ('profil', 'panel', 'blok'):
            return 'metr'
        if cat == 'termopanel':
            return 'm²'
        if cat == 'gips':
            unit = (self.gips_unit or 'metr').lower()
            return 'm²' if unit == 'm2' else unit
        if cat == 'loy_sotish':
            return 'kg'
        # 2026-09-18 (birlik auditi topilmasi — HAQIQIY xato tuzatildi):
        # Production/MRP mahsulotlari bu funksiyadan OLDIN mavjud emas edi,
        # shuning uchun ular pastdagi "dona"ga tushib ketardi — masalan
        # kg'da o'lchanadigan mahsulot ham "dona" deb ko'rsatilardi.
        # Endi mahsulot turining O'Z birligi olinadi (ProductType.unit).
        if cat == 'mrp_product' and self.product_type_id:
            pt = getattr(self, 'product_type', None)
            if pt and pt.unit:
                return pt.unit
        return 'dona'

    @property
    def delivered_qty(self):
        """Jami yetkazilgan miqdor."""
        return sum(float(d.quantity or 0) for d in (self.deliveries or []))

    @property
    def remaining_qty(self):
        """Qolgan (hali topshirilishi kerak) miqdor.

        kech60 (57-band, K59-3): omborga qo'yilgan ORTIQCHA qism (`ortiqcha_qty`) ham
        buyurtmadan chiqqan — u yana topshirilmaydi va o'chirishda xomashyo sifatida
        qaytmaydi. Yetkazish foizi (`Order.delivery_percent`) — faqat topshirilgan."""
        return max(self.order_qty_normalized - self.delivered_qty - self.ortiqcha_qty, 0)

    @property
    def ortiqcha_qty(self):
        """kech60 (57-band): shu detaldan omborga qo'yilgan ortiqcha (mijozga topshirilmagan)
        miqdor — brakdan boshqa, hozir MAVJUD qaytarish yozuvlarining `ortiqcha_miqdor`
        yig'indisi. Yozuv o'chirilsa (22-band — tayyor mahsulot AYNAN olinadi) qism
        buyurtmaga qaytadi."""
        order = self.order
        if order is None or self.id is None:
            return 0.0
        jami = 0.0
        for r in (order.returns or []):
            if r.order_item_id == self.id and r.reason != ReturnReason.DEFECT:
                jami += float(r.ortiqcha_miqdor or 0)
        return jami

    def __repr__(self):
        return f"<OrderItem {self.name} x{self.quantity}>"


class OrderItemSubDetail(Base):
    """Asosiy detal (OrderItem) ICHIDAGI qo'shimcha bo'lak — masalan karniz
    ichidagi rebristo/dekorativ chiziq. Bir nechta bo'lishi mumkin.

    MUHIM: alohida ombor zaxirasi YO'Q — xomashyosi HAR DOIM parent
    OrderItem bilan BIR XIL (parent.penoplast_id/price_per_m3 orqali
    hisoblanadi). Faqat hajm (inventarizatsiya uchun) va narx (audit
    uchun) shu yerda saqlanadi; mijozga ko'rinadigan Yuk xatida bu
    bo'lak ALOHIDA qator sifatida chiqmaydi — parentga qo'shib ko'rsatiladi."""
    __tablename__ = "order_item_sub_details"

    id = Column(Integer, primary_key=True, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(150), nullable=True)          # masalan "Ichki rebristo detal"
    category = Column(String(20), nullable=False, default="profil")  # 'profil' yoki 'panel'

    width = Column(Float, nullable=True)
    thickness = Column(Float, nullable=True)
    length = Column(Float, nullable=True)
    quantity = Column(Float, nullable=True, default=1.0)
    is_coated = Column(Boolean, default=False)

    # Audit uchun — server tomonida hisoblanib saqlanadi (pul hisobiga
    # to'g'ridan-to'g'ri ta'sir qilmaydi, faqat qayta ko'rish/tahrirlash
    # uchun ko'rsatiladi)
    volume_m3 = Column(Float, default=0)
    total_price = Column(Numeric(12, 2), default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    order_item = relationship("OrderItem", back_populates="sub_details")

    def __repr__(self):
        return f"<OrderItemSubDetail {self.name} ({self.category})>"


# ============================================================
# 8. RETURN ITEM — Qaytarilgan mahsulotlar
# ============================================================

class ReturnItem(Base):
    """Buyurtmadan qaytarilgan mahsulotlar (brak yoki ortiqcha) —
    YOKI tayyor mahsulot ishlab chiqarish jarayonidagi brak (buyurtmasiz,
    to'g'ridan-to'g'ri ishlab chiqarilgan mahsulotlar uchun)."""
    __tablename__ = "return_items"

    id = Column(Integer, primary_key=True, index=True)
    # 2026-09-18 — SaaS ko'p-tenantlilik, 6-to'lqin.
    # Qiymat MIJOZDAN QABUL QILINMAYDI. U har doim ota-yozuvdan olinadi —
    # models.py oxiridagi `_tenant_guard` hodisasi buni avtomatik bajaradi
    # va ota bilan mos kelmasa yozuvni RAD ETADI.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    # Tayyor mahsulot ishlab chiqarish jarayonidagi brak uchun — order_id
    # o'rniga shu ishlatiladi (ikkalasidan FAQAT BITTASI to'ldiriladi).
    finished_product_id = Column(Integer, ForeignKey("finished_products.id"), nullable=True, index=True)

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
    gips_kg_used = Column(Float, nullable=True)  # GIPS brak uchun — taxminan qancha gips ketgani (qo'lda kiritiladi)
    # kech39 (5-bo'lim 3-band): qaysi buyurtma DETALIDAN qaytgani. Ilgari faqat
    # `item_name` saqlanardi — bitta buyurtmada bir xil nomli ikki detal bo'lishi
    # mumkin (O'LCHANGAN: `POST /api/orders` 200), shuning uchun detal bo'yicha
    # yig'indini (omborga qaytgan jami <= buyurtmadagi miqdor) hisoblab
    # bo'lmasdi. Yangi yozuvlarda `crud.create_return_item` doim to'ldiradi;
    # eskilari `main._migrate_return_order_item` da FAQAT nomi buyurtmada
    # YAGONA bo'lsa bog'lanadi (qolganlari NULL — taxmin qilinmaydi). Detal
    # o'chirilsa — NULL (PostgreSQL `ON DELETE SET NULL`); oddiy kalit bo'lsa
    # detalni o'chirish FK 23503 bilan 500 berardi (12-banddagi
    # `payments.delivery_id` sinfi).
    order_item_id = Column(Integer, ForeignKey("order_items.id", ondelete="SET NULL"),
                           nullable=True, index=True)
    # kech60 (57-band, K59-3) — qaytarilgan miqdorning mijozga HALI TOPSHIRILMAGAN
    # qismi (ortiqcha mahsulot omborga qo'yilgan). FOYDALANUVCHI QARORI (kech60):
    # "kerak bo'lmay qolgan ortiqcha mahsulotni omborga qo'yamiz" — bunday qaytarish
    # hayotda BOR. Yozilgan paytda hisoblanadi (`crud._qaytarish_ortiqcha_qismi`:
    # avval topshirilgandan, qolgani — ortiqcha). Bu qism buyurtmadan CHIQQAN
    # hisoblanadi (`OrderItem.remaining_qty` dan ayiriladi): yana topshirilmaydi,
    # buyurtma / detal o'chirilganda yoki kamaytirilganda uning xomashyosi IKKINCHI
    # marta qaytmaydi. O'LCHANGAN (asl kod `55b6f69`, `work/probe60_k3.py`): 10 m
    # profildan 5 m omborga qo'yilib buyurtma o'chirilsa penoplast 10 m uchun to'liq
    # qaytardi VA 5 m tayyor mahsulot ham qolardi (25 000 so'm ikki marta); detalni
    # o'chirish, 10 -> 3 m tahrir, qisman topshirilganni o'chirish — xuddi shunday.
    # Brak va detalsiz yozuv — NULL (ishlatilmaydi). Eski yozuvlar migratsiyada
    # (`main._migrate_ortiqcha_qaytarish`) yozilish tartibi bo'yicha to'ldiriladi.
    ortiqcha_miqdor = Column(Float, nullable=True)
    # kech73 (86-band, K72-1): MRP detalidan (ishlab chiqarish buyurtmasi band qilgan tayyor
    # mahsulot) ortiqcha qism omborga qo'yilganda YANGI tayyor mahsulot yaratilmaydi — shu detalga
    # band TM ning bandidan erkin qoldiqqa o'tadi. Qaysi TM dan qancha: JSON `[[tm_id, miqdor], ...]`.
    # O'chirishda AYNAN shu TM larga band qaytadi. Boshqa yozuvlar — NULL (`default=` BERILMAGAN —
    # `sync_missing_columns` eski qatorlarga yozmasin, kech52 saboqi).
    mrp_ozod = Column(Text, nullable=True)
    # kech40 (5-bo'lim 22-band, K39-1) — qaytarish yozuvi O'CHIRILGANDA hammasi
    # AYNAN orqaga qaytishi uchun, yozuv paytida NIMA o'zgargani saqlanadi.
    # O'LCHANGAN (asl kod, SQLite va PostgreSQL): o'chirish faqat yozuvni
    # o'chirardi — omborga qo'shilgan tayyor mahsulot QOLARDI (qayta kiritilsa
    # 10 → 20), pul qaytarilgan bo'lsa kamaytirilgan kelishilgan summa va manfiy
    # to'lov QOLARDI (qayta kiritib yana "pul qaytdi" bosilsa — ikki marta).
    #  * `finished_product_id` (yuqorida, ilgari hech qachon to'ldirilmasdi) +
    #    `stock_qty` / `stock_cost` / `stock_volume_m3` — `add_returned_to_stock`
    #    shu yozuv uchun tayyor mahsulotga AYNAN qancha qo'shgani (miqdor, tan
    #    narxi, penoplast hajmi). Tan narxi keyin o'zgarishi mumkin, shuning uchun
    #    qayta hisoblanmaydi — saqlangani ayiriladi. NULL = omborga tushmagan
    #    (brak, `to_stock=false`) yoki yangilanishdan OLDINGI yozuv (bog'lam
    #    noma'lum — o'chirish omborga tegmaydi, avvalgidek).
    stock_qty = Column(Float, nullable=True)
    stock_cost = Column(Numeric(12, 2), nullable=True)
    stock_volume_m3 = Column(Float, nullable=True)
    #  * FOYDALANUVCHI QARORI (kech40, B): pul qaytarilgan qaytarish o'chirilsa —
    #    kelishilgan summa tiklanadi va manfiy to'lov o'chadi. `refunded_at` —
    #    "pul qaytdi" YANGI kod bilan bosilganining belgisi (manfiy to'lov
    #    `payments.return_item_id` orqali bog'langan); NULL + `is_refunded` =
    #    eski belgilash, to'lov bog'lami yo'q → o'chirish rad etiladi (taxmin
    #    qilinmaydi). `refund_agreed_delta` — kelishilgan summa AYNAN qanchaga
    #    kamaygani (`max(0, …)` tufayli summadan kam bo'lishi mumkin).
    refunded_at = Column(DateTime, nullable=True)
    refund_agreed_delta = Column(Numeric(12, 2), nullable=True)
    # kech53 (13-band, 1-qadam): brak BOSQICHI — ixtiyoriy, faqat brak yozuvida
    # (`crud.BRAK_BOSQICHLARI` kodlari: kesish / qoplash / quritish /
    # saqlash_tashish). NULL — tanlanmagan yoki shu yangilanishdan oldingi yozuv.
    # STANDARTSIZ (kech52 saboqi: `database.sync_missing_columns` ORM `default=`
    # ni ESKI qatorlarga ham yozadi — eski brak "tanlangan" bo'lib qolardi).
    brak_bosqich = Column(String(20), nullable=True)
    # kech56 (13-band, 7-qadam; foydalanuvchi qarori): brak SABABI — ixtiyoriy
    # (`crud.BRAK_SABABLARI` kodlari: xomashyo / ishchi / uskuna / olcham / boshqa) va
    # brakka sabab bo'lgan JAVOBGAR hodim — ixtiyoriy. NULL — tanlanmagan yoki eski
    # yozuv. STANDARTSIZ (kech52 saboqi). Hodim butunlay o'chirilsa — NULL (PG FK).
    brak_sabab = Column(String(20), nullable=True)
    brak_javobgar_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"),
                              nullable=True, index=True)

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
    # 2026-09-18 — SaaS ko'p-tenantlilik, 6-to'lqin.
    # Qiymat MIJOZDAN QABUL QILINMAYDI. U har doim ota-yozuvdan olinadi —
    # models.py oxiridagi `_tenant_guard` hodisasi buni avtomatik bajaradi
    # va ota bilan mos kelmasa yozuvni RAD ETADI.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=True, index=True)
    item_name = Column(String(150), nullable=False)

    movement_type = Column(String(10), nullable=False)  # "in" yoki "out"
    quantity = Column(Float, nullable=False)
    unit = Column(String(20), nullable=True)

    reason = Column(String(200), nullable=True)   # masalan "Yetkazib beruvchi: ABC" yoki "Buyurtma ORD-001-3"
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True, index=True)
    # kech45 (13-band, 6-qadam): shu harakatni yaratgan BRAK yozuvi (buyurtma
    # detali braki uchun ombordan yechilgan penoplast / loy). Brak yozuvi
    # o'chirilganda AYNAN shu harakatlar topilib, miqdori omborga qaytariladi.
    # Eski harakatlarda NULL — bog'lam noma'lum, ularga tegilmaydi.
    return_item_id = Column(Integer, ForeignKey("return_items.id", ondelete="SET NULL"),
                            nullable=True, index=True)
    # kech46 (13-band, 2-qadam): CHIQIM ("out") paytidagi materialning 1 birlik
    # narxi (`inventory.price_per_unit`) — muzlatilgan. Brak xarajati hisoboti
    # va sof foyda shu narxni o'qiydi, shuning uchun keyinroq narx o'zgarsa
    # o'tgan oy brakining qiymati o'zgarmaydi. Kirim ("in") va ushbu
    # yangilanishdan OLDINGI harakatlarda NULL — hisobot ular uchun joriy
    # narxni ishlatadi (avvalgidek; eski narx noma'lum, taxmin qilinmaydi).
    unit_cost = Column(Float, nullable=True)
    # kech52 (13-band, 3-qadam): BRAK harakati belgisi. Brak xarajati hisoboti
    # (`crud.get_brak_material_summary` → Moliya, oylik hisobot, sof foyda,
    # liniya hisoboti) va buyurtma tan narxidan brakni ajratish
    # (`services._buyurtma_sarf_narxlari`) endi sabab MATNIGA ("Brak%") emas,
    # shu belgiga qaraydi — sabab matni o'zgarsa (tarjima, yangi yozuv shakli)
    # hisobot jimgina nolga tushmaydi. Yangi harakatda HAR DOIM True / False
    # (`crud.log_movement` va `services.deduct_raw_material_for_brak` yozadi).
    # NULL — shu yangilanishdan OLDINGI harakat: `main._migrate_brak_belgisi()`
    # uni eski ta'rif bilan (bog'langan YOKI sabab "Brak%") to'ldiradi; o'qishda
    # ham NULL qator eski ta'rif bilan baholanadi (`crud.brak_harakati_sharti`).
    # ⚠ Standart qiymat (`default=`) BERILMAYDI: `database.sync_missing_columns`
    # uni `ADD COLUMN ... DEFAULT FALSE` qilib ESKI qatorlarga ham yozardi —
    # eski brak "brak emas" bo'lib, hisobotdan yo'qolardi.
    is_brak = Column(Boolean, nullable=True)

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
    is_opening_stock = Column(Boolean, default=False)  # Boshlang'ich (mavjud) ombor — kassa balansiga TA'SIR QILMAYDI

    # Ombor Kirim hujjati (qo'shimcha xarajatlar bilan) — ixtiyoriy bog'lanish.
    # Eski (bu funksiyadan oldingi) yozuvlarda bu — NULL bo'ladi, va tizim
    # ularni avvalgidek, o'zgarishsiz ishlatishda davom etadi.
    receipt_id = Column(Integer, ForeignKey("inventory_receipts.id"), nullable=True, index=True)
    receipt = relationship("InventoryReceipt", back_populates="purchases")
    # Shu qatorga to'g'ri kelgan qo'shimcha xarajat ulushi (agar hujjatda
    # "tannarxga qo'shish" yoqilgan bo'lsa) — bir birlikka, tarix uchun saqlanadi
    extra_cost_per_unit = Column(Numeric(12, 4), default=0)

    def __repr__(self):
        return f"<InventoryPurchase {self.item_name} {self.quantity}>"


class InventoryReceipt(Base):
    """Ombor kirim HUJJATI — bir martalik kirim jarayonida kiritilgan barcha
    mahsulotlarni, va ular bilan bog'liq qo'shimcha xarajatlarni (Transport,
    Tushirish, Yuklash, Boshqa) birlashtirib turadi.

    MUHIM (SaaS uchun kengaytiriladigan): bu jadval, xomashyo xaridi bilan
    birga keladigan HAR QANDAY qo'shimcha xarajat turini qo'llab-quvvatlaydi
    — kelajakda yangi xarajat turi kerak bo'lsa, shu yerga oson qo'shiladi."""
    __tablename__ = "inventory_receipts"

    id = Column(Integer, primary_key=True, index=True)
    # 2026-09-18 — SaaS ko'p-tenantlilik, 6-to'lqin.
    # Qiymat MIJOZDAN QABUL QILINMAYDI. U har doim ota-yozuvdan olinadi —
    # models.py oxiridagi `_tenant_guard` hodisasi buni avtomatik bajaradi
    # va ota bilan mos kelmasa yozuvni RAD ETADI.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True, index=True)
    supplier = relationship("Supplier")
    document_number = Column(String(50), nullable=True)
    receipt_date = Column(DateTime, default=datetime.utcnow)

    # Qo'shimcha xarajat turlari — har biri ALOHIDA maydonda
    transport_cost = Column(Numeric(12, 2), default=0)
    tushirish_cost = Column(Numeric(12, 2), default=0)   # Grushchik
    yuklash_cost = Column(Numeric(12, 2), default=0)
    boshqa_cost = Column(Numeric(12, 2), default=0)
    # Yo'nalish (ixtiyoriy): umumiy / penoplast / gips — hisobotda
    # Transport va boshqa qo'shimcha xarajatlarni ajratib ko'rish uchun
    production_type = Column(String(20), nullable=True)

    # "☑ Qo'shimcha xarajatlarni tannarxga qo'shish" — yoqilgan bo'lsa,
    # yuqoridagi 4 ta xarajat, mahsulotlar qiymatiga proporsional taqsimlanib,
    # ombordagi birlik tannarxiga qo'shiladi. O'chirilgan bo'lsa — bu
    # xarajatlar faqat Moliyada, alohida qator sifatida ko'rinadi, tannarxga
    # ta'sir qilmaydi.
    add_to_cost = Column(Boolean, default=False)

    notes = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    purchases = relationship("InventoryPurchase", back_populates="receipt")

    def __repr__(self):
        return f"<InventoryReceipt #{self.id} ({self.document_number or '—'})>"


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

    # 2026-09-18 — W2b: bu cheklov endi KORXONA ICHIDA yagona.
    # Ilgari butun tizim bo'yicha yagona edi, ya'ni ikkinchi korxona
    # bir xil qiymatni umuman qo'sha olmasdi. Nomi bazadagi indeks
    # nomi bilan AYNAN bir xil bo'lishi shart.
    __table_args__ = (
        UniqueConstraint("company_id", "phone",
                         name="uq_employees_company_phone"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G2.
    # Bazaga saas_migration.py (W2G2) qo'shadi. Kod ANA SHUNDAN KEYIN
    # yangilanadi — har bir muhitda avval migratsiya, keyin kod.
    # server_default SHART: usiz SQLAlchemy ustunni INSERT'ga NULL qilib
    # qo'shib yuboradi va NOT NULL buziladi (G1 da shu xato chiqqan edi).
    # Vaqtinchalik; barcha yozuv nuqtalari company_id ni aniq yuboradigan
    # bo'lgach, baza DEFAULT'i bilan birga olib tashlanadi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    name = Column(String(100), nullable=False)
    position = Column(String(100), nullable=True)   # Lavozimi: "Kesuvchi", "Qoplovchi" va h.k.

    pay_type = Column(Enum(PayType), default=PayType.FIXED, nullable=False)

    fixed_amount = Column(Numeric(12, 2), default=0)      # FIXED uchun
    percent_value = Column(Float, default=0.0)             # PERCENT_SALES / PERCENT_PROFIT uchun
    per_unit_rate = Column(Numeric(12, 2), default=0)      # PER_UNIT uchun — 1 birlik narxi
    per_unit_type = Column(String(20), default="blok")     # blok / metr / dona
    # 11.2b (2026-09-20): `gul_rate` modeldan olib tashlandi.
    # DB ustuni `employees.gul_rate` ATAYLAB QOLDIRILDI (nullable) —
    # eski yozuvlar buzilmasin uchun; ORM uni endi o'qimaydi ham,
    # yozmaydi ham.
    extra_monthly = Column(Numeric(12, 2), nullable=True)   # Istalgan to'lov turiga qo'shiladigan, ixtiyoriy doimiy oylik
    production_type = Column(String(20), nullable=True)     # penoplast / gips / umumiy — Gips/Penoplast mustaqil hisobot uchun

    is_active = Column(Boolean, default=True)
    hire_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)  # "O'chirilgan" — lekin tiklash uchun saqlanadi

    # Hodimning o'z paneliga kirishi uchun (ixtiyoriy — admin belgilaydi)
    phone = Column(String(20), nullable=True)
    pin_hash = Column(String(64), nullable=True)

    advance_requests = relationship("AdvanceRequest", back_populates="employee", cascade="all, delete-orphan")
    compensation_history = relationship("EmployeeCompensationHistory", back_populates="employee",
                                         cascade="all, delete-orphan", order_by="desc(EmployeeCompensationHistory.effective_year), desc(EmployeeCompensationHistory.effective_month)")

    def __repr__(self):
        return f"<Employee {self.name} ({self.pay_type.value})>"


class EmployeeCompensationHistory(Base):
    """Hodimning to'lov parametrlari (oylik, foiz, birlik narxi va h.k.) —
    QAYSI OYDAN BOSHLAB kuchga kirganini saqlaydi (2026-09-06).

    MUHIM: Employee jadvalidagi fixed_amount/percent_value/... maydonlari —
    faqat 'HOZIRGI' qiymatni tez ko'rsatish uchun (ro'yxat, profil sahifasi).
    Oylik hisob-kitob (calculate_monthly_employee_pay) esa HECH QACHON
    to'g'ridan-to'g'ri Employee.fixed_amount'dan o'qimaydi — u har doim,
    hisoblanayotgan (year, month) uchun, shu jadvaldan MOS keladigan
    (effective_year, effective_month) <= (year, month) bo'lgan ENG SO'NGGI
    yozuvni topib, o'shandan foydalanadi. Shu sababli, oylik oshirilganda,
    O'TGAN OYLARNING hisobotlari HECH QACHON o'zgarib qolmaydi — ular doim
    o'sha paytda haqiqatda amal qilgan summa bilan hisoblanadi.

    Har bir hodim yaratilganda (yoki eski hodimlar uchun bir martalik
    backfill orqali) — kamida bitta, ishga kirgan oyidan boshlanadigan
    yozuv avtomatik yaratiladi."""
    __tablename__ = "employee_compensation_history"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)

    effective_year = Column(Integer, nullable=False)
    effective_month = Column(Integer, nullable=False)   # 1-12 — shu oydan boshlab amal qiladi

    pay_type = Column(Enum(PayType), nullable=False)
    fixed_amount = Column(Numeric(12, 2), default=0)
    percent_value = Column(Float, default=0.0)
    per_unit_rate = Column(Numeric(12, 2), default=0)
    per_unit_type = Column(String(20), default="blok")
    # 11.2b: `gul_rate` olib tashlandi, DB ustuni qoldirildi.
    extra_monthly = Column(Numeric(12, 2), nullable=True)

    reason = Column(Text, nullable=True)          # Ixtiyoriy: "1 yillik ishlagani uchun oshirildi"
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)

    employee = relationship("Employee", back_populates="compensation_history")

    def __repr__(self):
        return f"<CompHistory emp={self.employee_id} {self.effective_year}-{self.effective_month:02d}>"


class EmployeeMonthlyAdjustment(Base):
    """Hodim uchun, muayyan oy uchun QO'LDA kiritilgan kamaytirish
    (masalan — kelmagan kunlar uchun, agar seh ish to'xtagan bo'lsa).
    MUHIM: bu — avtomatik formula EMAS, faqat admin real vaziyatni bilgan
    holda kiritadigan, SAQLANADIGAN (tarix bilan) tuzatish. Bir marta
    kiritilgach, shu oy uchun HAR SAFAR hisob-kitobda (Hodimlar, Moliya,
    Hisobotlar — barchasida, chunki ular bitta manbadan o'qiydi) hisobga
    olinadi."""
    __tablename__ = "employee_monthly_adjustments"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    reduction_amount = Column(Numeric(12, 2), default=0)
    reason = Column(Text, nullable=True)
    bonus_amount = Column(Numeric(12, 2), default=0)
    bonus_reason = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee = relationship("Employee")

    def __repr__(self):
        return f"<EmployeeMonthlyAdjustment emp={self.employee_id} {self.year}-{self.month}: -{self.reduction_amount}>"


class CashTransaction(Base):
    """Kassa balansiga QO'LDA (admin tomonidan aniq belgilangan) ta'sir
    qiluvchi harakatlar — boshlang'ich balans, Usta KPI to'landi, Ehson
    to'landi. Boshqa kirim/chiqim (mijoz to'lovi, xomashyo xaridi va h.k.)
    — mavjud jadvallardan (Payment, InventoryPurchase va h.k.) to'g'ridan-
    to'g'ri hisoblanadi, bu yerga yozilmaydi."""
    __tablename__ = "cash_transactions"

    id = Column(Integer, primary_key=True, index=True)
    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G3/G4.
    # Bazaga saas_migration.py qo'shadi; kod ANA SHUNDAN KEYIN yangilanadi.
    # server_default SHART: usiz SQLAlchemy ustunni INSERT'ga NULL qilib
    # qo'shib yuboradi va NOT NULL buziladi (G1 da shu xato chiqqan edi).
    # Vaqtinchalik; keyinroq baza DEFAULT'i bilan birga olib tashlanadi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    category = Column(String(30), nullable=False)  # "boshlangich" / "usta_kpi" / "ehson"
    amount = Column(Numeric(12, 2), nullable=False)  # ijobiy=kirim, manfiy=chiqim
    notes = Column(Text, nullable=True)
    performed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CompanySetting(Base):
    """Korxona darajasidagi sozlamalar — kalit/qiymat (masalan Ehson foizi).
    Kelajakda boshqa umumiy sozlamalar ham shu yerga qo'shilishi mumkin."""
    __tablename__ = "company_settings"

    # 2026-09-18 — W2b: BIRLAMCHI KALIT endi (company_id, key).
    # Ilgari faqat `key` edi — ya'ni ikkita korxona bir xil nomli
    # sozlamaga (masalan "Ehson foizi") ega bo'la olmasdi.
    # server_default SHART: usiz SQLAlchemy ustunni INSERT'ga NULL qilib
    # qo'shib yuboradi va NOT NULL buziladi (G1 da shu xato chiqqan edi).
    company_id = Column(Integer, ForeignKey("companies.id"), primary_key=True,
                        nullable=False)
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
    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G3/G4.
    # Bazaga saas_migration.py qo'shadi; kod ANA SHUNDAN KEYIN yangilanadi.
    # server_default SHART: usiz SQLAlchemy ustunni INSERT'ga NULL qilib
    # qo'shib yuboradi va NOT NULL buziladi (G1 da shu xato chiqqan edi).
    # Vaqtinchalik; keyinroq baza DEFAULT'i bilan birga olib tashlanadi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
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
    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G3/G4.
    # Bazaga saas_migration.py qo'shadi; kod ANA SHUNDAN KEYIN yangilanadi.
    # server_default SHART: usiz SQLAlchemy ustunni INSERT'ga NULL qilib
    # qo'shib yuboradi va NOT NULL buziladi (G1 da shu xato chiqqan edi).
    # Vaqtinchalik; keyinroq baza DEFAULT'i bilan birga olib tashlanadi.
    # 2026-09-20 — MUHIM: bu ustun ATAYLAB `nullable=True`.
    # Mavjud BO'LMAGAN foydalanuvchi nomi bilan kirishga urinilganda
    # korxonani aniqlab bo'lmaydi (nom hech kimga tegishli emas). Ilgari
    # bazadagi vaqtinchalik `DEFAULT 1` uni to'ldirardi; u olib tashlangach
    # `/login` NOT NULL xatosi bilan 500 qaytara boshladi — ya'ni loginni
    # xato yozgan har bir odam server xatosini ko'rardi.
    # Bunday yozuvlar hech bir korxonaning ro'yxatida ko'rinmaydi, lekin
    # bazada saqlanadi va IP bo'yicha rate-limit ularni hisobga oladi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
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
    # 2026-09-19 — Faza 3: xatolarni korxonaga bog'lash.
    # ATAYLAB `nullable=True`: foydalanuvchi sessiyasisiz yuz bergan
    # PLATFORMA xatolari (fon vazifalari, ishga tushish, autentifikatsiyadan
    # oldingi xatolar) hech bir korxonaga tegishli emas — ular NULL bo'ladi
    # va tenant adminlariga ham ko'rinadi (ularda tenant ma'lumoti yo'q).
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    endpoint = Column(String(255), nullable=True)
    method = Column(String(10), nullable=True)
    performed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=_uzb_now)

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

    # 2026-09-18 — W2b: bu cheklov endi KORXONA ICHIDA yagona.
    # Ilgari butun tizim bo'yicha yagona edi, ya'ni ikkinchi korxona
    # bir xil qiymatni umuman qo'sha olmasdi. Nomi bazadagi indeks
    # nomi bilan AYNAN bir xil bo'lishi shart.
    __table_args__ = (
        UniqueConstraint("company_id", "category",
                         name="uq_recurring_obligations_company_category"),
    )

    id = Column(Integer, primary_key=True, index=True)
    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G3/G4.
    # Bazaga saas_migration.py qo'shadi; kod ANA SHUNDAN KEYIN yangilanadi.
    # server_default SHART: usiz SQLAlchemy ustunni INSERT'ga NULL qilib
    # qo'shib yuboradi va NOT NULL buziladi (G1 da shu xato chiqqan edi).
    # Vaqtinchalik; keyinroq baza DEFAULT'i bilan birga olib tashlanadi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    category = Column(String(30), nullable=False)  # ExpenseTransaction.category bilan bir xil bo'lishi kerak
    label = Column(String(60), nullable=False)  # "Arenda (arendator)", "Transport"
    icon = Column(String(10), default="📦")
    monthly_target = Column(Numeric(12, 2), default=0)  # Har oy qancha to'lanishi kerak
    due_day = Column(Integer, default=5)  # Oyning nechinchi kunigacha to'lanishi kerak (masalan 5 — har oy 5-sanagacha)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)  # Qo'shilgan sana — undan OLDINGI oylar uchun qarz hisoblanmasin

    def __repr__(self):
        return f"<RecurringObligation {self.label}: {self.monthly_target}/oy>"


# ============================================================
# 9c. SUPPLIER — Yetkazib beruvchilar va nasiya qarzi
# ============================================================

class Supplier(Base):
    """Yetkazib beruvchi — xomashyo sotib olinadigan tomon."""
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)

    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G1.
    # Bazaga saas_migration.py (W2G1) qo'shadi: backfill, indeks, tashqi
    # kalit va NOT NULL bilan birga. Kod ANA SHUNDAN KEYIN yangilanadi —
    # har bir muhitda avval migratsiya, keyin kod.
    # Ustunda hozircha vaqtinchalik DEFAULT 1 bor; u barcha yozuv
    # nuqtalari company_id ni aniq yuboradigan bo'lgach olib tashlanadi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
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
    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G3/G4.
    # Bazaga saas_migration.py qo'shadi; kod ANA SHUNDAN KEYIN yangilanadi.
    # server_default SHART: usiz SQLAlchemy ustunni INSERT'ga NULL qilib
    # qo'shib yuboradi va NOT NULL buziladi (G1 da shu xato chiqqan edi).
    # Vaqtinchalik; keyinroq baza DEFAULT'i bilan birga olib tashlanadi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    materials_note = Column(String(255), nullable=True)   # "Akril, Kroshka, Mel uchun"
    expense_date = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    production_type = Column(String(20), nullable=True)  # umumiy / penoplast / gips

    def __repr__(self):
        return f"<TransportExpense {self.amount}>"


# ============================================================
# 10. FINISHED PRODUCT — Tayyor mahsulotlar ombori
# ============================================================

class FinishedProduct(Base):
    """Tayyor mahsulot: ishlab chiqarilgan yoki buyurtmadan qaytgan."""
    __tablename__ = "finished_products"

    id = Column(Integer, primary_key=True, index=True)
    # 2026-09-18 — SaaS ko'p-tenantlilik, 5-to'lqin.
    # Qiymat MIJOZDAN QABUL QILINMAYDI. U har doim ota-yozuvdan olinadi —
    # models.py oxiridagi `_tenant_guard` hodisasi buni avtomatik bajaradi
    # va ota bilan mos kelmasa yozuvni RAD ETADI.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)

    name = Column(String(150), nullable=False, index=True)
    category = Column(String(50), nullable=True)     # profil / panel / dona

    width = Column(Float, nullable=True)
    thickness = Column(Float, nullable=True)
    is_coated = Column(Boolean, default=True)

    quantity = Column(Float, default=0.0)            # Qoldiq (metr yoki dona) — SOTILGANDA/BRAKDA KAMAYADI
    produced_quantity = Column(Float, nullable=True)  # ASL ishlab chiqarilgan miqdor — HECH QACHON o'zgarmaydi
    # (hodim oyligini hisoblash uchun — "Sotish" qoldiqni kamaytiradi, lekin
    # hodim ALLAQACHON shu ishni bajargan, shuning uchun uning haqi o'zgarmasligi kerak)
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
    penoplast = relationship("Inventory", foreign_keys=[penoplast_id])
    volume_m3 = Column(Float, default=0.0)          # Penoplast hajmi (darhol yechiladi)
    price_per_m3 = Column(Numeric(12, 2), nullable=True)      # Foydalanuvchi kiritgan "1 m³ narxi" — Donalik hajmini qayta hisoblash uchun SAQLANADI (aks holda yo'qolib, penoplast tan narxiga qaytib, hajm buzilardi)
    planned_loy_kg = Column(Float, default=0.0)      # Reja qilingan loy
    actual_loy_kg = Column(Float, nullable=True)     # Haqiqiy sarflangan loy ("Tayyor" bosilganda)
    gips_kg_used = Column(Float, nullable=True)       # GIPS mahsulotlar uchun — sarflangan Gips (kg)
    gips_inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=True)  # Qaysi Gips ishlatilgani
    gips_inventory = relationship("Inventory", foreign_keys=[gips_inventory_id])
    # QO'SHILDI 2026-09-20 (Bosqich 3, 10-band). Tayyor mahsulot QAYSI
    # mahsulot turidan ekanini ko'rsatadi — liniya bo'yicha moliya (12-band)
    # shu ustunga tayanadi. Hozircha faqat MRP (Production moduli) orqali
    # ishlab chiqarilganlar va buyurtma detalidan qaytganlar to'ldiriladi;
    # eski, qattiq kodlangan turkumlar (profil/panel/dona/blok/gips/
    # termopanel) uchun hali `ProductType` yozuvi YO'Q, shuning uchun ular
    # ATAYLAB NULL bo'lib qoladi — 11-band ularni ko'chirganda to'ldiriladi.
    # `OrderItem.product_type_id` bilan bir xil naqsh (models.py:734).
    product_type_id = Column(Integer, ForeignKey("product_types.id"), nullable=True, index=True)
    # QO'SHILDI 2026-09-20 — BARQAROR "1 birlik tan narxi".
    # `_fp_stable_unit_cost()` mavjud mahsulotlar uchun buni
    # `unit_volume_m3`/`unit_loy_kg` dan hisoblaydi. MRP (Ishlab chiqarish
    # moduli) esa u maydonlarni UMUMAN to'ldirmaydi — retsept ixtiyoriy
    # materiallardan iborat bo'lishi mumkin. Shuning uchun MRP ishlab
    # chiqarish yakunlanganda 1 birlik tan narxini SHU YERGA yozib qo'yadi.
    # U keyin HECH QACHON o'zgarmaydi — shu tufayli ombordan olish va
    # qaytarish simmetrik bo'ladi (qisman topshirishda ham).
    unit_cost_stable = Column(Numeric(14, 4), nullable=True)
    # MUHIM: `lazy="joined"` QO'YILMAYDI — `FinishedProduct` boshqa joyda
    # `.with_for_update()` bilan qulflanadi va LEFT OUTER JOIN Postgres'da
    # "FOR UPDATE cannot be applied to the nullable side of an outer join"
    # xatosini beradi (2026-09-18 da OrderItem'da shunday yiqilgan edi).
    product_type = relationship("ProductType")
    # GIPS qo'shimchalari (Granula, Po'lat sim, Serpiyanka va h.k.) —
    # ishlab chiqarishda tanlangan har bir qo'shimchani JSON ro'yxat
    # sifatida saqlaydi: [{"inventory_id": 12, "quantity": 10.0}, ...].
    # MUHIM: bu ustun bo'lmasa, "+" orqali miqdor qo'shilganda tizim
    # qaysi qo'shimchalar ishlatilgani va qancha nisbatda ekanini
    # BILOLMAYDI — shuning uchun avval faqat asosiy Gips yechilib,
    # qo'shimchalar ombordan umuman ayirilmay qolgan edi.
    gips_additives_json = Column(Text, nullable=True)
    # 1 BIRLIKKA (metr/dona) qancha Penoplast (m³) va loy (kg) ketishi —
    # ishlab chiqarilganda BIR MARTA hisoblab qo'yiladi va keyin
    # O'ZGARMAYDI. Qoldiq keyinchalik sotilib kamaysa (hatto 0 bo'lsa)
    # ham, "+" orqali qo'shimcha ishlab chiqarishda shu ANIQ nisbatdan
    # foydalaniladi — volume_m3/quantity kabi "joriy" nisbatga emas
    # (bu — sotuv bilan volume_m3 mos ravishda kamaymagani uchun,
    # vaqt o'tishi bilan noto'g'ri bo'lib qolar edi).
    unit_volume_m3 = Column(Float, nullable=True)
    unit_loy_kg = Column(Float, nullable=True)
    bazalt_item_id = Column(Integer, ForeignKey("inventory.id"), nullable=True)  # Termopanel "+" qo'shish uchun: qaysi bazaltdan ishlab chiqarilgan
    # Termopanel — Bazalt bilan BIRGA ishlatilgan Serpiyanka/Kley miqdori
    # (JAMI, ishlab chiqarilgan/qo'shilgan barcha marta uchun). MUHIM: bular
    # bo'lmasa, "Tayyor mahsulotdan" buyurtmaga o'tkazilganda (yoki sotilganda)
    # tan narxdan faqat Loy qismi kamayadi — Bazalt/Serpiyanka/Kley qismi esa
    # HECH QACHON kamaymay, tan narx haqiqiysidan yuqori bo'lib qolaveradi
    # (2026-08-23 zaxira tekshiruvida aniqlangan: "Bazalt panel").
    termo_bazalt_qty = Column(Float, nullable=True)
    termo_serp_id = Column(Integer, ForeignKey("inventory.id"), nullable=True)
    termo_serp_qty = Column(Float, nullable=True)
    termo_kley_id = Column(Integer, ForeignKey("inventory.id"), nullable=True)
    termo_kley_qty = Column(Float, nullable=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=True, index=True)
    recipe = relationship("Recipe")

    production_status = Column(Enum(ProductionStatus), default=ProductionStatus.IN_PROGRESS, nullable=False)
    finished_production_at = Column(DateTime, nullable=True)

    # 2026-09-17: Production/MRP'dan "Mijoz buyurtmasi asosida" ishlab
    # chiqarilgan partiya — aniq bitta buyurtma-detaliga BAND QILINADI
    # (umumiy sotuvdan ajratiladi). reserved_quantity — shu qatordagi
    # `quantity`dan qanchasi band (0 bo'lsa — butunlay erkin, umumiy
    # sotuv uchun). "Sotish mumkin miqdor" = quantity - reserved_quantity.
    # Bekor qilinsa (band ozod qilinsa), ikkalasi ham 0/NULL ga qaytariladi
    # — mahsulotning o'zi YO'QOLMAYDI, faqat yana umumiy sotuvga qaytadi.
    reserved_quantity = Column(Float, default=0.0)
    reserved_for_order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=True, index=True)

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


class FinishedProductSale(Base):
    """Tayyor mahsulotni to'g'ridan-to'g'ri sotish (buyurtma/Yuk xatisiz).
    Masalan G'isht — tan narxi 0 bo'lgani uchun, sotilgan summaning
    HAMMASI sof foyda hisoblanadi. Bu — Moliyaga alohida qator sifatida
    qo'shiladi, umumiy daromad/foydaga ta'sir qiladi."""
    __tablename__ = "finished_product_sales"

    id = Column(Integer, primary_key=True, index=True)
    # 2026-09-18 — SaaS ko'p-tenantlilik, 6-to'lqin.
    # Qiymat MIJOZDAN QABUL QILINMAYDI. U har doim ota-yozuvdan olinadi —
    # models.py oxiridagi `_tenant_guard` hodisasi buni avtomatik bajaradi
    # va ota bilan mos kelmasa yozuvni RAD ETADI.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    finished_product_id = Column(Integer, ForeignKey("finished_products.id"), nullable=True, index=True)
    product_name = Column(String(150), nullable=False)  # Nusxa — mahsulot keyin o'chsa ham tarix qolsin

    quantity = Column(Float, nullable=False)
    unit = Column(String(20), default="dona")
    unit_price = Column(Numeric(12, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)   # MOLIYA uchun — kelishilgan (chegirilgan) summaning shu qatorga to'g'ri keladigan qismi
    cost_amount = Column(Numeric(12, 2), default=0)  # Sotilgan qismning tan narxi (odatda 0)

    # ── "Kelishilgan summa" (jamlab sotishda) ──────────────────
    # Yuk xati (PDF)'da har detal O'Z ASL narxida ko'rinishi kerak ("Yo'l B").
    # Shuning uchun asl summani ALOHIDA saqlaymiz. Chegirma esa total_amount'ga
    # proporsional singdiriladi — moliya (daromad/foyda) avtomatik to'g'ri chiqadi.
    original_total = Column(Numeric(12, 2), nullable=True)   # unit_price × quantity (chegirmasiz, PDF uchun)
    group_discount_percent = Column(Float, nullable=True)    # Butun guruhga umumiy chegirma foizi (ko'rsatish uchun)

    sold_at = Column(DateTime, default=datetime.utcnow)
    buyer_name = Column(String(150), nullable=True)
    payment_method = Column(String(20), default="naqd")
    notes = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    sale_group_id = Column(String(40), nullable=True, index=True)  # Bir nechta mahsulot BITTA Yuk xati bilan sotilganda, ularni birlashtiradi
    # MUHIM (2026-09): Tayyor mahsulot bo'limidan TO'G'RIDAN-TO'G'RI (buyurtmasiz)
    # sotuv — agar ustaga (masalan o'zi kelib xarid qilgan usta) biriktirilsa,
    # shu maydon orqali belgilanadi va oylik Usta KPI hisobiga qo'shiladi
    # (aks holda faqat Buyurtma orqali sotilgandagina KPI hisoblanardi).
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=True, index=True)

    finished_product = relationship("FinishedProduct")

    def __repr__(self):
        return f"<FinishedProductSale {self.product_name} x{self.quantity} = {self.total_amount}>"


class FinishedProductLoss(Base):
    """Tayyor mahsulotdan brak/yo'qotish sababli KAMAYTIRISH (butunlay
    o'chirish EMAS — masalan 200 metrdan 50 metri sinib, endi kerak emas).
    Bu — Moliyada, xuddi xomashyo brak'i kabi, 'Brak' xarajatiga qo'shiladi."""
    __tablename__ = "finished_product_losses"

    id = Column(Integer, primary_key=True, index=True)
    # 2026-09-18 — SaaS ko'p-tenantlilik, 6-to'lqin.
    # Qiymat MIJOZDAN QABUL QILINMAYDI. U har doim ota-yozuvdan olinadi —
    # models.py oxiridagi `_tenant_guard` hodisasi buni avtomatik bajaradi
    # va ota bilan mos kelmasa yozuvni RAD ETADI.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    finished_product_id = Column(Integer, ForeignKey("finished_products.id"), nullable=True, index=True)
    product_name = Column(String(150), nullable=False)
    category = Column(String(30), nullable=True)

    quantity = Column(Float, nullable=False)
    unit = Column(String(20), default="dona")
    cost_amount = Column(Numeric(12, 2), default=0)  # Shu miqdorning tan narxi

    reason = Column(Text, nullable=True)
    lost_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)
    # kech53 (13-band, 1-qadam): brak BOSQICHI — ixtiyoriy ("Kamaytirish" va
    # ishlab chiqarish braki oynasi). `ReturnItem.brak_bosqich` bilan bir xil
    # kodlar; NULL — tanlanmagan / eski yozuv. STANDARTSIZ (sabab — yuqorida).
    brak_bosqich = Column(String(20), nullable=True)
    # kech56 (13-band, 7-qadam): brak SABABI va JAVOBGAR hodim — ixtiyoriy
    # (`ReturnItem` bilan bir xil kodlar va qoida).
    brak_sabab = Column(String(20), nullable=True)
    brak_javobgar_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"),
                              nullable=True, index=True)

    finished_product = relationship("FinishedProduct")

    def __repr__(self):
        return f"<FinishedProductLoss {self.product_name} -{self.quantity}>"


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
    # kech70 (76-band): MRP detali — shu yuk QAYSI tayyor mahsulotdan (TM) QANCHA olgani,
    # JSON `[[tm_id, miqdor], ...]`. Yuk xati o'chirilganda mahsulot AYNAN shu TM larga
    # qaytadi. Eski yozuvlarda NULL — standart qiymat ataylab BERILMAYDI (kech52 saboqi:
    # `sync_missing_columns` `default=` ni eski qatorlarga ham yozadi).
    mrp_olingan = Column(Text, nullable=True)

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
    # kech40 (22-band, foydalanuvchi qarori B): "pul qaytdi" bosilganda yoziladigan
    # MANFIY to'lov qaysi qaytarishniki — qaytarish o'chirilsa AYNAN shu to'lov
    # o'chiriladi (izoh matni bo'yicha qidirish — taxmin). Qaytarish yozuvi
    # o'chsa — NULL (PostgreSQL `ON DELETE SET NULL`; kod baribir to'lovni oldin
    # o'chiradi).
    return_item_id = Column(Integer, ForeignKey("return_items.id", ondelete="SET NULL"),
                            nullable=True, index=True)

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

# kech87 (104-band): kirim hujjatidagi qo'shimcha xarajat (transport / tushirish / yuklash / boshqa) "tannarxga
# qo'shish" bilan yozilganda `ExpenseTransaction.source` shu qiymatni oladi. Bunday xarajat xomashyo tannarxida
# (o'rtacha narxda) hisoblanadi va xomashyo ishlatilganda "ishlab chiqarish xarajati" orqali foydadan ayriladi —
# shuning uchun oylik sof foydadan ALOHIDA ayrilmaydi (ilgari ikki marta ayrilardi — O'LCHANGAN, probe104 K4/K5).
# Ustun `String(20)` — qiymat 13 belgi.
KIRIM_TANNARX_MANBA = "kirim_tannarx"

# kech88 (105-band): kirim hujjatining TANNARXGA QO'SHILMAGAN qo'shimcha xarajati (`crud.create_inventory_receipt`
# shu qiymatni yozadi — 2026-07 dan beri). Bunday yozuv oylik hisobotda "qo'shimcha xarajat" sifatida sof foydadan
# ayriladi; "Naqd xarajatlar" ko'rsatkichi ikkala manbani (shu va `KIRIM_TANNARX_MANBA`) chiqib ketgan pul deb sanaydi.
KIRIM_XARAJAT_MANBA = "inventory_receipt"


class ExpenseTransaction(Base):
    """Har bir xarajatni ALOHIDA tranzaksiya sifatida saqlaydi (SaaS arxitekturasi uchun).

    MUHIM: bu jadval MonthlyExpense'ni ALMASHTIRMAYDI — ikkalasi parallel ishlaydi.
    Oylik hisobot (get_monthly_report) avval shu jadvaldan tranzaksiyalarni qidiradi;
    agar topilmasa (eski oylar), MonthlyExpense'dan o'qishda davom etadi — to'liq
    orqaga moslik saqlanadi.
    """
    __tablename__ = "expense_transactions"

    id = Column(Integer, primary_key=True, index=True)
    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G3/G4.
    # Bazaga saas_migration.py qo'shadi; kod ANA SHUNDAN KEYIN yangilanadi.
    # server_default SHART: usiz SQLAlchemy ustunni INSERT'ga NULL qilib
    # qo'shib yuboradi va NOT NULL buziladi (G1 da shu xato chiqqan edi).
    # Vaqtinchalik; keyinroq baza DEFAULT'i bilan birga olib tashlanadi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
    date = Column(DateTime, nullable=False, default=datetime.utcnow)
    category = Column(String(30), nullable=False)  # arenda / elektr / tushlik / soliqlar / boshqa
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    notes = Column(Text, nullable=True)

    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 'monthly_form' — Moliya sahifasidagi oylik forma orqali avtomatik yaratilgan
    # 'manual'       — kelajakda alohida "xarajat qo'shish" orqali qo'lda kiritilgan
    source = Column(String(20), default="manual")
    # Yo'nalish bo'yicha ajratish (ixtiyoriy): umumiy / penoplast / gips
    production_type = Column(String(20), nullable=True)

    def __repr__(self):
        return f"<ExpenseTransaction {self.category}: {self.amount}>"


class MonthlyExpense(Base):
    """Oylik xarajatlar: arenda, elektr, tushlik, hodim oyliqlari."""
    __tablename__ = "monthly_expenses"

    id         = Column(Integer, primary_key=True, index=True)
    # 2026-09-18 — SaaS ko'p-tenantlilik, 2-to'lqin G3/G4.
    # Bazaga saas_migration.py qo'shadi; kod ANA SHUNDAN KEYIN yangilanadi.
    # server_default SHART: usiz SQLAlchemy ustunni INSERT'ga NULL qilib
    # qo'shib yuboradi va NOT NULL buziladi (G1 da shu xato chiqqan edi).
    # Vaqtinchalik; keyinroq baza DEFAULT'i bilan birga olib tashlanadi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False,
                        index=True)
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


# ============================================================
# TENANT HIMOYASI — company_id ni ota-yozuvdan olish va tekshirish
# ============================================================
# 2026-09-18. Nima uchun markazlashtirilgan:
#   Bu jadvallar kodning 16 xil joyida yaratiladi. Har bir joyga qo'lda
#   `company_id=...` yozish — bittasi unutilishi bilan buziladigan yechim.
#   Bu yerdagi hodisa esa HAR BIR yozuvda, qayerda yaratilganidan qat'i
#   nazar ishlaydi.
#
# Uch qoida:
#   1. company_id MIJOZDAN QABUL QILINMAYDI — u ota-yozuvdan olinadi.
#   2. Agar yozuvda company_id allaqachon qo'yilgan bo'lsa-yu, otasiniki
#      BOSHQA bo'lsa — yozuv RAD ETILADI (korxonalar aralashib ketmasin).
#   3. Ota topilmasa — hech narsa taxmin qilinmaydi, qiymat o'zgarishsiz
#      qoldiriladi. Bunday qatorlar migratsiya sahifasidagi TEKSHIRUV
#      bo'limida "otasi aniqlanmagan" bo'lib alohida ko'rinadi.
#
# Har bir jadval uchun ota zanjiri (birinchi topilgani ishlatiladi):

_TENANT_RULES = {
    # Buyurtma o'z loyihasidan
    "Order":               [("project_id", "Project")],
    # Detal o'z buyurtmasidan (order_id NOT NULL — har doim topiladi)
    "OrderItem":           [("order_id", "Order")],
    # Tayyor mahsulot: buyurtmadan; bo'lmasa retseptdan; bo'lmasa penoplastdan.
    # (MRP orqali omborga ishlab chiqarilganda buyurtma bo'lmaydi.)
    "FinishedProduct":     [("from_order_id", "Order"),
                            ("recipe_id", "Recipe"),
                            ("penoplast_id", "Inventory")],
    # Qaytarish: buyurtmadan; bo'lmasa qaytarilgan tayyor mahsulotdan
    "ReturnItem":          [("order_id", "Order"),
                            ("finished_product_id", "FinishedProduct")],
    # Ombor harakati: materialdan; bo'lmasa buyurtmadan; bo'lmasa ta'minotchidan
    "InventoryMovement":   [("inventory_id", "Inventory"),
                            ("order_id", "Order"),
                            ("supplier_id", "Supplier")],
    # Ombor kirimi: ta'minotchidan
    "InventoryReceipt":    [("supplier_id", "Supplier")],
    # Sotuv: sotilgan tayyor mahsulotdan; bo'lmasa ustadan
    "FinishedProductSale": [("finished_product_id", "FinishedProduct"),
                            ("master_id", "Master")],
    # Yo'qotish/brak: tayyor mahsulotdan
    "FinishedProductLoss": [("finished_product_id", "FinishedProduct")],

    # --- M2 (2026-09-18) ---
    # Bu modellarda company_id ustuni YO'Q — ular ota orqali tenant oladi.
    # Qoidalar shu yerda, chunki tenant mosligini tekshirish uchun otani
    # bilish kifoya (company_id ustuni bo'lishi shart emas).
    "Payment":             [("order_id", "Order")],
    "Delivery":            [("order_id", "Order")],
    "DeliveryItem":        [("delivery_id", "Delivery")],
    "OrderAttachment":     [("order_id", "Order")],
    "OrderItemSubDetail":  [("order_item_id", "OrderItem")],
    "OrderGipsAdditive":   [("order_id", "Order")],

    # --- M3 (2026-09-18) ---
    # Bularda ham company_id ustuni yo'q — tenant otadan olinadi.
    # InventoryPurchase uchun BIRINCHI ota (material) tenant'ni beradi,
    # keyin _TENANT_REFS ta'minotchini ham SHU tenant'ga tekshiradi —
    # ya'ni A materiali + B ta'minotchisi juftligi rad etiladi.
    "InventoryPurchase":   [("inventory_id", "Inventory"),
                            ("supplier_id", "Supplier")],
    "SupplierPayment":     [("supplier_id", "Supplier")],
    # 2026-09-21 (12-sizish) — O'LCHANGAN: `_TENANT_REFS` da
    # `RecipeIngredient.inventory_id` qoidasi BOR edi, lekin HECH QACHON
    # ishlamasdi: bu jadvalda o'z `company_id` si yo'q, bu yerda ota ham
    # yo'q edi → `_check_refs` ga own_cid=None borardi va u darhol
    # qaytardi. Natija: B retsepti A materialiga bog'lanardi, B loy
    # ishlab chiqarganda A ombori kamayardi. Endi korxona retseptdan olinadi.
    "RecipeIngredient":    [("recipe_id", "Recipe")],

    # --- M5 (2026-09-18) — ustalar / hodimlar / sovg'a ---
    # Bu modellarda ham company_id ustuni YO'Q; tenant otadan olinadi.
    # Auditda aniqlangan holat: bu zanjirlarning HECH BIRI qoidalarda
    # yo'q edi, ya'ni A korxonaning sovg'a davriga B korxonaning
    # ustasini ishtirokchi qilib yozib qo'yish mumkin edi.
    "GiftPeriodTier":              [("period_id", "GiftPeriod")],
    "GiftPeriodTier": [("period_id", "GiftPeriod")],
    "GiftPeriodParticipant":       [("period_id", "GiftPeriod")],
    "MasterGiftPeriodRedemption":  [("period_id", "GiftPeriod")],
    "MasterGiftRedemption":        [("master_id", "Master")],
    "EmployeeAdvance":             [("employee_id", "Employee")],
    "EmployeeCompensationHistory": [("employee_id", "Employee")],
    "EmployeeMonthlyAdjustment":   [("employee_id", "Employee")],
    "AdvanceRequest":              [("employee_id", "Employee")],
    "EmployeeSession":             [("employee_id", "Employee")],
}


# ============================================================
# HAVOLALAR (references) — ota emas, lekin BIR KORXONADA bo'lishi shart
# ============================================================
# 2026-09-18 — M2. Yuqoridagi _TENANT_RULES "bu yozuv qaysi korxonaniki?"
# degan savolga javob beradi. Bu yerdagi qoidalar esa boshqa savolga:
# "bu yozuv KO'RSATAYOTGAN boshqa yozuv ham SHU korxonanikimi?"
#
# Masalan buyurtma detali A korxonaniki, lekin uning `penoplast_id` si
# B korxonaning materialiga ishora qilishi mumkin edi. Baza buni to'smaydi
# (oddiy FK faqat "shunday id bormi" deb tekshiradi), tenant qoidasi ham
# to'smasdi — chunki detalning o'z otasi (buyurtma) to'g'ri edi.
#
# Endi har bir havola tekshiriladi: ko'rsatilayotgan yozuvning company_id si
# yozuvnikidan farq qilsa — RAD ETILADI.

_TENANT_REFS = {
    # Buyurtma detali qaysi material/retsept/tayyor mahsulotga ishora qiladi
    "OrderItem": [
        ("penoplast_id", "Inventory"),
        ("recipe_id", "Recipe"),
        ("finished_product_id", "FinishedProduct"),
        # 2026-09-20: bu bog'lam bor edi, lekin qo'riqchida yo'q edi —
        # `ProductType` ni topib bo'lmagani uchun. Endi topiladi.
        ("product_type_id", "ProductType"),
    ],
    # Retsept tarkibidagi xomashyo
    "RecipeIngredient": [("inventory_id", "Inventory")],
    # Qaytarish — qaysi tayyor mahsulotga
    "ReturnItem": [("finished_product_id", "FinishedProduct"),
                   # kech39: qaytarish qaysi buyurtma detalidan (3-band)
                   ("order_item_id", "OrderItem"),
                   # kech56 (13-band, 7-qadam): brakka sabab bo'lgan javobgar hodim
                   ("brak_javobgar_id", "Employee")],
    # kech40 (22-band): pul qaytarish to'lovi — qaysi qaytarishniki (begona
    # korxona qaytarishiga bog'langan to'lov yozishdayoq rad etiladi)
    "Payment": [("return_item_id", "ReturnItem")],
    # Yetkazish qatori — qaysi detalga
    "DeliveryItem": [("order_item_id", "OrderItem")],
    # Ombor harakati — qaysi material/buyurtma/ta'minotchiga
    "InventoryMovement": [("inventory_id", "Inventory"), ("order_id", "Order"),
                          ("supplier_id", "Supplier"),
                          # kech45 (13-band): qaysi brak yozuvi yaratgan
                          ("return_item_id", "ReturnItem")],

    # --- M3 (2026-09-18) ---
    # Ishlab chiqarish retsepti (BOM) qatori qaysi materialga ishora qiladi.
    # Bu M3 dagi eng muhim FK teshigi edi: A korxonaning BOM'i B korxonaning
    # materialini ko'rsatib, ishlab chiqarishda O'SHA omborni kamaytirardi.
    "BOMItem": [("inventory_id", "Inventory")],
    # Xarid — qaysi material va qaysi ta'minotchidan
    "InventoryPurchase": [("inventory_id", "Inventory"), ("supplier_id", "Supplier")],
    # Ombor kirimi — qaysi ta'minotchidan
    "InventoryReceipt": [("supplier_id", "Supplier")],
    # Ta'minotchiga to'lov
    "SupplierPayment": [("supplier_id", "Supplier")],
    # Tayyor mahsulot — qaysi buyurtma/retsept/materialga
    "FinishedProduct": [("from_order_id", "Order"), ("recipe_id", "Recipe"),
                        ("penoplast_id", "Inventory"),
                        ("gips_inventory_id", "Inventory"),
                        # Bosqich 3, 10-band (2026-09-20) — yangi bog'lam.
                        # `ProductType` production_models.py da, qo'riqchi
                        # uni kech import orqali topadi (_check_refs).
                        ("product_type_id", "ProductType")],
    # Sotuv/brak — qaysi mahsulot/ustaga
    "FinishedProductSale": [("finished_product_id", "FinishedProduct"),
                            ("master_id", "Master")],
    "FinishedProductLoss": [("finished_product_id", "FinishedProduct"),
                            # kech56 (13-band, 7-qadam): javobgar hodim
                            ("brak_javobgar_id", "Employee")],
    # Buyurtma — qaysi loyiha va ustaga
    "Order": [("project_id", "Project"), ("master_id", "Master"),
              # kech58 (K58-1): qoplama retsepti — faqat o'z korxonasiniki
              ("qoplama_retsept_id", "Recipe")],

    # --- M5 (2026-09-18) — ustalar / hodimlar / sovg'a ---
    # Ota "bu yozuv kimniki" degan savolga javob beradi; bu yerdagi
    # qoidalar esa "ko'rsatilayotgan boshqa yozuv ham shu korxonanikimi"
    # degan savolga. Sovg'a davri ishtirokchisi va sovg'ani olish
    # yozuvida AYNAN shu teshik bor edi: davr A niki, usta esa B niki.
    "GiftPeriodTier":              [("period_id", "GiftPeriod")],
    "GiftPeriodParticipant":       [("period_id", "GiftPeriod"),
                                    ("master_id", "Master")],
    "MasterGiftPeriodRedemption":  [("period_id", "GiftPeriod"),
                                    ("master_id", "Master"),
                                    ("tier_id", "GiftPeriodTier")],
    "MasterGiftRedemption":        [("master_id", "Master"),
                                    ("gift_id", "MasterGift")],
    "EmployeeAdvance":             [("employee_id", "Employee")],
    "EmployeeCompensationHistory": [("employee_id", "Employee")],
    "EmployeeMonthlyAdjustment":   [("employee_id", "Employee")],
    "AdvanceRequest":              [("employee_id", "Employee")],
    "EmployeeSession":             [("employee_id", "Employee")],
}


class TenantMismatchError(Exception):
    """Yozuvning company_id si ota-yozuvnikiga mos kelmadi."""


# 2026-09-21 — O'LCHANGAN: `TENANT_FILTER=1` da himoya KO'R edi. Ota/havola
# yozuvi `session.get()` bilan o'qiladi va bu o'qishning o'zi joriy korxona
# filtridan o'tardi — BEGONA yozuv "mavjud emas" (None) bo'lib ko'rinardi,
# `if ... is None: continue` esa uni jimgina o'tkazib yuborardi. Natija: filtr
# o'chiq bo'lsa 409 bilan rad etiladigan bog'lanish (B ning buyurtma detaliga
# A ning `penoplast_id` si) filtr yoniq bo'lganda BAZAGA YOZILARDI.
# Himoyaning butun vazifasi — aynan begona yozuvni ko'rish, shuning uchun
# bu ichki o'qish filtrsiz bajariladi. Hech narsa foydalanuvchiga
# qaytarilmaydi — faqat `company_id` taqqoslanadi.
_GUARD_READ_OPTS = {"skip_tenant_filter": True}


def _resolve_parent_company(session, obj, rules):
    """Ota zanjiri bo'yicha birinchi topilgan company_id ni qaytaradi."""
    _mapped = {c.key for c in type(obj).__table__.columns}
    for fk_attr, parent_name in rules:
        if fk_attr not in _mapped:
            continue
        fk_value = getattr(obj, fk_attr, None)
        if not fk_value:
            continue
        parent_cls = globals().get(parent_name)
        if parent_cls is None:
            continue
        parent = session.get(parent_cls, fk_value,
                             execution_options=_GUARD_READ_OPTS)
        if parent is None:
            continue
        cid = getattr(parent, "company_id", None)
        if cid:
            return cid, f"{fk_attr} -> {parent_name}"
    return None, None


def _check_refs(session, obj, own_cid):
    """Yozuv KO'RSATAYOTGAN boshqa yozuvlar ham shu korxonanikimi.

    2026-09-18 — M2. own_cid — yozuvning o'z korxonasi (ota orqali yoki
    aniq berilgan). Havola boshqa korxonaga ishora qilsa, rad etiladi."""
    refs = _TENANT_REFS.get(type(obj).__name__)
    if not refs or not own_cid:
        return
    _mapped = {c.key for c in type(obj).__table__.columns}
    for fk_attr, ref_name in refs:
        if fk_attr not in _mapped:
            continue
        fk_value = getattr(obj, fk_attr, None)
        if not fk_value:
            continue
        ref_cls = globals().get(ref_name)
        if ref_cls is None:
            # QO'SHILDI 2026-09-20. Ba'zi modellar `production_models.py` da
            # yashaydi va models.py ularni ATAYLAB import qilmaydi (aylanma
            # import). Ular uchun kech (lazy) import — faqat haqiqatan
            # kerak bo'lganda, funksiya ichida.
            try:
                import production_models as _pm
                ref_cls = getattr(_pm, ref_name, None)
            except Exception:
                ref_cls = None
        if ref_cls is None:
            continue
        ref = session.get(ref_cls, fk_value,
                          execution_options=_GUARD_READ_OPTS)
        if ref is None:
            continue
        ref_cid = getattr(ref, "company_id", None)
        if ref_cid and ref_cid != own_cid:
            raise TenantMismatchError(
                f"{type(obj).__name__}.{fk_attr}={fk_value} boshqa korxonaga "
                f"({ref_cid}) tegishli, yozuvning o'zi esa {own_cid} ga. "
                f"Korxonalar orasida bog'lanish yaratib bo'lmaydi."
            )


@event.listens_for(SASession, "before_flush")
def _tenant_guard(session, flush_context, instances):
    """company_id ni ota-yozuvdan qo'yadi va mos kelishini tekshiradi.

    NIMA UCHUN `before_flush`, `before_insert` EMAS:
      `before_insert` mapper darajasidagi hodisa bo'lib, uning ichida
      so'rov yuborish (ota-yozuvni qidirish) rasman qo'llab-quvvatlanmaydi
      va flush holatini buzishi mumkin. `before_flush` esa aynan shu ish
      uchun mo'ljallangan — sessiya hali barqaror holatda, so'rov yuborish
      xavfsiz. `no_autoflush` esa qidiruvning yana flush chaqirib, cheksiz
      aylanishga tushishini oldini oladi.

    YANGI va O'ZGARTIRILGAN yozuvlarni ham tekshiradi: ota-FK keyinchalik
    BOSHQA korxonaning yozuviga ko'chirilishi ham rad etiladi.

    ⚠️ BU YAGONA HIMOYA EMAS. Quyidagilarni QAMRAB OLMAYDI:
      * `query.update()` / `query.delete()` — ORM bularda hodisa chaqirmaydi
      * `bulk_save_objects`, `bulk_insert_mappings`
      * Core `insert()`/`update()` va xom SQL
    Shuning uchun bazadagi tashqi kalitlar (FK) va xizmat qatlamidagi
    tekshiruvlar SAQLANADI — bu hodisa ularning o'rnini bosmaydi, ustiga
    qo'shimcha qatlam bo'lib turadi.
    """
    if not (session.new or session.dirty):
        return
    with session.no_autoflush:
        # --- YANGI yozuvlar ---
        for obj in session.new:
            nom = type(obj).__name__
            rules = _TENANT_RULES.get(nom)
            own = getattr(obj, "company_id", None)
            if rules:
                parent_cid, manba = _resolve_parent_company(session, obj, rules)
                if parent_cid is not None:
                    if own is None:
                        # Modelda company_id ustuni bo'lsa — to'ldiramiz.
                        if hasattr(obj, "company_id"):
                            obj.company_id = parent_cid
                        own = parent_cid
                    elif own != parent_cid:
                        raise TenantMismatchError(
                            f"{nom}: company_id={own} berilgan, lekin ota-yozuv "
                            f"({manba}) company_id={parent_cid} ga tegishli. "
                            f"Bir korxonaning yozuvini boshqasiga bog'lab bo'lmaydi."
                        )
            _check_refs(session, obj, own)

        # --- O'ZGARTIRILGAN yozuvlar ---
        # Mavjud yozuvning ota-FK'si yoki company_id si o'zgartirilsa,
        # ular baribir bir-biriga mos bo'lishi shart.
        for obj in session.dirty:
            rules = _TENANT_RULES.get(type(obj).__name__)
            if (not rules and type(obj).__name__ not in _TENANT_REFS):
                continue
            if not session.is_modified(obj, include_collections=False):
                continue
            rules = rules or []
            kuzatiladi = ([r[0] for r in rules] + ["company_id"] +
                          [r[0] for r in _TENANT_REFS.get(type(obj).__name__, [])])
            # Faqat HAQIQATDA mavjud (mapped) maydonlar — aks holda
            # get_history KeyError beradi.
            _mapped = {c.key for c in type(obj).__table__.columns}
            ozgargan = {a for a in kuzatiladi
                        if a in _mapped and get_history(obj, a).has_changes()}
            if not ozgargan:
                continue
            parent_cid, manba = _resolve_parent_company(session, obj, rules)
            own = getattr(obj, "company_id", None)
            if parent_cid is not None:
                if own is not None and own != parent_cid:
                    raise TenantMismatchError(
                        f"{type(obj).__name__} (id={getattr(obj, 'id', '?')}): "
                        f"o'zgartirilgan yozuvning company_id={own}, lekin yangi "
                        f"ota-yozuv ({manba}) company_id={parent_cid} ga tegishli. "
                        f"O'zgarish rad etildi."
                    )
                own = own or parent_cid
            _check_refs(session, obj, own)
