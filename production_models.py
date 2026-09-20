"""
PenoDecorPro ERP — Dinamik Ishlab chiqarish (Production/MRP) modullari
========================================================================
2026-09-16: yangi arxitektura — hozirgi TUR'larga (Profil/Panel/Donali/
Blok/Termopanel/Loy/Gips) qattiq yozilgan (hardcoded) hisoblash mantig'i
o'rniga, korxonaning O'ZI interfeys orqali istalgan yangi mahsulot turi
va uning retseptini (BOM — Bill of Materials) yarata oladigan tizim.

ADR (Architecture Decision Record) — asosiy qarorlar:
  1. BOM = mahsulot turi (ProductType) + versiya (masalan "Yozgi/Qishki")
  2. Har bir BOM tarkibi (BOMItem) — xomashyo, isrof foizi, ixtiyoriylik
     (is_optional — masalan "Qoplama"), va tannarxga qo'shimcha xarajat.
  3. Ishlab chiqarish 2 bosqichli: DRAFT -> IN_PROGRESS -> COMPLETED.
     IN_PROGRESS'ga o'tishda retsept "suratga olinadi" (snapshot) — shu
     paytdagi narx/miqdorlar QOTIB QOLADI, keyinchalik BOM yoki narx
     o'zgarsa ham, bu buyurtmaning tannarxi ORQAGA QARAB o'zgarmaydi.
  4. Xomashyo COMPLETED bosqichida ayiriladi, tayyor mahsulot COMPLETED
     bosqichida qo'shiladi (hozirgi bir-bosqichli tizimdan farqli).
  5. SaaS-tayyorlik: barcha jadvallarda company_id bor. Hozircha
     tizimning boshqa qismi ko'p-tenant emas, shuning uchun bitta
     "Company" yozuvi (id=1) hamma joyda ishlatiladi — bu, to'liq SaaS
     migratsiyasi boshlanganda, faqat shu YANGI modullarni emas, BUTUN
     tizimni qayta yozishni talab qilmasligi uchun ataylab shunday.

2026-09-16 (davomi) — foydalanuvchi tomonidan berilgan "7 ta Guardrails"
arxitektura talabiga qarshi tekshirilib, quyidagilar QO'SHILDI:
  6. Birlik konversiyasi (Inventory.base_unit / conversion_factor) —
     BOMItem.quantity endi materialning base_unit'i (masalan gramm)
     bo'yicha kiritiladi, ombordan esa HAR DOIM Inventory.unit (masalan
     qop) birligida ayiriladi — konversiya production_service.py'da.
  7. BOMItem.company_id qo'shildi (ilgari faqat ota-BOM orqali bilvosita
     tenant-scoped edi).
Allaqachon MAVJUD bo'lgan (o'zgarishsiz qoldirilgan) talablar: snapshot
immutability (bandi 3), input_template/pricing_formula ajratilgani
(pastdagi enumlarga qarang), is_optional komponentlar, va soft/hard
stock validatsiya (allow_negative_stock, Company klassiga qarang) —
bularning barchasi ASL arxitekturada allaqachon to'g'ri edi.

MUHIM, OCHIQ QOLGAN ARXITEKTURA NUQTASI (buni albatta o'qing):
  "IN_PROGRESS = RESERVED" degani — ombordagi xomashyo boshqa birov
  tomonidan "band qilingan" deb hisoblanishi kerak, degan ma'noni
  anglatadi. LEKIN quyidagi modellar buni FAQAT tekshiruv (validation)
  darajasida amalga oshiradi — Inventory jadvalida alohida
  "reserved_quantity" ustuni YO'Q. Amalda bu shuni bildiradi: agar
  IKKITA ishlab chiqarish buyurtmasi BIR VAQTDA (ikkalasi ham DRAFT'dan
  IN_PROGRESS'ga o'tayotganda) bir xil, chegaralangan xomashyoga
  da'vogarlik qilsa — ikkalasi ham "yetarli" deb hisoblanishi mumkin,
  chunki birinchisi hali FIZIK ravishda hech narsani ayirmagan. Bitta
  xodim ishlaydigan tizimda bu deyarli hech qachon muammo bo'lmaydi,
  lekin bir nechta xodim BIR VAQTDA ishlab chiqarishni boshlaydigan
  bo'lsa — Inventory'ga "reserved_quantity" ustuni qo'shish kerak
  bo'ladi (bu — alohida, kelajakdagi qaror, hozircha qo'shilmagan).
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime,
    ForeignKey, Numeric,
)
from sqlalchemy.orm import relationship

from models import Base   # Bitta metadata ostida — Alembic/create_all uchun MUHIM


# ============================================================
# ENUMLAR
# ============================================================

class InputTemplate(PyEnum):
    """Buyurtma/ishlab chiqarish oynasida QAYSI kiritish maydonlari
    chiqishini belgilaydi. Bular — TAYYOR naqshlar (frontendni to'liq
    dinamik form-builder qilib murakkablashtirmaslik uchun ataylab
    cheklangan to'plam — ADR: "1-variant, tayyor naqshlar")."""
    QUANTITY_ONLY = "quantity_only"      # Donali, qop/quti hisobidagi mahsulotlar
    DIMENSIONAL_3D = "dimensional_3d"    # Bo'yi x Qalinlik x Uzunlik (Profil, Nalichnik)
    AREA_2D = "area_2d"                  # Bo'yi x Eni -> m² (Termopanel, Plita)
    WEIGHT_VOLUME = "weight_volume"      # Kg yoki litrda o'lchanadigan suyuq/quruq
    FLEXIBLE_UNIT = "flexible_unit"      # Miqdor + foydalanuvchi o'zi birlik tanlaydi (hozirgi Gips kabi)


class PricingFormula(PyEnum):
    """Sotuv narxi QANDAY hisoblanishini belgilaydi. input_template'dan
    ATAYLAB alohida — chunki masalan "Blok" o'lchamli (DIMENSIONAL_3D)
    bo'lsa-da, narxi hajmga bog'liq emas, balki QAT'IY (FIXED_PRICE)."""
    VOLUME_BASED = "volume_based"   # narx = hajm (m³) x 1m³ narxi
    AREA_BASED = "area_based"       # narx = maydon (m²) x 1m² narxi
    FIXED_PRICE = "fixed_price"     # narx = miqdor x qat'iy belgilangan narx (o'lchamdan qat'i nazar)
    UNIT_BASED = "unit_based"       # narx = miqdor x 1 birlik (dona/kg/litr) narxi


class BOMComponentType(PyEnum):
    """Retsept tarkibidagi bitta qatorning turi — 2026-09-15 suhbatda
    kelishilgan farq: xomashyo (mahsulotning "tarkibi") va qadoqlash
    (idish, naklayka — mahsulotning "tarkibi" emas, lekin har bir
    tayyor donaga sarflanadi) ikkalasi bitta BOM ichida, shu maydon
    bilan ajratiladi."""
    RAW_MATERIAL = "raw_material"
    PACKAGING = "packaging"


class ProductionOrderStatus(PyEnum):
    """2 bosqichli MRP oqimi (ADR bandi 5)."""
    DRAFT = "draft"              # Hali hech narsa tekshirilmagan/band qilinmagan
    IN_PROGRESS = "in_progress"  # Retsept suratga olingan, ombor TEKSHIRILGAN (lekin hali ayirilmagan)
    COMPLETED = "completed"      # Xomashyo ayirilgan, tayyor mahsulot qo'shilgan
    CANCELLED = "cancelled"      # Bekor qilingan (DRAFT yoki IN_PROGRESS holatidan)


class ProductionSourceType(PyEnum):
    """Ishlab chiqarish QAYERDAN kelib chiqqani — mijoz buyurtmasi
    asosidami, yoki to'g'ridan-to'g'ri omborga ishlab chiqarishmi
    (ADR bandi 10 — ikkalasi ham bir xil ProductionOrder orqali)."""
    CUSTOMER_ORDER = "customer_order"
    WAREHOUSE_STOCK = "warehouse_stock"


# ============================================================
# COMPANY — SaaS-tayyorlik uchun minimal jadval
# ============================================================

class Company(Base):
    """2026-09-16: hozircha tizimning QOLGAN qismi (Order, Project,
    Inventory va h.k.) hali company_id'ga ega emas — bu YANGI Production
    modullari uchun ataylab, oldindan tayyorlab qo'yilgan minimal jadval.
    To'liq SaaS migratsiyasi boshlanganda, boshqa jadvallarga ham
    company_id qo'shilib, shu Company jadvaliga bog'lanadi.

    Hozircha — bitta korxona uchun BITTA yozuv (id=1) yetarli, va
    allow_negative_stock shu yagona yozuvda sozlanadi."""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)

    # 2026-09-18 — M1: KORXONA KODI.
    # Xodim paneliga kirishda (telefon+PIN) korxona kontekstini aniqlash
    # uchun kerak. W2b dan keyin `employees.phone` cheklovi (company_id, phone)
    # ga o'tdi — ya'ni ikki korxonada bir xil telefon bo'lishi MUMKIN.
    # Faqat telefon bo'yicha qidirish noto'g'ri korxonaning xodimini
    # tanlab qo'yishi mumkin edi. Endi kod + telefon + PIN.
    # Kod mijozdan keladi, LEKIN unga ishonilmaydi: server uni companies
    # jadvalidan qidiradi, topilmasa kirishga yo'l qo'yilmaydi.
    code = Column(String(30), unique=True, index=True, nullable=True)

    # ADR bandi 2: "Stock Validation — Company Level". False (qat'iy
    # taqiqlash) — xavfsizroq standart qiymat sifatida ataylab tanlandi;
    # korxona xohlasa, buni yumshoq ogohlantirishga o'zgartira oladi.
    allow_negative_stock = Column(Boolean, default=False, nullable=False)

    # 2026-09-20 — KORXONA BRENDI (Faza 5).
    # Ilgari yuk xati, nakladnoy va moliya hisobotlarida "PenoDecorPro ·
    # Fasad bezaklari · Andijon · +998 97 999 57 57" QATTIQ yozilgan edi —
    # ya'ni ikkinchi mijozning hujjatida boshqa korxonaning nomi va
    # TELEFON RAQAMI chiqardi. Mijozi qo'ng'iroq qilsa, boshqa odamga
    # tushardi. Endi bularning hammasi shu yerdan olinadi.
    # Bo'sh qoldirilsa — eski qiymatlar ishlatiladi, ya'ni mavjud
    # korxonada hech narsa o'zgarmaydi.
    slogan = Column(String(150), nullable=True)      # "Fasad bezaklari"
    phone = Column(String(60), nullable=True)        # "+998 97 999 57 57"
    address = Column(String(200), nullable=True)     # "Andijon"
    logo_path = Column(String(255), nullable=True)   # "static/logos/company_1.png"

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Company {self.name}>"


