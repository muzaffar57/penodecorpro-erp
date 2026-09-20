"""
PenoDecorPro ERP — Production/MRP xizmat (service) qatlami
=============================================================
Mavjud crud.py uslubiga qat'iy mos yozilgan:
  - Xatolar Exception emas, {"success": False, "message": "..."} shaklida
    qaytariladi (mavjud produce_gips_finished_product va h.k. bilan bir xil).
  - Ombordan yechishdan oldin .with_for_update() bilan qator qulflanadi.
  - Har bir ombor harakati log_movement() orqali jurnalga yoziladi.
  - JSON-shaklidagi "suratlar" (snapshot) Text ustunga json.dumps bilan
    yoziladi — xuddi mavjud gips_additives_json kabi.

Bu fayl — mustaqil modul (production_models.py'ga bog'liq), lekin
qolgan qismi (log_movement, FinishedProduct va h.k.) uchun mavjud
crud.py/models.py'ga murojaat qiladi.

2026-09-16 (davomi) — "7 ta Guardrails" arxitektura talabi bo'yicha
qo'shilgan/mustahkamlangan narsalar:

  [Qoida #1 — Unit Conversion] _compute_bom_line() endi HAR BIR qatorda
  IKKI XIL miqdorni hisoblaydi: total_quantity_needed (RETSEPT birligida,
  masalan gramm — Inventory.base_unit) va total_quantity_needed_stock_unit
  (OMBOR birligida, masalan qop — Inventory.unit). Ombordan HAQIQIY
  ayirish/tekshirish HAR DOIM ikkinchisi bilan amalga oshiriladi.
  Agar Inventory.base_unit bo'sh bo'lsa — ikkalasi TENG (eski, konversiyasiz
  xatti-harakat, orqaga to'liq mos).

  [Qoida #3 — ACID/Rollback] Loyihaning butun stack'i SINXRON SQLAlchemy
  (`Session`, pg8000 drayveri, database.py'ga qarang) — asosiy main.py'ning
  BARCHA boshqa funksiyalari ham shu tarzda yozilgan. Shuning uchun
  "async with session.begin()" BU LOYIHAGA MOS EMAS (loyihada asyncio/
  asyncpg umuman yo'q — buni joriy qilish butun main.py'ni qayta yozishni
  talab qiladi, alohida, katta qaror bo'lardi). O'RNIGA, xuddi shu ATOMIKLIK
  KAFOLATI mavjud sinxron Session bilan, EXPLICIT try/except/rollback
  orqali ta'minlanadi: har bir ko'p qadamli funksiya (start/complete)
  butunlay bitta try blokida, YAGONA db.commit() oxirida, va istisno
  (Exception) yuz bersa — db.rollback() ANIQ chaqirilib, xato qayta
  ko'tariladi (raise). (Bundan tashqari, database.py'dagi get_db() ham
  so'rov darajasida xuddi shunday zaxira rollback qiladi — bu esa ikkinchi,
  ICHKI xavfsizlik qatlami sifatida qo'shildi.)
"""

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

import crud  # log_movement uchun — mavjud, sinovdan o'tgan funksiya qayta ishlatiladi
from production_models import (
    Company, ProductType, BOM, BOMItem, ProductionOrder,
    ProductionOrderStatus, ProductionSourceType, BOMComponentType,
)


# ============================================================
# YORDAMCHI FUNKSIYALAR
# ============================================================

def _get_company(db: Session, company_id: int) -> Optional[Company]:
    return db.query(Company).filter(Company.id == company_id).first()


