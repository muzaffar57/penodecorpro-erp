"""
PenoDecorPro ERP — Production/MRP uchun API yo'llari
=======================================================
Mavjud main.py juda katta (4000+ qator) bo'lgani uchun, yangi
endpointlar ATAYLAB alohida APIRouter sifatida yozildi — main.py'ga
faqat 2 qator qo'shish kifoya (pastda, "main.py'GA QO'SHISH KERAK
BO'LGAN QATORLAR" bo'limiga qarang).

Hozircha company_id har doim 1 (bitta korxona) — to'liq SaaS
migratsiyasi boshlanganda, bu joyga "joriy foydalanuvchining
korxonasi" degan haqiqiy mantiq keladi.
"""

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

import auth
import crud
from models import Inventory
from database import get_db
import production_schemas as schemas
import production_service as service
from production_models import ProductType, BOM, BOMItem, ProductionOrder, Company

# 2026-09-18 — M3: bu modulda tenant endi QATTIQ YOZILGAN qiymatdan emas,
# TIZIMGA KIRGAN foydalanuvchining korxonasidan olinadi
# (auth.company_id_of(current_user)). Ilgari hamma joyda DEFAULT_COMPANY_ID
# (=1) turardi — bitta korxonada to'g'ri ishlardi, ikkinchisi qo'shilganda
# esa MRP butunlay 1-korxonaning ma'lumoti bilan ishlab qolardi.

router = APIRouter(prefix="/api/production", tags=["production"])

# 2026-09-16: to'liq SaaS migratsiyasigacha — YAGONA korxona.
DEFAULT_COMPANY_ID = 1