# ============================================================
# PRODUCT TYPE — korxona o'zi qo'shadigan "mahsulot turi"
# ============================================================

class ProductType(Base):
    """Hozirgi OrderType/TUR tugmalarining (Profil/Panel/.../Gips)
    o'rnini bosadigan, DINAMIK, bazadan boshqariladigan mahsulot turi.
    Har bir yangi mahsulot (Travertin, Kafel kley, Gruntofka...) —
    kodga tegmasdan, shu jadvalga bitta yozuv qo'shish orqali paydo
    bo'ladi."""
    __tablename__ = "product_types"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    name = Column(String(150), nullable=False)          # "Travertin", "Kafel kley"...
    unit = Column(String(20), nullable=False)             # Ko'rsatish uchun: "dona", "m²", "kg", "litr"

    input_template = Column(String(30), nullable=False)   # InputTemplate enum qiymati
    pricing_formula = Column(String(30), nullable=False)  # PricingFormula enum qiymati

    # Faqat pricing_formula == FIXED_PRICE bo'lganda ishlatiladi
    # (masalan hozirgi "Blok" kabi — o'lchamdan qat'i nazar bitta narx)
    fixed_unit_price = Column(Numeric(12, 2), nullable=True)

    # QO'SHILDI 2026-09-20 (Bosqich 3, 11.0-band) — QOPLAMA.
    # Eski qattiq kodlangan turkumlarda (profil/panel) qoplama narxni
    # HAR DOIM 2 baravar oshirardi. Korxonalarda esa bu koeffitsiyent
    # har xil — kimdir 2, kimdir 2.5. Shuning uchun u endi mahsulot
    # TURINING sozlamasi: korxona turni yaratayotganda o'zi yozadi.
    #
    # MUHIM: bu faqat SOTUV NARXIGA tegishli. Qoplamaning XOMASHYOSI
    # (loy va h.k.) butunlay boshqa joyda — retseptning `is_optional`
    # + `is_coating` belgili qatorida. Ikkalasi bir-biridan MUSTAQIL.
    supports_coating = Column(Boolean, default=False, nullable=True)
    coating_price_multiplier = Column(Numeric(5, 2), nullable=True)   # masalan 2.00 / 2.50

    is_active = Column(Boolean, default=True)  # "O'chirilgan" emas, balki "hozircha ishlatilmaydi"
    created_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)

    boms = relationship("BOM", back_populates="product_type", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ProductType {self.name} ({self.unit})>"


# ============================================================
# BOM (Bill of Materials) — retsept "sarlavhasi"
# ============================================================

class BOM(Base):
    """Bitta mahsulot turi uchun BITTA retsept versiyasi. Bitta
    ProductType bir nechta BOM'ga ega bo'lishi mumkin (masalan
    "Standart" va "Qishki" — ADR bandi: recipe_variant_id orqali
    tanlanadi, alohida "qaysi xomashyo" tanlovi YO'Q endi)."""
    __tablename__ = "boms"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    product_type_id = Column(Integer, ForeignKey("product_types.id"), nullable=False, index=True)

    variant_name = Column(String(100), nullable=False, default="Standart")  # "Yozgi", "Qishki", "Standart"...

    # Bu retsept QANCHA mahsulot (ProductType.unit birligida) ishlab
    # chiqarish uchun mo'ljallangan — masalan batch_quantity=100 (dona)
    # bo'lsa, quyidagi BOMItem'lar shu 100 dona uchun kerakli miqdorni
    # bildiradi. Ishlab chiqarish buyurtmasi boshqa miqdorda bo'lsa,
    # nisbatan (proporsional) qayta hisoblanadi.
    batch_quantity = Column(Float, nullable=False, default=1.0)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    notes = Column(Text, nullable=True)

    product_type = relationship("ProductType", back_populates="boms")
    items = relationship("BOMItem", back_populates="bom", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BOM {self.product_type.name if self.product_type else '?'} / {self.variant_name}>"


class BOMItem(Base):
    """Retsept tarkibidagi BITTA qator — xomashyo YOKI qadoqlash
    materiali. inventory_id — Omborxonadagi ISTALGAN materialga
    bog'lanadi (qattiq yozilgan ro'yxat emas)."""
    __tablename__ = "bom_items"

    id = Column(Integer, primary_key=True, index=True)
    bom_id = Column(Integer, ForeignKey("boms.id"), nullable=False, index=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False, index=True)

    # 2026-09-16: SaaS-tayyorlik (qoida #6) — BOM/ProductionOrder singari
    # bu yerga ham to'g'ridan-to'g'ri company_id qo'shildi (parent BOM
    # orqali BILVOSITA emas), toki kelajakda BOMItem alohida so'ralganda
    # ham tenant filtri to'g'ridan-to'g'ri qo'llanilsin.
    # NULLABLE qilib qo'yilgan SABABI: bu jadval ALLAQACHON stagingda
    # mavjud (bo'sh/test qatorlari bilan) — avtomatik ustun qo'shish
    # (sync_missing_columns) faqat NULL bo'lishi mumkin bo'lgan ustunlarni
    # xavfsiz qo'sha oladi. Ilova darajasida (routes.py) BU MAYDON
    # HAR DOIM to'ldiriladi — amalda hech qachon NULL bo'lmaydi.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)

    component_type = Column(String(20), nullable=False, default=BOMComponentType.RAW_MATERIAL.value)

    # BOM.batch_quantity uchun kerakli miqdor (Inventory.unit birligida)
    quantity = Column(Float, nullable=False)

    # Isrof/yo'qotish foizi — HAR BIR komponentga alohida (ADR bandi 2).
    # Masalan scrap_factor_percent=5.0 bo'lsa, haqiqiy sarf
    # quantity * 1.05 bo'ladi.
    scrap_factor_percent = Column(Float, nullable=False, default=0.0)

    # QO'SHILDI 2026-09-20 (11.0-band). Retseptda bittadan ortiq ixtiyoriy
    # qator bo'lishi mumkin (masalan qadoqlash). "Qoplama yoqildi" degani
    # HAMMA ixtiyoriy qator qo'shilsin degani EMAS — shuning uchun qaysi
    # qator aynan qoplama ekani alohida belgilanadi. Faqat
    # `is_optional=True` bo'lganda ma'noga ega.
    is_coating = Column(Boolean, default=False, nullable=True)

    # Ixtiyoriy komponent (masalan Profil "Qoplama" — akril/loy).
    # UI'da bunday komponent(lar) bo'lsa, "Qoplama bor/yo'q" kabi
    # svitch avtomatik chiqadi (ADR bandi 3).
    is_optional = Column(Boolean, default=False)

    # Tannarxga QO'SHIMCHA xarajat (ADR bandi 7) — xomashyo narxidan
    # TASHQARI. Ikkalasi ham bo'lishi mumkin (masalan ish haqi FIXED,
    # qo'shimcha kutilmagan xarajat PERCENTAGE) — shuning uchun ikkalasi
    # ham qo'shiladi, birini tanlash shart emas.
    fixed_cost_per_unit = Column(Numeric(12, 2), nullable=True)     # 1 dona/kg mahsulotga qat'iy summa (so'm)
    percentage_cost = Column(Float, nullable=True)                   # Xomashyo narxiga nisbatan foiz (masalan 10.0 = 10%)

    notes = Column(Text, nullable=True)

    bom = relationship("BOM", back_populates="items")
    inventory = relationship("Inventory")

    @property
    def item_name(self):
        return self.inventory.item_name if self.inventory else "—"

    @property
    def unit(self):
        """2026-09-16: qoida #1 (Unit Conversion). Agar material uchun
        `base_unit` belgilangan bo'lsa (masalan "g"), retsept miqdori
        (BOMItem.quantity) O'SHA mayda birlikda kiritilgan deb hisoblanadi
        — shuning uchun ko'rsatish uchun ham o'sha birlik qaytariladi.
        Aks holda (base_unit yo'q) — eski xatti-harakat: ombor birligi
        (Inventory.unit)ning o'zi."""
        if not self.inventory:
            return "—"
        return self.inventory.base_unit or self.inventory.unit

    @property
    def stock_unit(self):
        """Har doim OMBOR birligi (Inventory.unit) — konversiyadan
        qat'i nazar. Xomashyo shu birlikda ayiriladi/saqlanadi."""
        return self.inventory.unit if self.inventory else "—"

    def __repr__(self):
        return f"<BOMItem {self.item_name}: {self.quantity} ({self.component_type})>"


# ============================================================
# PRODUCTION ORDER — ishlab chiqarish buyurtmasi
# ============================================================

class ProductionOrder(Base):
    """Ishlab chiqarish buyurtmasining o'zi. Mijoz buyurtmasi asosida
    HAM, to'g'ridan-to'g'ri omborga ishlab chiqarish uchun HAM — bir xil
    jadval, faqat source_type va source_order_id orqali farqlanadi
    (ADR bandi 10)."""
    __tablename__ = "production_orders"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    product_type_id = Column(Integer, ForeignKey("product_types.id"), nullable=False, index=True)
    bom_id = Column(Integer, ForeignKey("boms.id"), nullable=False, index=True)  # Tanlangan retsept versiyasi

    source_type = Column(String(20), nullable=False)
    source_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)  # Faqat CUSTOMER_ORDER bo'lsa
    # 2026-09-17: aniq QAYSI buyurtma-detalini to'ldirish uchun ekanini
    # bildiradi (source_order_id — faqat buyurtmaning O'ZI, bitta
    # buyurtmada bir nechta MRP-detal bo'lishi mumkin). Rezervatsiya
    # ANIQ shu maydon orqali ishlaydi — source_order_id faqat ko'rsatish/
    # moslik uchun saqlanadi.
    source_order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=True, index=True)

    quantity = Column(Float, nullable=False)  # ProductType.unit birligida — nechta ishlab chiqarilmoqda

    # Mavjud "Tayyor mahsulotlar" jadvaliga bog'lanish — IN_PROGRESS'ga
    # o'tishda bitta FinishedProduct yozuvi yaratiladi (production_status
    # = in_progress, hozirgi bir-bosqichli tizim bilan bir xil ko'rinish
    # uchun — ro'yxatda "Ishlab chiqarilmoqda" deb ko'rinadi), va
    # COMPLETED bo'lganda SHU YOZUVNING o'zi (yangisi emas) yangilanadi
    # (cost_price, production_status=ready).
    finished_product_id = Column(Integer, ForeignKey("finished_products.id"), nullable=True, index=True)

    # Agar BOM'da is_optional=True bo'lgan qatorlar bo'lsa, shulardan
    # QAYSI BIRI shu buyurtma uchun tanlangani (BOMItem.id lar ro'yxati,
    # JSON matn sifatida saqlanadi — masalan "[7, 9]").
    selected_optional_bom_item_ids_json = Column(Text, nullable=True)

    status = Column(String(20), nullable=False, default=ProductionOrderStatus.DRAFT.value)

    # IN_PROGRESS'ga o'tganda "suratga olingan" retsept — shu paytdagi
    # aniq miqdor/narxlar. Tuzilishi (har bir element):
    #   {inventory_id, item_name, unit, component_type, is_optional,
    #    included, base_quantity, scrap_factor_percent,
    #    effective_quantity_per_batch, total_quantity_needed,
    #    unit_price_at_time, line_cost}
    # (mavjud kodda ANALOG pattern: models.py'dagi
    # OrderItem.gips_additives_json bilan bir xil uslub — Text ustunda
    # JSON matn, alohida jadval emas.)
    recipe_snapshot_json = Column(Text, nullable=True)

    # COMPLETED bosqichida hisoblab, QOTIRIB qo'yiladigan yakuniy tannarx
    total_material_cost = Column(Numeric(14, 2), nullable=True)   # Faqat xomashyo+qadoqlash narxi
    total_extra_cost = Column(Numeric(14, 2), nullable=True)      # fixed_cost + percentage_cost yig'indisi
    total_cost = Column(Numeric(14, 2), nullable=True)            # material + extra — 1 DONA emas, BUTUN partiya uchun

    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)      # DRAFT -> IN_PROGRESS bo'lgan payt
    completed_at = Column(DateTime, nullable=True)    # IN_PROGRESS -> COMPLETED bo'lgan payt
    cancelled_at = Column(DateTime, nullable=True)

    notes = Column(Text, nullable=True)

    product_type = relationship("ProductType")
    bom = relationship("BOM")

    def __repr__(self):
        return f"<ProductionOrder #{self.id} {self.status} x{self.quantity}>"