def _compute_bom_line(bom_item: BOMItem, production_quantity: float, batch_quantity: float) -> dict:
    """Bitta BOMItem uchun, berilgan ishlab chiqarish miqdoriga mos
    ravishda, ISROF FOIZINI HISOBGA OLGAN HOLDA, kerakli xomashyo
    miqdorini hisoblaydi — HAM retsept birligida, HAM ombor birligida
    (qoida #1 — Unit Conversion).

    Formula: 1 batch uchun quantity (retsept birligida, masalan gramm),
    isrof bilan (scrap_factor_percent), keyin (production_quantity /
    batch_quantity) nisbatiga ko'paytiriladi. Natija ombor birligiga
    material.conversion_factor orqali o'giriladi (agar base_unit
    belgilangan bo'lsa) — aks holda ikkalasi bir xil (konversiya yo'q).
    """
    inv = bom_item.inventory

    effective_per_batch = bom_item.quantity * (1 + (bom_item.scrap_factor_percent or 0) / 100.0)
    ratio = production_quantity / batch_quantity if batch_quantity else 0
    total_needed_recipe_unit = effective_per_batch * ratio

    conversion_factor = float(inv.conversion_factor) if (inv and inv.conversion_factor) else None
    has_conversion = bool(inv and inv.base_unit and conversion_factor)

    if has_conversion:
        # Masalan: retsept 500 g talab qiladi, 1 qop (ombor birligi) =
        # 50000 g -> 500 / 50000 = 0.01 qop ombordan ayiriladi.
        total_needed_stock_unit = total_needed_recipe_unit / conversion_factor
    else:
        total_needed_stock_unit = total_needed_recipe_unit  # Konversiya yo'q — eski xatti-harakat

    # Narx HAR DOIM Inventory.price_per_unit — bu HAR DOIM ombor birligi
    # (Inventory.unit) uchun narx, shuning uchun tannarx OMBOR birligidagi
    # miqdorga ko'paytiriladi (retsept birligiga emas).
    unit_price = float(inv.price_per_unit or 0) if inv else 0.0
    line_cost = total_needed_stock_unit * unit_price

    return {
        "inventory_id": bom_item.inventory_id,
        "item_name": bom_item.item_name,
        "unit": bom_item.unit,                 # Retsept birligi (masalan "g") — ko'rsatish uchun
        "stock_unit": bom_item.stock_unit,      # Ombor birligi (masalan "qop") — haqiqiy ayirish shu bilan
        "conversion_factor_at_time": conversion_factor,  # Suratga olinadi — keyin material o'zgarsa ham bu buyurtmaga ta'sir qilmasin
        "component_type": bom_item.component_type,
        "is_optional": bool(bom_item.is_optional),
        "base_quantity": float(bom_item.quantity),
        "scrap_factor_percent": float(bom_item.scrap_factor_percent or 0),
        "effective_quantity_per_batch": effective_per_batch,
        "total_quantity_needed": total_needed_recipe_unit,
        "total_quantity_needed_stock_unit": total_needed_stock_unit,
        "unit_price_at_time": unit_price,
        "line_cost": line_cost,
    }


# ============================================================
# 1. PRODUCTION ORDER YARATISH (DRAFT)
# ============================================================

def get_order_mrp_readiness(db: Session, order_id: int) -> dict:
    """2026-09-17 (Milestone 4 — xavfsiz variant): buyurtmadagi barcha
    'mrp_product' turidagi detallar TO'LIQ band qilinganmi (demak,
    ishlab chiqarilib bo'lganmi), degan holatni HISOBLAB qaytaradi.

    MUHIM: bu — mavjud Order.status (OrderStatus.READY va h.k.)ga
    HECH QANDAY tegishli emas va uni O'ZGARTIRMAYDI. O'sha holat allaqachon
    ustalar KPI/bonus hisobini va buyurtmani tahrirlashni bloklashni
    ishga tushiradi (crud.py'da tekshirilgan) — MRP-tayyorlik bilan
    aralashtirib bo'lmaydi. Bu funksiya FAQAT ko'rsatish (badge) uchun.

    Har safar JORIY ma'lumotdan HISOBLANADI (saqlanadigan holat emas) —
    shuning uchun rezervatsiya ozod qilinsa, keyingi chaqiriqning o'zi
    avtomatik "hali tayyor emas"ga qaytadi — alohida "rollback" kodi
    kerak emas.

    Aralash buyurtmalar haqida: faqat 'mrp_product' turidagi detallar
    tekshiriladi. Eski turlar (Profil/Panel/Donali va h.k.) uchun ombordan
    oldindan band qilish tushunchasi umuman yo'q (ular buyurtma bilan
    birga tayyorlanadi) — shuning uchun ular har doim "tayyor" deb
    hisoblanadi, faqat MRP qismi haqiqiy to'siq bo'la oladi.
    """
    from models import OrderItem, FinishedProduct
    mrp_items = db.query(OrderItem).filter(
        OrderItem.order_id == order_id, OrderItem.category == 'mrp_product'
    ).all()
    if not mrp_items:
        return {"applicable": False}

    lines = []
    for item in mrp_items:
        reserved = db.query(func.coalesce(func.sum(FinishedProduct.reserved_quantity), 0.0)).filter(
            FinishedProduct.reserved_for_order_item_id == item.id
        ).scalar() or 0.0
        needed = float(item.quantity or 0)
        remaining = needed - float(reserved)
        lines.append({
            "order_item_id": item.id,
            "item_name": item.name,
            "needed_quantity": needed,
            "reserved_quantity": float(reserved),
            "remaining_quantity": max(0.0, remaining),
            "is_ready": remaining <= 0.0001,
        })

    return {
        "applicable": True,
        "fully_ready": all(l["is_ready"] for l in lines),
        "items": lines,
    }


