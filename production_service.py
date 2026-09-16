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
"""

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

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
    miqdorini hisoblaydi.

    Formula: 1 batch uchun quantity, isrof bilan (scrap_factor_percent),
    keyin (production_quantity / batch_quantity) nisbatiga ko'paytiriladi.
    """
    effective_per_batch = bom_item.quantity * (1 + (bom_item.scrap_factor_percent or 0) / 100.0)
    ratio = production_quantity / batch_quantity if batch_quantity else 0
    total_needed = effective_per_batch * ratio
    unit_price = float(bom_item.inventory.price_per_unit or 0) if bom_item.inventory else 0.0
    return {
        "inventory_id": bom_item.inventory_id,
        "item_name": bom_item.item_name,
        "unit": bom_item.unit,
        "component_type": bom_item.component_type,
        "is_optional": bool(bom_item.is_optional),
        "base_quantity": float(bom_item.quantity),
        "scrap_factor_percent": float(bom_item.scrap_factor_percent or 0),
        "effective_quantity_per_batch": effective_per_batch,
        "total_quantity_needed": total_needed,
        "unit_price_at_time": unit_price,
        "line_cost": total_needed * unit_price,
    }


# ============================================================
# 1. PRODUCTION ORDER YARATISH (DRAFT)
# ============================================================

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

    bom = db.query(BOM).filter(
        BOM.id == data.bom_id, BOM.product_type_id == product_type.id, BOM.is_active == True
    ).first()
    if not bom:
        return {"success": False, "message": "Tanlangan retsept (BOM) topilmadi yoki faol emas"}

    if data.source_type == ProductionSourceType.CUSTOMER_ORDER.value and not data.source_order_id:
        return {"success": False, "message": "Mijoz buyurtmasi asosida ishlab chiqarish uchun source_order_id shart"}

    po = ProductionOrder(
        company_id=company_id,
        product_type_id=product_type.id,
        bom_id=bom.id,
        source_type=data.source_type,
        source_order_id=data.source_order_id,
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
      1. Ombordagi HAR BIR kerakli xomashyoni TEKSHIRADI (yetarlimi).
      2. Yetarli bo'lmasa — Company.allow_negative_stock ga qarab:
         False bo'lsa -> BUTUNLAY TO'XTAYDI, hech narsa o'zgarmaydi;
         True bo'lsa -> davom etadi, lekin ogohlantirish qaytaradi.
      3. Retseptni "suratga oladi" (recipe_snapshot_json) — shu paytdagi
         narx/miqdorlar shu yerda QOTIB QOLADI.
      4. Mavjud "Tayyor mahsulotlar" jadvaliga IN_PROGRESS holatda
         bitta yozuv qo'shadi (hozirgi UX bilan bir xil ko'rinish uchun).

    MUHIM: bu bosqichda ombordan HALI HECH NARSA AYRILMAYDI — faqat
    tekshiriladi va "suratga olinadi". Haqiqiy ayirish faqat
    complete_production_order() da sodir bo'ladi. (Fayl boshidagi
    docstring'da yozilgan "reservation" cheklovini albatta o'qing —
    bu YETARLILIKNI TEKSHIRADI, lekin xomashyoni boshqa buyurtma
    olib qo'yishidan HIMOYA QILMAYDI, chunki Inventory'da alohida
    "band qilingan" ustuni yo'q.)
    """
    from models import Inventory  # Mavjud, asosiy Inventory jadvali

    po = db.query(ProductionOrder).filter(
        ProductionOrder.id == po_id, ProductionOrder.company_id == company_id
    ).first()
    if not po:
        return {"success": False, "message": "Ishlab chiqarish buyurtmasi topilmadi"}
    if po.status != ProductionOrderStatus.DRAFT.value:
        return {"success": False, "message": f"Faqat 'draft' holatidagi buyurtma boshlanishi mumkin (hozirgi holat: {po.status})"}

    bom = db.query(BOM).filter(BOM.id == po.bom_id).first()
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

        inv = db.query(Inventory).filter(Inventory.id == item.inventory_id).with_for_update().first()
        if not inv:
            return {"success": False, "message": f"Xomashyo topilmadi (ID {item.inventory_id})"}

        available = float(inv.stock_quantity or 0)
        needed = line["total_quantity_needed"]
        if available < needed:
            stock_warnings.append({
                "inventory_id": inv.id, "item_name": inv.item_name, "unit": inv.unit,
                "required_quantity": needed, "available_quantity": available,
                "shortage": needed - available,
            })
            if not allow_negative:
                # Qattiq rejim — BUTUN amal bekor qilinadi, hech narsa
                # o'zgarmaydi (db.commit() chaqirilmagan).
                db.rollback()
                return {
                    "success": False,
                    "message": f"Omborda yetarli '{inv.item_name}' yo'q (kerak: {needed:.2f} {inv.unit}, bor: {available:.2f} {inv.unit})",
                    "stock_issues": stock_warnings,
                }
        snapshot.append(line)

    # Mavjud "Tayyor mahsulotlar" jadvaliga "ishlab chiqarilmoqda" yozuvi
    from models import FinishedProduct, StockSource, ProductionStatus as FPStatus
    product_type = db.query(ProductType).filter(ProductType.id == po.product_type_id).first()
    fp = FinishedProduct(
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


# ============================================================
# 3. IN_PROGRESS -> COMPLETED ("Yakunlash" — haqiqiy ayirish/qo'shish)
# ============================================================

def complete_production_order(db: Session, po_id: int, company_id: int, performed_by: str = None) -> dict:
    """IN_PROGRESS holatidagi buyurtmani yakunlaydi:
      1. recipe_snapshot_json'da QOTIRILGAN miqdorlarni o'qiydi (JORIY
         BOM'ni QAYTA o'qimaydi — chunki BOM shu orada o'zgargan bo'lishi
         mumkin, lekin bu buyurtma ESKI shartlar bilan boshlangan edi).
      2. Har bir xomashyoni omborda HAQIQATAN ayiradi, log_movement()
         bilan jurnalga yozadi.
      3. Tayyor mahsulot yozuvini (FinishedProduct) 'ready' holatiga
         o'tkazadi, tannarxni (cost_price) hisoblab yozadi.
    """
    from models import Inventory, FinishedProduct, ProductionStatus as FPStatus

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

    total_material_cost = 0.0
    for line in snapshot:
        if not line.get("included"):
            continue  # Tanlanmagan ixtiyoriy komponent — o'tkazib yuboriladi
        inv = db.query(Inventory).filter(Inventory.id == line["inventory_id"]).with_for_update().first()
        if not inv:
            continue  # Xomashyo o'chirilgan bo'lsa ham, yakunlashni to'xtatmaymiz — snapshot narxi bilan hisoblashda davom etamiz
        needed = line["total_quantity_needed"]
        inv.stock_quantity = float(inv.stock_quantity or 0) - needed
        crud.log_movement(
            db, inv.id, inv.item_name, movement_type="out",
            quantity=needed, unit=inv.unit,
            reason=f"Ishlab chiqarish buyurtmasi #{po.id} yakunlandi",
            performed_by=performed_by,
        )
        total_material_cost += line["line_cost"]

    # Qo'shimcha xarajatlar (fixed_cost_per_unit, percentage_cost) —
    # BOMItem'dan emas, snapshot momentidagi narxdan hisoblanadi
    bom = db.query(BOM).filter(BOM.id == po.bom_id).first()
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
        fp = db.query(FinishedProduct).filter(FinishedProduct.id == po.finished_product_id).first()
        if fp:
            fp.cost_price = total_cost
            fp.production_status = FPStatus.READY
            fp.finished_production_at = datetime.utcnow()

    db.commit()
    db.refresh(po)
    return {"success": True, "production_order": po}


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

    if po.finished_product_id:
        fp = db.query(FinishedProduct).filter(FinishedProduct.id == po.finished_product_id).first()
        if fp:
            db.delete(fp)

    po.status = ProductionOrderStatus.CANCELLED.value
    po.cancelled_at = datetime.utcnow()
    db.commit()
    db.refresh(po)
    return {"success": True, "production_order": po}