def _tana(model: str, data, sxema):
    """kech93 (8-band): xom JSON QAT'IY tekshiriladi (`crud._clean_val`), keyin
    sxemaga o'giriladi (sxema ham strict — ikkinchi to'siq). Qoida buzilsa 400 va
    `detail` — MATN: `production.html` `'Xato: ' + e.detail` ni ko'rsatadi
    (sxemaning 422 ro'yxati "Xato: [object Object]" bo'lib chiqardi)."""
    try:
        toza = crud._clean_val(model, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return sxema(**toza)


def _retsept_materiallari(db: Session, items, company_id: int) -> None:
    """kech93 (8-band, HAQIQIY PostgreSQL da O'LCHANGAN `work/probe8b.py` M7 / M8):
    yo'q material id si (va 2**31) — PostgreSQL 500 (FK / integer), SQLite esa
    JIM bog'lamsiz retsept qatori saqlardi; begona korxona materiali — 409 (ORM
    qo'riqchisi). Endi har qator materiali SHU korxonada bo'lishi shart → 400
    (qaysi qator ekani bilan; begona — "topilmadi", oracle yo'q)."""
    ids = {it.inventory_id for it in items}
    bor = set()
    if ids:
        bor = {r[0] for r in db.query(Inventory.id).filter(
            Inventory.id.in_(ids), Inventory.company_id == company_id).all()}
    for i, it in enumerate(items):
        if it.inventory_id not in bor:
            raise HTTPException(status_code=400,
                                detail=f"'items' {i + 1}-qator: material topilmadi")


# ============================================================
# MAHSULOT TURLARI (ProductType)
# ============================================================

@router.get("/product-types", response_model=list[schemas.ProductTypeRead])
def list_product_types(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    return db.query(ProductType).filter(
        ProductType.company_id == auth.company_id_of(current_user), ProductType.is_active == True
    ).order_by(ProductType.name).all()


@router.post("/product-types", response_model=schemas.ProductTypeRead)
def create_product_type(data: dict = Body(...), db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    # kech93 (8-band): tana QAT'IY (`_tana`), sabab — `crud._val_rules()["ProductType"]` izohida.
    data = _tana("ProductType", data, schemas.ProductTypeCreate)
    _cid = auth.company_id_of(current_user)
    # QO'SHILDI 2026-09-20 — nom TAKRORLANMASIN.
    # Ilgari hech qanday shart yo'q edi: bitta korxona aynan bir xil
    # nomli ikkita tur yaratishi mumkin edi va ishlab chiqarish
    # oynasidagi ro'yxatda ular bir xil ko'rinardi — operator qaysi
    # biri qaysiligini ajrata olmasdi.
    # Faqat FAOL turlar tekshiriladi: nofaol qilingan (o'chirilgan)
    # turning nomini qayta ishlatish mumkin bo'lib qolsin.
    _nom = (data.name or "").strip()
    _bor = db.query(ProductType).filter(
        ProductType.company_id == _cid,
        ProductType.is_active == True,
        func.lower(func.trim(ProductType.name)) == _nom.lower(),
    ).first()
    if _bor:
        raise HTTPException(
            status_code=400,
            detail=f"'{_nom}' nomli mahsulot turi allaqachon bor. Boshqa nom tanlang.")
    _payload = data.model_dump()
    _payload["name"] = _nom
    pt = ProductType(company_id=_cid, **_payload)
    db.add(pt)
    db.commit()
    db.refresh(pt)
    return pt


@router.delete("/product-types/{pt_id}")
def deactivate_product_type(pt_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """O'chirilmaydi (eski BOM/ProductionOrder tarixi buzilmasligi
    uchun) — faqat 'nofaol' qilib belgilanadi, xuddi mavjud
    Inventory.is_deleted naqshiga o'xshab."""
    pt = db.query(ProductType).filter(ProductType.id == pt_id, ProductType.company_id == auth.company_id_of(current_user)).first()
    if not pt:
        raise HTTPException(status_code=404, detail="Mahsulot turi topilmadi")
    pt.is_active = False
    db.commit()
    return {"status": "ok"}


# ============================================================
# RETSEPTLAR (BOM)
# ============================================================

@router.get("/product-types/{pt_id}/boms", response_model=list[schemas.BOMRead])
def list_boms_for_product(pt_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    return db.query(BOM).filter(
        BOM.product_type_id == pt_id, BOM.company_id == auth.company_id_of(current_user), BOM.is_active == True
    ).all()


@router.post("/boms", response_model=schemas.BOMRead)
def create_bom(data: dict = Body(...), db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    # kech93 (8-band): tana QAT'IY (`_tana`), materiallar — shu korxonadan.
    data = _tana("BOM", data, schemas.BOMCreate)
    pt = db.query(ProductType).filter(ProductType.id == data.product_type_id, ProductType.company_id == auth.company_id_of(current_user)).first()
    if not pt:
        raise HTTPException(status_code=404, detail="Mahsulot turi topilmadi")
    _retsept_materiallari(db, data.items, auth.company_id_of(current_user))
    # QO'SHILDI 2026-09-20 — variant nomi ham TAKRORLANMASIN (yuqoridagi
    # bilan bir xil sabab: ro'yxatda ikkita "Standart" ajralmaydi).
    # kech93: faqat bo'shliqli nom ham "Standart" (ilgari '' saqlanardi).
    _vnom = (data.variant_name or "").strip() or "Standart"
    _bor = db.query(BOM).filter(
        BOM.product_type_id == pt.id,
        BOM.company_id == auth.company_id_of(current_user),
        BOM.is_active == True,
        func.lower(func.trim(BOM.variant_name)) == _vnom.lower(),
    ).first()
    if _bor:
        raise HTTPException(
            status_code=400,
            detail=f"Bu mahsulotda '{_vnom}' nomli retsept allaqachon bor. Boshqa nom tanlang.")
    bom = BOM(
        company_id=auth.company_id_of(current_user),
        product_type_id=pt.id,
        variant_name=_vnom,
        batch_quantity=data.batch_quantity,
        notes=data.notes,
    )
    db.add(bom)
    db.flush()
    for item_data in data.items:
        # Qoida #6 (Multi-tenancy): BOMItem endi to'g'ridan-to'g'ri
        # company_id'ga ega — ota-BOM orqali bilvosita emas.
        db.add(BOMItem(bom_id=bom.id, company_id=auth.company_id_of(current_user), **item_data.model_dump()))
    db.commit()
    db.refresh(bom)
    return bom


@router.put("/boms/{bom_id}", response_model=schemas.BOMRead)
def update_bom(bom_id: int, data: dict = Body(...), db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """MUHIM: bu FAQAT hali IN_PROGRESS/COMPLETED bo'lmagan kelajakdagi
    ishlab chiqarishlarga ta'sir qiladi — chunki boshlangan buyurtmalar
    o'zining recipe_snapshot_json'idan foydalanadi, JORIY BOM'ni emas."""
    # kech93 (8-band): tana QAT'IY (`_tana`), materiallar — shu korxonadan.
    data = _tana("BOM", data, schemas.BOMCreate)
    bom = db.query(BOM).filter(BOM.id == bom_id, BOM.company_id == auth.company_id_of(current_user)).first()
    if not bom:
        raise HTTPException(status_code=404, detail="Retsept topilmadi")
    _retsept_materiallari(db, data.items, auth.company_id_of(current_user))
    _vnom = (data.variant_name or "").strip() or "Standart"
    _bor = db.query(BOM).filter(
        BOM.product_type_id == bom.product_type_id,
        BOM.company_id == auth.company_id_of(current_user),
        BOM.is_active == True,
        BOM.id != bom.id,
        func.lower(func.trim(BOM.variant_name)) == _vnom.lower(),
    ).first()
    if _bor:
        raise HTTPException(
            status_code=400,
            detail=f"Bu mahsulotda '{_vnom}' nomli boshqa retsept bor. Boshqa nom tanlang.")
    bom.variant_name = _vnom
    bom.batch_quantity = data.batch_quantity
    bom.notes = data.notes
    db.query(BOMItem).filter(BOMItem.bom_id == bom.id, BOMItem.company_id == auth.company_id_of(current_user)).delete()
    for item_data in data.items:
        db.add(BOMItem(bom_id=bom.id, company_id=auth.company_id_of(current_user), **item_data.model_dump()))
    db.commit()
    db.refresh(bom)
    return bom


@router.delete("/boms/{bom_id}")
def deactivate_bom(bom_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """2026-09-16: ProductType.is_active bilan bir xil naqsh — BOM
    o'chirilmaydi (eski ProductionOrder'lar o'zining recipe_snapshot_json
    surati bilan ishlaydi, JORIY BOM'ga bog'liq emas, shuning uchun
    o'chirish ularga zarar keltirmaydi), faqat yangi buyurtmalar uchun
    tanlov ro'yxatidan yashiriladi."""
    bom = db.query(BOM).filter(BOM.id == bom_id, BOM.company_id == auth.company_id_of(current_user)).first()
    if not bom:
        raise HTTPException(status_code=404, detail="Retsept topilmadi")
    bom.is_active = False
    db.commit()
    return {"status": "ok"}


# ============================================================
# ISHLAB CHIQARISH BUYURTMALARI (ProductionOrder)
# ============================================================

@router.get("/orders", response_model=list[schemas.ProductionOrderRead])
def list_production_orders(status: str = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    q = db.query(ProductionOrder).filter(ProductionOrder.company_id == auth.company_id_of(current_user))
    if status:
        q = q.filter(ProductionOrder.status == status)
    rows = q.order_by(ProductionOrder.created_at.desc()).all()
    return [_serialize_po(r) for r in rows]


@router.get("/mrp-order-items")
def list_mrp_order_items_pending(product_type_id: int = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    """2026-09-17: "Mijoz buyurtmasi asosida" ishlab chiqarish uchun —
    hali to'liq ta'minlanmagan (remaining_quantity > 0) buyurtma-
    detallari ro'yxati, ixtiyoriy ravishda bitta mahsulot turi bo'yicha
    filtrlangan."""
    return service.get_mrp_order_items_status(db, auth.company_id_of(current_user), product_type_id)


@router.post("/orders")
def create_order(data: dict = Body(...), db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    # kech93 (8-band): tana QAT'IY (`_tana`); manba bog'lanishlari — servisda (K93-1).
    data = _tana("ProductionOrder", data, schemas.ProductionOrderCreate)
    result = service.create_production_order(db, auth.company_id_of(current_user), data, created_by=current_user.full_name or current_user.username)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return {"success": True, "production_order": _serialize_po(result["production_order"])}


@router.post("/orders/{po_id}/start")
def start_order(po_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    # ESLATMA (qoida #4): "Guardrails" talabida qattiq bloklashda HTTP 400
    # so'ralgan edi; bu yerda ATAYLAB 409 (Conflict) qoldirildi — chunki bu
    # "so'rov noto'g'ri tuzilgan" (400 ning ma'nosi) emas, balki "so'rov
    # to'g'ri, lekin joriy holat/ombor bilan ziddiyatda" degani (masalan
    # noto'g'ri holatdagi buyurtmani boshlash — shu yerning o'zida ham 409
    # qaytaradi). Ikkalasi BIR XIL endpoint ichida bo'lgani uchun, ikkitasi
    # ham 409 bo'lishi frontend uchun izchil. Agar 400'ni qat'iy xohlasangiz
    # — shu qatordagi status_code'ni almashtirish yetarli.
    result = service.start_production_order(db, po_id, auth.company_id_of(current_user), performed_by=current_user.full_name or current_user.username)
    if not result["success"]:
        raise HTTPException(status_code=409, detail={"message": result["message"], "stock_issues": result.get("stock_issues", [])})
    return {
        "success": True,
        "production_order": _serialize_po(result["production_order"]),
        "stock_warnings": result.get("stock_warnings", []),
    }


@router.post("/orders/{po_id}/complete")
def complete_order(po_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    result = service.complete_production_order(db, po_id, auth.company_id_of(current_user), performed_by=current_user.full_name or current_user.username)
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["message"])
    return {"success": True, "production_order": _serialize_po(result["production_order"])}


@router.post("/orders/{po_id}/cancel")
def cancel_order(po_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    result = service.cancel_production_order(db, po_id, auth.company_id_of(current_user), performed_by=current_user.full_name or current_user.username)
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["message"])
    return {"success": True, "production_order": _serialize_po(result["production_order"])}


# ============================================================
# KORXONA SOZLAMALARI (allow_negative_stock)
# ============================================================

@router.get("/company-settings")
def get_company_settings(db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    c = db.query(Company).filter(Company.id == auth.company_id_of(current_user)).first()
    if not c:
        raise HTTPException(status_code=404, detail="Korxona topilmadi (init_production_module ishga tushirilmagan bo'lishi mumkin)")
    return {"allow_negative_stock": c.allow_negative_stock}


@router.put("/company-settings")
def update_company_settings(allow_negative_stock: bool, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    c = db.query(Company).filter(Company.id == auth.company_id_of(current_user)).first()
    if not c:
        raise HTTPException(status_code=404, detail="Korxona topilmadi")
    c.allow_negative_stock = allow_negative_stock
    db.commit()
    return {"status": "ok"}


# ============================================================
# Yordamchi — JSON snapshot'ni sxemaga mos parse qilib beradi
# ============================================================

def _serialize_po(po: ProductionOrder) -> dict:
    import json
    data = schemas.ProductionOrderRead.model_validate(po).model_dump()
    data["recipe_snapshot"] = json.loads(po.recipe_snapshot_json) if po.recipe_snapshot_json else []
    return data