def get_mrp_order_items_status(db: Session, company_id: int, product_type_id: int = None) -> list:
    """2026-09-17: "Mijoz buyurtmasi asosida" ishlab chiqarish uchun —
    barcha 'mrp_product' turidagi buyurtma-detallarini, ularning qancha
    qismi ALLAQACHON ishlab chiqarilib band qilinganini hisoblab,
    ro'yxat qilib qaytaradi. Faqat hali TO'LIQ band qilinmaganlari
    (remaining_quantity > 0) qaytariladi — allaqachon to'liq
    ta'minlanganlar ro'yxatda ko'rinmaydi (ular allaqachon bajarilgan)."""
    from models import OrderItem, Order, Project, FinishedProduct
    # M4 (2026-09-18) — TENANT: `company_id` parametri qabul qilinardi,
    # lekin so'rovda UMUMAN ishlatilmasdi — B korxonaning buyurtma
    # detallari A ning "ishlab chiqarish kerak" ro'yxatida chiqardi.
    q = db.query(OrderItem).filter(
        OrderItem.category == 'mrp_product',
        OrderItem.company_id == company_id,
    )
    if product_type_id:
        q = q.filter(OrderItem.product_type_id == product_type_id)
    items = q.all()
    result = []
    for item in items:
        reserved = db.query(func.coalesce(func.sum(FinishedProduct.reserved_quantity), 0.0)).filter(
            FinishedProduct.reserved_for_order_item_id == item.id
        ).scalar() or 0.0
        remaining = float(item.quantity or 0) - float(reserved)
        if remaining <= 0.0001:
            continue
        order = db.query(Order).filter(Order.id == item.order_id).first()
        project = db.query(Project).filter(Project.id == order.project_id).first() if order else None
        result.append({
            "order_item_id": item.id,
            "order_id": item.order_id,
            "order_number": order.order_number if order else None,
            "client_name": project.client_name if project else None,
            "item_name": item.name,
            "product_type_id": item.product_type_id,
            "needed_quantity": float(item.quantity or 0),
            "already_reserved": float(reserved),
            "remaining_quantity": remaining,
        })
    return result


def create_production_order(db: Session, company_id: int, data, created_by: str = None) -> dict:
    """Yangi ishlab chiqarish buyurtmasini DRAFT holatida yaratadi.
    Bu bosqichda OMBORGA HECH QANDAY TA'SIR YO'Q — faqat "reja" yozib
    qo'yiladi, keyinchalik tahrirlash (masalan miqdorni o'zgartirish)
    mumkin, chunki hali hech narsa "band qilinmagan"."""
    product_type = db.query(ProductType).filter(
        ProductType.id == data.product_type_id, ProductType.company_id == company_id
    ).first()
    if not product_type:
        return {"success": False, "message": "Mahsulot turi topilmadi"}

    # M4 (2026-09-18) — F6: BOM ham ANIQ joriy korxonadan olinadi.
    # Ilgari faqat `product_type` orqali bilvosita cheklanardi — bu
    # auditda `ProductionOrder → BOM` yo'nalishidagi yagona NEEDS_FIX edi.
    bom = db.query(BOM).filter(
        BOM.id == data.bom_id, BOM.product_type_id == product_type.id,
        BOM.company_id == company_id, BOM.is_active == True
    ).first()
    if not bom:
        return {"success": False, "message": "Tanlangan retsept (BOM) topilmadi yoki faol emas"}

    if data.source_type == ProductionSourceType.CUSTOMER_ORDER.value and not data.source_order_item_id:
        return {"success": False, "message": "Mijoz buyurtmasi asosida ishlab chiqarish uchun source_order_item_id shart"}

    source_order_id = data.source_order_id
    if data.source_type == ProductionSourceType.CUSTOMER_ORDER.value:
        from models import OrderItem, FinishedProduct
        # M2 (2026-09-18): detal SHU korxonaniki bo'lishi shart. Ilgari faqat
        # id bo'yicha olinardi — A korxonaning ishlab chiqarish buyurtmasi
        # B korxonaning buyurtma-detaliga bog'lanib qolishi mumkin edi.
        order_item = db.query(OrderItem).filter(
            OrderItem.id == data.source_order_item_id,
            OrderItem.company_id == company_id
        ).first()
        if not order_item:
            return {"success": False, "message": "Tanlangan buyurtma-detali topilmadi"}
        if order_item.product_type_id != product_type.id:
            return {"success": False, "message": f"Bu detal '{product_type.name}' uchun emas — noto'g'ri detal tanlangan"}
        # 2026-09-17: ORTIQCHA BAND QILISHNING oldini olish (haqiqiy xato,
        # foydalanuvchi topdi). Bu yerdagi tekshiruv — DASTLABKI, tezkor
        # signal uchun (hali qulflanmagan); HAQIQIY, poyga-xavfsiz
        # tekshiruv start_production_order()da, qatorni qulflab
        # (with_for_update) amalga oshiriladi — shu yerdagi tekshiruv
        # buni ALMASHTIRMAYDI, faqat oldindan xabardor qiladi.
        already_reserved = db.query(func.coalesce(func.sum(FinishedProduct.reserved_quantity), 0.0)).filter(
            FinishedProduct.reserved_for_order_item_id == order_item.id
        ).scalar() or 0.0
        remaining = float(order_item.quantity or 0) - float(already_reserved)
        if data.quantity > remaining + 0.0001:
            return {"success": False, "message": f"Bu buyurtma-detali uchun endi faqat {remaining:g} {product_type.unit} kerak (allaqachon {already_reserved:g} band qilingan) — {data.quantity:g} ko'p"}
        source_order_id = order_item.order_id

    po = ProductionOrder(
        company_id=company_id,
        product_type_id=product_type.id,
        bom_id=bom.id,
        source_type=data.source_type,
        source_order_id=source_order_id,
        source_order_item_id=getattr(data, 'source_order_item_id', None),
        quantity=data.quantity,
        selected_optional_bom_item_ids_json=json.dumps(data.selected_optional_bom_item_ids or []),
        status=ProductionOrderStatus.DRAFT.value,
        created_by=created_by,
        notes=data.notes,
    )
    db.add(po)
    db.commit()
    db.refresh(po)
    return {"success": True, "production_order": po}


# ============================================================
# 2. DRAFT -> IN_PROGRESS ("Boshlash" — retsept suratga olinadi)
# ============================================================

def start_production_order(db: Session, po_id: int, company_id: int, performed_by: str = None) -> dict:
    """DRAFT holatidagi buyurtmani IN_PROGRESS'ga o'tkazadi:
      1. Ombordagi HAR BIR kerakli xomashyoni TEKSHIRADI (yetarlimi) —
         konversiya (qoida #1) hisobga olingan holda, OMBOR birligida.
      2. Yetarli bo'lmasa — Company.allow_negative_stock ga qarab:
         False bo'lsa -> BUTUNLAY TO'XTAYDI, hech narsa o'zgarmaydi
         (qoida #4 — Hard Block);
         True bo'lsa -> davom etadi, lekin ogohlantirish qaytaradi
         (qoida #4 — Soft Warning).
      3. Retseptni "suratga oladi" (recipe_snapshot_json) — shu paytdagi
         narx/miqdorlar/konversiya koeffitsienti shu yerda QOTIB QOLADI
         (qoida #2 — Snapshot Immutability).
      4. Mavjud "Tayyor mahsulotlar" jadvaliga IN_PROGRESS holatda
         bitta yozuv qo'shadi (hozirgi UX bilan bir xil ko'rinish uchun).

    Butun funksiya BITTA atomik amal sifatida ishlaydi (qoida #3): agar
    QAYERDADIR kutilmagan xato yuz bersa, HAMMASI (shu jumladan yuqoridagi
    Inventory qulflari) db.rollback() bilan bekor qilinadi va xato qayta
    ko'tariladi — yarim bajarilgan holat HECH QACHON saqlanmaydi.

    MUHIM: bu bosqichda ombordan HALI HECH NARSA AYRILMAYDI — faqat
    tekshiriladi va "suratga olinadi". Haqiqiy ayirish faqat
    complete_production_order() da sodir bo'ladi. (Fayl boshidagi
    docstring'da yozilgan "reservation" cheklovini albatta o'qing —
    bu YETARLILIKNI TEKSHIRADI, lekin xomashyoni boshqa buyurtma
    olib qo'yishidan HIMOYA QILMAYDI, chunki Inventory'da alohida
    "band qilingan" ustuni yo'q.)
    """
    from models import Inventory  # Mavjud, asosiy Inventory jadvali

    try:
        po = db.query(ProductionOrder).filter(
            ProductionOrder.id == po_id, ProductionOrder.company_id == company_id
        ).first()
        if not po:
            return {"success": False, "message": "Ishlab chiqarish buyurtmasi topilmadi"}
        if po.status != ProductionOrderStatus.DRAFT.value:
            return {"success": False, "message": f"Faqat 'draft' holatidagi buyurtma boshlanishi mumkin (hozirgi holat: {po.status})"}

        bom = db.query(BOM).filter(BOM.id == po.bom_id, BOM.company_id == company_id).first()
        if not bom:
            return {"success": False, "message": "Retsept (BOM) topilmadi"}

        company = _get_company(db, company_id)
        allow_negative = bool(company.allow_negative_stock) if company else False

        selected_optional_ids = set(json.loads(po.selected_optional_bom_item_ids_json or "[]"))

        snapshot = []
        stock_warnings = []
        for item in bom.items:
            included = (not item.is_optional) or (item.id in selected_optional_ids)
            line = _compute_bom_line(item, po.quantity, bom.batch_quantity)
            line["included"] = included
            if not included:
                # Tanlanmagan ixtiyoriy komponent — suratga kiradi (shaffoflik
                # uchun, "bu safar ishlatilmagan" deb ko'rsatish mumkin bo'lsin),
                # lekin ombor tekshiruviga ham, tannarxga ham ta'sir qilmaydi.
                snapshot.append(line)
                continue

            # M4: xomashyo ham ANIQ joriy korxonadan (BOMItem→Inventory
            # himoyasi faqat YOZISH paytida ishlaydi, o'qishda emas).
            inv = db.query(Inventory).filter(
                Inventory.id == item.inventory_id,
                Inventory.company_id == company_id,
            ).with_for_update().first()
            if not inv:
                db.rollback()
                return {"success": False, "message": f"Xomashyo topilmadi (ID {item.inventory_id})"}

            available = float(inv.stock_quantity or 0)
            # Qoida #1: solishtirish HAR DOIM ombor birligida (stock_unit),
            # retsept birligida (masalan gramm) EMAS.
            needed = line["total_quantity_needed_stock_unit"]
            if available < needed:
                stock_warnings.append({
                    "inventory_id": inv.id, "item_name": inv.item_name, "unit": inv.unit,
                    "required_quantity": needed, "available_quantity": available,
                    "shortage": needed - available,
                })
                if not allow_negative:
                    # Qattiq rejim (qoida #4 — Hard Block): BUTUN amal
                    # bekor qilinadi, hech narsa o'zgarmaydi.
                    db.rollback()
                    return {
                        "success": False,
                        "message": f"Omborda yetarli '{inv.item_name}' yo'q (kerak: {needed:.4f} {inv.unit}, bor: {available:.2f} {inv.unit})",
                        "stock_issues": stock_warnings,
                    }
                # Yumshoq rejim (qoida #4 — Soft Warning): ogohlantirish
                # bilan davom etiladi, amal to'xtatilmaydi.
            snapshot.append(line)

        # 2026-09-17: ORTIQCHA BAND QILISH — HAQIQIY, POYGA-XAVFSIZ
        # (race-safe) tekshiruv. Buyurtma-detal qatorini QULFLAB
        # (with_for_update) o'qiymiz — shu tufayli, agar IKKI ISHCHI
        # (yoki ikkita so'rov) AYNI BIR PAYTDA shu detal uchun ishlab
        # chiqarishni boshlasa, IKKINCHISI birinchisi tugagunicha
        # kutadi, so'ng ALLAQACHON YANGILANGAN (band qilingan) miqdorni
        # ko'rib, kerak bo'lsa to'g'ri rad etiladi — omborni "ortiqcha
        # band qilib qo'yish" (over-reservation) imkonsiz bo'ladi.
        if po.source_order_item_id:
            from models import OrderItem, FinishedProduct
            locked_item = db.query(OrderItem).filter(
                OrderItem.id == po.source_order_item_id,
                OrderItem.company_id == company_id,          # M4
            ).with_for_update().first()
            if locked_item:
                already_reserved = db.query(func.coalesce(func.sum(FinishedProduct.reserved_quantity), 0.0)).filter(
                    FinishedProduct.reserved_for_order_item_id == locked_item.id
                ).scalar() or 0.0
                remaining = float(locked_item.quantity or 0) - float(already_reserved)
                if po.quantity > remaining + 0.0001:
                    db.rollback()
                    return {
                        "success": False,
                        "message": f"Bu buyurtma-detali uchun endi faqat {remaining:g} kerak — boshqa ishlab chiqarish buyurtmasi shu orada band qilib ulgurgan. {po.quantity:g} band qilib bo'lmaydi.",
                    }

        # Mavjud "Tayyor mahsulotlar" jadvaliga "ishlab chiqarilmoqda" yozuvi
        from models import FinishedProduct, StockSource, ProductionStatus as FPStatus
        product_type = db.query(ProductType).filter(
            ProductType.id == po.product_type_id, ProductType.company_id == company_id
        ).first()
        fp = FinishedProduct(
            # M4 (2026-09-18) — MUHIM: bu yozuvda `from_order_id`,
            # `recipe_id`, `penoplast_id` ning hech biri yo'q, shuning
            # uchun models.py dagi `_TENANT_RULES` otani topa olmaydi va
            # yozuv bazadagi vaqtinchalik `DEFAULT 1` ga tushib qolardi —
            # ya'ni B korxonaning MRP ishlab chiqarishi 1-korxonaga
            # tegishli tayyor mahsulot yaratardi. Endi ANIQ beriladi.
            company_id=company_id,
            name=product_type.name if product_type else "Noma'lum mahsulot",
            category="dynamic_bom",
            quantity=po.quantity,
            produced_quantity=po.quantity,
            unit=product_type.unit if product_type else "dona",
            unit_price=0,       # Sotuv narxi alohida (pricing_formula orqali) belgilanadi — bu yerga tegishli emas
            cost_price=0,       # COMPLETED bosqichida to'ldiriladi
            source=StockSource.PRODUCED,
            production_status=FPStatus.IN_PROGRESS,
            created_by=performed_by,
            # 2026-09-17: "Mijoz buyurtmasi asosida" bo'lsa — chiqadigan
            # BUTUN partiya SHU DAQIQADAN BOSHLAB (hali IN_PROGRESS
            # bo'lsa ham) aynan shu buyurtma-detaliga BAND qilinadi —
            # boshqa hech kim (boshqa sotuv/buyurtma) buni ololmaydi.
            # Umumiy ombor uchun (source_type=warehouse_stock) —
            # reserved_quantity=0, ya'ni butunlay erkin.
            reserved_quantity=(po.quantity if po.source_order_item_id else 0.0),
            reserved_for_order_item_id=po.source_order_item_id,
            # QO'SHILDI 2026-09-20 (Bosqich 3, 10-band). Bu ma'lumot shu
            # yerda ALLAQACHON bor edi (`po.product_type_id`), lekin tayyor
            # mahsulotga yozilmasdi — natijada liniya bo'yicha moliya
            # mahsulotning qaysi turdan ekanini bilolmasdi.
            product_type_id=po.product_type_id,
        )
        db.add(fp)
        db.flush()  # fp.id kerak, hali commit qilmasdan

        po.finished_product_id = fp.id
        po.recipe_snapshot_json = json.dumps(snapshot, ensure_ascii=False)
        po.status = ProductionOrderStatus.IN_PROGRESS.value
        po.started_at = datetime.utcnow()
        db.commit()
        db.refresh(po)

        return {"success": True, "production_order": po, "stock_warnings": stock_warnings}

    except Exception:
        # Qoida #3 — ACID: kutilmagan har qanday xatoda, shu paytgacha
        # ushbu funksiya ichida bajarilgan HAMMA narsa (Inventory qulflari,
        # FinishedProduct qo'shilishi va h.k.) bekor qilinadi.
        db.rollback()
        raise


# ============================================================
# 3. IN_PROGRESS -> COMPLETED ("Yakunlash" — haqiqiy ayirish/qo'shish)
# ============================================================

def complete_production_order(db: Session, po_id: int, company_id: int, performed_by: str = None) -> dict:
    """IN_PROGRESS holatidagi buyurtmani yakunlaydi:
      1. recipe_snapshot_json'da QOTIRILGAN miqdorlarni o'qiydi (JORIY
         BOM'ni QAYTA o'qimaydi — chunki BOM shu orada o'zgargan bo'lishi
         mumkin, lekin bu buyurtma ESKI shartlar bilan boshlangan edi;
         qoida #2 — Snapshot Immutability).
      2. Har bir xomashyoni omborda HAQIQATAN ayiradi — snapshot'dagi
         OMBOR birligidagi miqdor bilan (qoida #1 — Unit Conversion,
         konversiya allaqachon start()'da hisoblab qo'yilgan), va
         log_movement() bilan jurnalga yozadi.
      3. Tayyor mahsulot yozuvini (FinishedProduct) 'ready' holatiga
         o'tkazadi, tannarxni (cost_price) hisoblab yozadi.

    Butun funksiya BITTA atomik amal (qoida #3): xomashyo ayirish,
    tannarx hisoblash, order statusini o'zgartirish va FinishedProduct'ni
    yangilash — HAMMASI bitta db.commit() bilan yakunlanadi; QAYERDADIR
    xato chiqsa, HAMMASI (ayirilgan xomashyolar ham) db.rollback() bilan
    butunlay bekor qilinadi.
    """
    from models import Inventory, FinishedProduct, ProductionStatus as FPStatus

    try:
        po = db.query(ProductionOrder).filter(
            ProductionOrder.id == po_id, ProductionOrder.company_id == company_id
        ).first()
        if not po:
            return {"success": False, "message": "Ishlab chiqarish buyurtmasi topilmadi"}
        if po.status != ProductionOrderStatus.IN_PROGRESS.value:
            return {"success": False, "message": f"Faqat 'in_progress' holatidagi buyurtma yakunlanishi mumkin (hozirgi holat: {po.status})"}
        if not po.recipe_snapshot_json:
            return {"success": False, "message": "Retsept surati topilmadi — bu buyurtma to'g'ri boshlanmagan bo'lishi mumkin"}

        snapshot = json.loads(po.recipe_snapshot_json)

        # 2026-09-18 (chuqur audit — ENG MUHIM topilma, jonli sinovda
        # dalili bilan aniqlandi): bu yergacha xomashyo HECH QANDAY
        # tekshiruvsiz ayirilardi — agar boshqa bir ishlab chiqarish
        # (yoki oddiy sotuv) shu orada xuddi shu xomashyoni band qilib
        # ulgurgan bo'lsa (chunki IN_PROGRESS bosqichi ombordan hali
        # HAQIQATAN ayirmaydi — fayl boshidagi arxitektura izohiga
        # qarang), OMBOR MANFIY SONGA TUSHIB QOLARDI, hech qanday xato
        # yoki ogohlantirishsiz. Jonli sinov: 40 kg ombor, ikkita 30 kg'lik
        # ishlab chiqarish ikkalasi ham "Boshlash"dan o'tib, ikkalasini
        # "Yakunlash" qilinganda ombor -20 kg ga tushib qoldi. Endi
        # start_production_order() bilan BIR XIL qoidaga (company.allow_
        # negative_stock) rioya qilinadi: standart holatda (False) qattiq
        # to'xtatiladi, hozirgacha ayirilgan qatorlar (agar bo'lsa) BUTUN
        # tranzaksiya bilan birga rollback qilinadi.
        company = _get_company(db, company_id)
        allow_negative = bool(company.allow_negative_stock) if company else False

        total_material_cost = 0.0
        for line in snapshot:
            if not line.get("included"):
                continue  # Tanlanmagan ixtiyoriy komponent — o'tkazib yuboriladi
            inv = db.query(Inventory).filter(
                Inventory.id == line["inventory_id"],
                Inventory.company_id == company_id,          # M4
            ).with_for_update().first()
            if not inv:
                continue  # Xomashyo o'chirilgan bo'lsa ham, yakunlashni to'xtatmaymiz — snapshot narxi bilan hisoblashda davom etamiz
            # Qoida #1: OMBOR birligidagi miqdor bilan ayiriladi (agar
            # eski, konversiyasiz snapshot bo'lsa — kalit yo'q, shuning
            # uchun retsept-birlik qiymatiga qaytadi, orqaga mos).
            needed = line.get("total_quantity_needed_stock_unit", line["total_quantity_needed"])
            available = float(inv.stock_quantity or 0)
            if available < needed and not allow_negative:
                db.rollback()
                return {
                    "success": False,
                    "message": f"Omborda yetarli '{inv.item_name}' yo'q (kerak: {needed:.4f} {inv.unit}, bor: {available:.2f} {inv.unit}) — boshqa ishlab chiqarish shu orada band qilib ulgurgan bo'lishi mumkin",
                }
            inv.stock_quantity = available - needed
            crud.log_movement(
                db, inv.id, inv.item_name, movement_type="out",
                quantity=needed, unit=inv.unit,
                reason=f"Ishlab chiqarish buyurtmasi #{po.id} yakunlandi",
                performed_by=performed_by,
            )
            total_material_cost += line["line_cost"]

        # Qo'shimcha xarajatlar (fixed_cost_per_unit, percentage_cost) —
        # BOMItem'dan emas, snapshot momentidagi narxdan hisoblanadi
        bom = db.query(BOM).filter(BOM.id == po.bom_id, BOM.company_id == company_id).first()
        total_extra_cost = 0.0
        if bom:
            for item in bom.items:
                if item.fixed_cost_per_unit:
                    total_extra_cost += float(item.fixed_cost_per_unit) * po.quantity
                if item.percentage_cost:
                    total_extra_cost += total_material_cost * (float(item.percentage_cost) / 100.0)

        total_cost = total_material_cost + total_extra_cost

        po.total_material_cost = total_material_cost
        po.total_extra_cost = total_extra_cost
        po.total_cost = total_cost
        po.status = ProductionOrderStatus.COMPLETED.value
        po.completed_at = datetime.utcnow()

        if po.finished_product_id:
            fp = db.query(FinishedProduct).filter(
                FinishedProduct.id == po.finished_product_id,
                FinishedProduct.company_id == company_id,    # M4
            ).first()
            if fp:
                fp.cost_price = total_cost
                fp.production_status = FPStatus.READY
                fp.finished_production_at = datetime.utcnow()

        db.commit()
        db.refresh(po)
        return {"success": True, "production_order": po}

    except Exception:
        # Qoida #3 — ACID: xomashyo ayirish yarim yo'lda to'xtagan bo'lsa
        # ham, HAMMASI (shu jumladan yuqorida ayirilgan qatorlar) bekor
        # qilinadi — omborda "yarim ayirilgan" holat qolmaydi.
        db.rollback()
        raise


# ============================================================
# 4. BEKOR QILISH
# ============================================================

def cancel_production_order(db: Session, po_id: int, company_id: int, performed_by: str = None) -> dict:
    """DRAFT yoki IN_PROGRESS holatidagi buyurtmani bekor qiladi.
    IN_PROGRESS bo'lsa ham — xomashyo hali HAQIQATAN ayirilmagani
    uchun (faqat tekshirilgan va suratga olingan), ombordan hech
    narsa "qaytarish" shart emas. Faqat bog'liq FinishedProduct
    yozuvi (agar bo'lsa) ham bekor qilinadi."""
    from models import FinishedProduct

    po = db.query(ProductionOrder).filter(
        ProductionOrder.id == po_id, ProductionOrder.company_id == company_id
    ).first()
    if not po:
        return {"success": False, "message": "Ishlab chiqarish buyurtmasi topilmadi"}
    if po.status not in (ProductionOrderStatus.DRAFT.value, ProductionOrderStatus.IN_PROGRESS.value):
        return {"success": False, "message": f"'{po.status}' holatidagi buyurtmani bekor qilib bo'lmaydi"}

    try:
        if po.finished_product_id:
            fp = db.query(FinishedProduct).filter(
                FinishedProduct.id == po.finished_product_id,
                FinishedProduct.company_id == company_id,    # M4
            ).first()
            if fp:
                # 2026-09-18 (jonli sinovda aniqlangan HAQIQIY xato):
                # `production_orders.finished_product_id` hali shu yozuvga
                # ishora qilib turgani uchun, uni to'g'ridan-to'g'ri
                # o'chirish PostgreSQL FK cheklovini
                # ("production_orders_finished_product_id_fkey") buzib,
                # 500-xato berardi — IN_PROGRESS holatdagi ishlab
                # chiqarish buyurtmasini bekor qilish umuman ishlamasdi.
                # Yechim — `crud.delete_order` dagi mavjud, xavfsiz naqsh:
                # AVVAL bog'lanish uziladi, KEYIN yozuv o'chiriladi.
                fp_id_to_delete = fp.id
                po.finished_product_id = None
                db.query(ProductionOrder).filter(
                    ProductionOrder.finished_product_id == fp_id_to_delete
                ).update({"finished_product_id": None})
                db.flush()
                db.delete(fp)

        po.status = ProductionOrderStatus.CANCELLED.value
        po.cancelled_at = datetime.utcnow()
        db.commit()
        db.refresh(po)
        return {"success": True, "production_order": po}
    except Exception:
        # Qoida #3 — ACID: FinishedProduct o'chirilib, lekin status
        # yangilanmay qolgan oraliq holat hech qachon saqlanmasin.
        db.rollback()
        raise
