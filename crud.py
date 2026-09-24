"""
PenoDecorPro ERP — CRUD operatsiyalari
========================================
CRUD = Create (yaratish), Read (o'qish), Update (yangilash), Delete (o'chirish).
Bu fayl bazaga yozish va o'qish funksiyalarini saqlaydi.
"""

from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy.orm import Session

from models import Master
from schemas import MasterCreate, MasterUpdate


class OverpaymentWarning(Exception):
    """To'lov summasi qarzdan ko'p bo'lganda — xato emas, faqat
    aniq tasdiqlash talab qilinishini bildiradi (frontend buni
    ushlab, tasdiqlash oynasini ko'rsatadi)."""
    def __init__(self, amount: float, debt: float, excess: float):
        self.amount = amount
        self.debt = debt
        self.excess = excess
        super().__init__(f"Ortiqcha to'lov: {excess:,.0f} so'm qarzdan ko'p")


# ============================================================
# MASTER CRUD
# ============================================================

def create_master(db: Session, master_data: MasterCreate,
                  company_id: int = None) -> Master:
    """Yangi ustani bazaga qo'shadi.

    2026-09-18 (jonli sinovda topildi): ilgari bu funksiyada takror
    tekshiruvi UMUMAN yo'q edi — bir xil telefon (yoki telegram_id)
    bilan usta qo'shilsa, baza cheklovi ishlab, foydalanuvchiga xom
    "Serverda kutilmagan xato yuz berdi" qaytardi. Ombor uchun bunday
    himoya allaqachon bor edi (main.py:/api/inventory), ustalar uchun
    esa yo'q. Endi ikkalasi bir xil: aniq, tushunarli xabar."""
    from fastapi import HTTPException

    # 15-band: qat'iy tekshiruv — HECH NARSA yozilmasdan OLDIN (ValueError → 400).
    _clean_create("Master", master_data.model_dump(exclude_unset=True))

    # M5 (2026-09-18) — TENANT: takror tekshiruvi FAQAT shu korxona
    # ichida bo'ladi. Ilgari u butun tizim bo'yicha edi va ikki xato
    # berardi: (1) boshqa korxonadagi ustaning ISMI va HOLATI xabarda
    # oshkor bo'lardi (jonli sinovda tasdiqlangan); (2) A korxona
    # B allaqachon ishlatgan raqamni umuman qo'sha olmasdi, holbuki
    # bazadagi cheklov `uq_masters_company_phone`, ya'ni korxona ichida.
    def _scoped(q):
        return q.filter(Master.company_id == company_id) if company_id is not None else q

    phone = (master_data.phone or "").strip()
    if phone:
        mavjud = _scoped(db.query(Master).filter(Master.phone == phone)).first()
        if mavjud:
            # Xabar ATAYLAB umumiy — boshqa yozuvning nomi/holati berilmaydi.
            raise HTTPException(
                status_code=400,
                detail=(f'"{phone}" raqamli usta allaqachon mavjud. '
                        f'Telefon raqami har bir ustada boshqa-boshqa '
                        f'bo\'lishi kerak.'),
            )

    tg = (str(master_data.telegram_id).strip()
          if getattr(master_data, "telegram_id", None) else "")
    if tg:
        _telegram_id_bandmi(db, tg, company_id)

    db_master = Master(
        company_id=company_id,      # M5: tenant ANIQ beriladi
        name=master_data.name,
        phone=master_data.phone,
        cashback_percent=master_data.cashback_percent,
        # 15-band (O'LCHANGAN): ilgari `kpi_percent` umuman yozilmasdi —
        # sxema uni qabul qilib, jimgina tashlab yuborardi (7 → 0.0).
        kpi_percent=(master_data.kpi_percent if master_data.kpi_percent is not None else 0.0),
        telegram_id=master_data.telegram_id,
        region=master_data.region,
        notes=master_data.notes,
        is_active=True
    )
    db.add(db_master)
    db.commit()
    db.refresh(db_master)
    return db_master


def _telegram_id_bandmi(db: Session, tg: str, company_id: int = None,
                        exclude_id: int = None) -> None:
    """Usta Telegram ID si SHU korxonada band bo'lsa — 400.

    2026-09-21 (12-sizish) — O'LCHANGAN: bazadagi cheklov endi
    `(company_id, telegram_id)` (Faza 3: bir usta ikki korxonada ishlashi
    mumkin; webhook ko'p moslikni o'zi rad etadi). Eski tekshiruv esa
    "global" yozilgan edi va natijasi FILTRGA bog'liq edi: filtr o'chiq —
    boshqa korxonadagi ID ham rad etilardi (begona ID borligini oshkor
    qiluvchi oracle), filtr yoniq — o'z korxonasidagi bilan solishtirardi.
    PUT da esa umuman tekshiruv yo'q edi → dublikat = baza xatosi (500).
    Endi POST va PUT bir xil, QAT'IY shu korxona bo'yicha."""
    from fastapi import HTTPException
    q = db.query(Master.id).filter(Master.telegram_id == tg)
    if company_id is not None:
        q = q.filter(Master.company_id == company_id)
    if exclude_id is not None:
        q = q.filter(Master.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=400,
                            detail=f'Bu Telegram ID ({tg}) allaqachon band.')


def get_masters(db: Session, only_active: bool = False,
                company_id: int = None) -> List[Master]:
    """Barcha ustalarni qaytaradi.

    M5 (2026-09-18) — TENANT: company_id berilsa, FAQAT shu korxona
    ustalari qaytariladi (ro'yxat, dropdown, hisobot — hammasi shundan
    o'qiydi)."""
    query = db.query(Master)
    if company_id is not None:
        query = query.filter(Master.company_id == company_id)
    if only_active:
        query = query.filter(Master.is_active == True)
    return query.order_by(Master.name).all()


def get_master(db: Session, master_id: int, company_id: int = None) -> Optional[Master]:
    """ID bo'yicha bitta ustani qaytaradi — M5 markaziy getter.

    M5 (2026-09-18) — TENANT: company_id berilsa, usta FAQAT shu
    korxona ichidan qidiriladi; topilmasa None (chaqiruvchi 404 beradi).
    `company_id=None` — filtrsiz, orqaga moslik uchun."""
    q = db.query(Master).filter(Master.id == master_id)
    if company_id is not None:
        q = q.filter(Master.company_id == company_id)
    return q.first()


def update_master(db: Session, master_id: int, master_data: MasterUpdate,
                  company_id: int = None) -> Optional[Master]:
    """Mavjud ustani yangilaydi."""
    db_master = get_master(db, master_id, company_id)   # M5: faqat shu korxonadan
    if not db_master:
        return None

    # Faqat berilgan maydonlarni yangilaymiz
    update_data = master_data.model_dump(exclude_unset=True)
    # M5: company_id hech qachon mijoz so'rovidan qabul qilinmaydi.
    update_data.pop("company_id", None)
    # 14-band: qat'iy tekshiruv — HECH NARSA yozilmasdan OLDIN (ValueError → 400).
    update_data = _clean_update("Master", update_data)
    # 12-sizish: Telegram ID — POST bilan bir xil qoida (500 o'rniga 400).
    if update_data.get("telegram_id"):
        update_data["telegram_id"] = str(update_data["telegram_id"]).strip()
        _telegram_id_bandmi(db, update_data["telegram_id"], db_master.company_id,
                            exclude_id=db_master.id)
    for field, value in update_data.items():
        setattr(db_master, field, value)

    db.commit()
    db.refresh(db_master)
    return db_master


def delete_master(db: Session, master_id: int, company_id: int = None) -> bool:
    """Ustani o'chiradi (haqiqatda is_active=False qilamiz, ma'lumot saqlanadi)."""
    db_master = get_master(db, master_id, company_id)   # M5: faqat shu korxonadan
    if not db_master:
        return False
    db_master.is_active = False
    db.commit()
    return True


# ============================================================
# INVENTORY CRUD
# ============================================================

from models import Inventory
from schemas import InventoryCreate, InventoryUpdate


def add_item(db: Session, item_data: InventoryCreate, company_id: int = None) -> Inventory:
    """Yangi xomashyo qo'shadi.

    2026-09-18 — M8/F1: `company_id` ANIQ beriladi. Ilgari endpoint uni
    `add_item()` QAYTGANIDAN KEYIN qo'yardi, ya'ni funksiya ichidagi
    `db.commit()` vaqtida ustun bo'sh bo'lar va faqat bazadagi vaqtinchalik
    `DEFAULT 1` uni to'ldirardi. Default olib tashlangach bu yo'l
    NOT NULL xatosi berardi — shuning uchun tenant endi boshidanoq
    beriladi. "Tiriltirish" (o'chirilgan qatorni qayta ishlatish) mantig'i
    ham SHU korxona ichida qidiradi."""
    # 15-band: qat'iy tekshiruv — HECH NARSA yozilmasdan OLDIN (ValueError → 400).
    _clean_create("Inventory", item_data.model_dump(exclude_unset=True))
    is_peno = getattr(item_data, 'is_penoplast', False)
    is_default = getattr(item_data, 'is_default_penoplast', False)

    # MUHIM: agar shu nomdagi xomashyo avval o'chirilgan bo'lsa (lekin xarid
    # tarixi bo'lgani uchun butunlay o'chmasdan, "yashirin" — is_deleted=True
    # holda qolgan bo'lsa) — YANGI qator yaratmaymiz (bu — nom takrorlanishi
    # xatosini keltirib chiqarardi), aksincha O'SHA eskisini "tiriltiramiz"
    # (is_deleted=False) va yangi ma'lumotlar bilan yangilaymiz.
    _scope = (lambda q: q.filter(Inventory.company_id == company_id)) if company_id is not None else (lambda q: q)

    existing_deleted = _scope(db.query(Inventory).filter(
        Inventory.item_name == item_data.item_name,
        Inventory.is_deleted.is_(True)
    )).first()

    # MUHIM (2): agar shu nomda ALLAQACHON, "yashirin" emas, ODDIY faol
    # (is_deleted=False) qator bo'lsa-yu, u HALI HECH QACHON ISHLATILMAGAN
    # bo'lsa (qoldiq=0 VA birorta xarid tarixi yo'q) — bu, katta ehtimol
    # bilan, "Kirim" sahifasida bekor qilingan/tugallanmagan urinishdan
    # qolgan "bo'sh" yozuv (masalan: material qo'shib, keyin ro'yxatdan
    # olib tashlangan, lekin haqiqiy kirim hech qachon tasdiqlanmagan).
    # Bunday holatda ham YANGI qator yaratib, nom takrorlanishi xatosini
    # chiqarish o'rniga — O'SHA bo'sh yozuvni qayta ishlatamiz (xuddi
    # yuqoridagi holat kabi). Bu, "materialni o'chirib-qayta yozsam xato
    # beryapti" muammosini butunlay oldini oladi.
    existing_unused = None
    if not existing_deleted:
        existing_unused = _scope(db.query(Inventory).filter(
            Inventory.item_name == item_data.item_name,
            Inventory.is_deleted.is_(False),
            Inventory.stock_quantity == 0
        )).first()
        if existing_unused:
            from models import InventoryPurchase
            has_purchase = db.query(InventoryPurchase).filter(
                InventoryPurchase.inventory_id == existing_unused.id
            ).first()
            if has_purchase:
                existing_unused = None  # haqiqiy, ishlatilgan material ekan — tegmaymiz

    existing_to_reuse = existing_deleted or existing_unused
    if existing_to_reuse:
        # 15-band (O'LCHANGAN): qayta ishlatilayotgan qator korxonaning
        # ASOSIY penoplasti bo'lsa-yu, yangi tana uni oddiy material qilsa —
        # korxonada asosiy penoplast qolmasdi. `update_item` dagi qoida bilan
        # bir xil: rad etiladi, hech narsa yozilmaydi.
        if existing_to_reuse.is_default_penoplast and not is_peno:
            raise ValueError("Asosiy penoplastni oddiy materialga aylantirib bo'lmaydi — "
                             "avval boshqa penoplastni asosiy qiling")
        existing_to_reuse.is_deleted = False
        existing_to_reuse.stock_quantity = item_data.stock_quantity
        existing_to_reuse.unit = item_data.unit
        existing_to_reuse.min_stock = item_data.min_stock
        if item_data.price_per_unit is not None:
            existing_to_reuse.price_per_unit = item_data.price_per_unit
        if item_data.volume_per_unit is not None:
            existing_to_reuse.volume_per_unit = item_data.volume_per_unit
        existing_to_reuse.is_penoplast = is_peno
        existing_to_reuse.is_default_penoplast = (is_default and is_peno)
        if getattr(item_data, 'category', None):
            existing_to_reuse.category = item_data.category
        # 15-band (O'LCHANGAN): izoh berilmasa eski izoh JIMGINA o'chardi
        # (UI yaratish formasi izoh yubormaydi). Endi kategoriya / birlik
        # kabi — faqat berilganda yangilanadi.
        if getattr(item_data, 'notes', None) is not None:
            existing_to_reuse.notes = item_data.notes
        if getattr(item_data, 'base_unit', None) is not None:
            existing_to_reuse.base_unit = item_data.base_unit
        if getattr(item_data, 'conversion_factor', None) is not None:
            existing_to_reuse.conversion_factor = item_data.conversion_factor
        if is_peno and is_default:
            # 2026-09-21 (O'LCHANGAN): qayta tiklanayotgan pozitsiyaning o'zi
            # UPDATE dan chiqariladi. Aks holda autoflush uning `True` sini
            # bazaga yozib, UPDATE uni `False` qilardi, xotiradagi `True`
            # esa "o'zgarish yo'q" bo'lib qolardi — korxonada birorta ham
            # asosiy penoplast qolmasdi.
            _scope(db.query(Inventory).filter(
                Inventory.is_default_penoplast == True,
                Inventory.id != existing_to_reuse.id)).update(
                {"is_default_penoplast": False}, synchronize_session=False
            )
            existing_to_reuse.is_default_penoplast = True
        db.flush()
        # 15-band (O'LCHANGAN): bu yo'lda boshlang'ich qoldiq uchun xarid
        # yozuvi yaratilmasdi (yangi qator yo'lida bor) — qoldiq 0 → 50
        # bo'lsa ham, xarajat Moliyada ko'rinmasdi. Endi ikki yo'l bir xil.
        _r_qty = float(item_data.stock_quantity or 0)
        _r_price = float(item_data.price_per_unit or 0)
        if _r_qty > 0 and _r_price > 0:
            from models import InventoryPurchase
            db.add(InventoryPurchase(
                inventory_id=existing_to_reuse.id,
                item_name=existing_to_reuse.item_name,
                quantity=_r_qty,
                unit=existing_to_reuse.unit,
                # 17g: narx va jami bazadagidek yaxlitlanadi (`_xarid_narx_jami`)
                price_per_unit=_xarid_narx_jami(_r_qty, _r_price)[0],
                total_amount=_xarid_narx_jami(_r_qty, _r_price)[1],
                notes="Boshlang'ich qoldiq (material yaratilganda kiritilgan)"
            ))
        # 15-band (O'LCHANGAN): yangi qator yo'lidagi kabi — korxonada asosiy
        # penoplast qolmagan bo'lsa, shu penoplast asosiy bo'ladi (aks holda
        # yagona asosiy penoplast qayta yaratilganda korxonada 0 ta qolardi).
        if is_peno and not existing_to_reuse.is_default_penoplast:
            # kech37 (18-band): yashirin qatordagi eski asosiy belgi hisobga olinmaydi
            _bor = _scope(db.query(Inventory).filter(
                Inventory.is_default_penoplast == True,
                Inventory.id != existing_to_reuse.id,
                Inventory.is_deleted.isnot(True)
            )).first()
            if not _bor:
                existing_to_reuse.is_default_penoplast = True
        db.commit()
        db.refresh(existing_to_reuse)
        return existing_to_reuse

    # Agar asosiy deb belgilangan bo'lsa — eskisini bekor qilamiz
    if is_peno and is_default:
        _scope(db.query(Inventory).filter(Inventory.is_default_penoplast == True)).update(
            {"is_default_penoplast": False}, synchronize_session=False
        )

    db_item = Inventory(
        company_id=company_id,
        item_name=item_data.item_name,
        stock_quantity=item_data.stock_quantity,
        unit=item_data.unit,
        min_stock=item_data.min_stock,
        price_per_unit=item_data.price_per_unit,
        volume_per_unit=item_data.volume_per_unit,
        is_penoplast=is_peno,
        is_default_penoplast=(is_default and is_peno),
        category=(item_data.category if getattr(item_data, 'category', None) else guess_category(item_data.item_name, is_peno)),
        notes=item_data.notes,
        base_unit=getattr(item_data, 'base_unit', None),
        conversion_factor=getattr(item_data, 'conversion_factor', None)
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    # MUHIM: agar boshlang'ich miqdor (va narx) kiritilgan bo'lsa —
    # bu ham HAQIQIY xarajat, shuning uchun uni ham "xarid" tarixiga
    # yozamiz. Aks holda bu pul Moliya hisobotlarida umuman ko'rinmay
    # qolar edi (faqat ombor miqdori yozilib, xarajat qayd etilmasdi).
    qty = float(item_data.stock_quantity or 0)
    price = float(item_data.price_per_unit or 0)
    if qty > 0 and price > 0:
        from models import InventoryPurchase
        purchase = InventoryPurchase(
            inventory_id=db_item.id,
            item_name=db_item.item_name,
            quantity=qty,
            unit=db_item.unit,
            # 17g: narx va jami bazadagidek yaxlitlanadi (`_xarid_narx_jami`)
            price_per_unit=_xarid_narx_jami(qty, price)[0],
            total_amount=_xarid_narx_jami(qty, price)[1],
            notes="Boshlang'ich qoldiq (material yaratilganda kiritilgan)"
        )
        db.add(purchase)
        db.commit()

    # Agar birinchi penoplast bo'lsa — avtomatik asosiy qilamiz
    # kech37 (18-band): yashirilgan (o'chirilgan) qatordagi eski asosiy belgi
    # hisobga olinmaydi — aks holda korxonada ko'rinadigan asosiy penoplast
    # bo'lmasa ham yangi penoplast asosiy bo'lmasdi (PG da O'LCHANGAN).
    if is_peno:
        has_default = _scope(db.query(Inventory).filter(
            Inventory.is_default_penoplast == True,
            Inventory.is_deleted.isnot(True)
        )).first()
        if not has_default:
            db_item.is_default_penoplast = True
            db.commit()
            db.refresh(db_item)

    return db_item


def get_inventory(db: Session, company_id: int = None) -> List[Inventory]:
    """Barcha xomashyo ro'yxatini qaytaradi (o'chirilganlar bundan mustasno)."""
    q = db.query(Inventory).filter(Inventory.is_deleted.isnot(True))
    if company_id is not None:
        q = q.filter(Inventory.company_id == company_id)
    return q.order_by(Inventory.item_name).all()


def get_item(db: Session, item_id: int, company_id: int = None) -> Optional[Inventory]:
    """ID bo'yicha bitta xomashyoni qaytaradi.

    2026-09-18 — M3: company_id berilsa, material FAQAT shu korxonadan
    qidiriladi. Berilmasa — eski xatti-harakat (ichki, allaqachon
    tekshirilgan oqimlar uchun). Tashqi chaqiruvlar company_id uzatadi."""
    q = db.query(Inventory).filter(Inventory.id == item_id)
    if company_id is not None:
        q = q.filter(Inventory.company_id == company_id)
    return q.first()


def get_item_locked(db: Session, item_id: int, company_id: int = None) -> Optional[Inventory]:
    """ID bo'yicha xomashyoni QULFLAB qaytaradi (SELECT ... FOR UPDATE).

    Bir nechta foydalanuvchi AYNI shu xomashyoni bir vaqtda o'zgartirmoqchi
    bo'lsa — ikkinchisi birinchisi tugaguncha (millisekundlar) kutadi,
    shunda hech kimning o'zgartirishi "yo'qolib" ketmaydi.
    Faqat MIQDORNI O'ZGARTIRISH kerak bo'lgan joylarda ishlatiladi —
    oddiy ko'rish/ro'yxat uchun emas (aks holda keraksiz sekinlik yaratadi).
    PostgreSQL'da haqiqiy qulflaydi; SQLite'da (test muhiti) e'tiborsiz qoldiriladi."""
    q = db.query(Inventory).filter(Inventory.id == item_id)
    if company_id is not None:
        q = q.filter(Inventory.company_id == company_id)
    return q.with_for_update().first()


def create_expense_transaction(db: Session, data, performed_by: Optional[str] = None, source: str = "manual",
                               company_id: int = None):
    """Yangi xarajat tranzaksiyasini yaratadi. Bu funksiya faqat YANGI ExpenseTransaction
    jadvaliga yozadi — mavjud MonthlyExpense yoki hisob-kitob logikasiga umuman tegmaydi."""
    from models import ExpenseTransaction
    # 17e (2026-09-22): ILDIZ — tana QAT'IY (summa musbat va chekli,
    # kategoriya 1–30 belgi, yo'nalish ro'yxatdan, sana 2000–2100).
    # Marshrut ham tekshiradi; bu qatlam boshqa chaqiruvchilar uchun.
    data = _clean_val("ExpenseTransaction", _val_dump(data, "ExpenseTransaction"))
    # M6 — TENANT: company_id ANIQ beriladi (ota-FK yo'q, DEFAULT 1 ga tushmasin).
    tx = ExpenseTransaction(
        company_id=company_id,
        date=data.get("date") or datetime.utcnow(),
        category=data["category"],
        amount=data.get("amount", 0),
        notes=data.get("notes"),
        created_by=performed_by,
        source=source,
        production_type=data.get("production_type"),
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def update_expense_transaction(db: Session, tx_id: int, data,
                               company_id: int = None) -> Optional["ExpenseTransaction"]:
    """2026-09-16: foydalanuvchi so'rovi bo'yicha qo'shildi — xato kiritilgan
    summani (masalan "125 000" o'rniga "125") o'chirib-qayta yozish o'rniga,
    to'g'ridan-to'g'ri TAHRIRLASH imkonini beradi. create_expense_transaction
    kabi — faqat shu BITTA ExpenseTransaction yozuvini yangilaydi, boshqa
    hech qanday jadval yoki hisob-kitobga (Kassa balansi va h.k. — bular
    har safar JORIY yozuvlar asosida qayta hisoblanadi) alohida ta'sir
    qilmaydi."""
    from models import ExpenseTransaction
    # 17e (2026-09-22): ILDIZ — yaratish bilan BIR XIL qat'iy qoida
    # (bazaga tegishdan OLDIN; xato → `ValueError`, hech narsa yozilmaydi).
    data = _clean_val("ExpenseTransaction", _val_dump(data, "ExpenseTransaction"))
    _q = db.query(ExpenseTransaction).filter(ExpenseTransaction.id == tx_id)
    if company_id is not None:      # M6: faqat shu korxonadan
        _q = _q.filter(ExpenseTransaction.company_id == company_id)
    tx = _q.first()
    if not tx:
        return None
    if "date" in data and data["date"]:
        tx.date = data["date"]
    if "category" in data and data["category"]:
        tx.category = data["category"]
    if "amount" in data and data["amount"] is not None:
        tx.amount = data["amount"]
    if "notes" in data:
        tx.notes = data["notes"]
    if "production_type" in data:
        tx.production_type = data["production_type"]
    db.commit()
    db.refresh(tx)
    return tx


def get_expense_transactions(db: Session, year: Optional[int] = None, month: Optional[int] = None,
                              day: Optional[int] = None, category: Optional[str] = None, limit: int = 200,
                              company_id: int = None):
    """Xarajat tranzaksiyalari ro'yxati — faqat o'qish (M6 — tenant-safe)."""
    from models import ExpenseTransaction
    from sqlalchemy import extract
    q = db.query(ExpenseTransaction)
    if company_id is not None:
        q = q.filter(ExpenseTransaction.company_id == company_id)
    if year:
        q = q.filter(extract('year', ExpenseTransaction.date) == year)
    if month:
        q = q.filter(extract('month', ExpenseTransaction.date) == month)
    if day:
        q = q.filter(extract('day', ExpenseTransaction.date) == day)
    if category:
        q = q.filter(ExpenseTransaction.category == category)
    return q.order_by(ExpenseTransaction.date.desc()).limit(limit).all()


def delete_expense_transaction(db: Session, tx_id: int, company_id: int = None) -> bool:
    from models import ExpenseTransaction
    _q = db.query(ExpenseTransaction).filter(ExpenseTransaction.id == tx_id)
    if company_id is not None:      # M6: faqat shu korxonadan
        _q = _q.filter(ExpenseTransaction.company_id == company_id)
    tx = _q.first()
    if not tx:
        return False
    db.delete(tx)
    db.commit()
    return True


def log_movement(db: Session, inventory_id: Optional[int], item_name: str, movement_type: str,
                  quantity: float, unit: Optional[str] = None, reason: Optional[str] = None,
                  order_id: Optional[int] = None, supplier_id: Optional[int] = None,
                  performed_by: Optional[str] = None, notes: Optional[str] = None,
                  company_id: Optional[int] = None, is_brak: Optional[bool] = None):
    """Ombor harakati jurnaliga bitta yozuv qo'shadi.

    kech52 (13-band, 3-qadam): `is_brak` — brak harakati belgisi (hisobot shu
    belgiga qaraydi, sabab matniga emas). Berilmasa: CHIQIM brak oynasi ichida
    bo'lsa True — `create_return_item` brak yozuvi raqamini
    (`db.info["_brak_qaytarish_id"]`) yoki ishlab chiqarish braki
    `db.info["_brak_harakat"]` belgisini sessiyaga qo'yadi (chuqur `services`
    chaqiruvlari — tayyor loy, loy ingredientlari — ham shu yo'l bilan
    belgilanadi); aks holda False. Hech qachon NULL yozilmaydi.

    MUHIM: bu funksiya faqat LOG yozadi — hech qanday hisob-kitobga yoki
    stock_quantity qiymatiga ta'sir qilmaydi. Xato yuz bersa ham asosiy
    amalni to'xtatmaslik uchun try/except bilan o'ralgan."""
    from models import InventoryMovement
    try:
        if quantity is None or quantity == 0:
            return
        # M8/F1: uchala ota-FK (`inventory_id`, `order_id`, `supplier_id`)
        # ham NULL bo'lishi mumkin (o'chirilgan material bo'yicha harakat) —
        # bunday holatda qo'riqchi korxonani aniqlay olmaydi.
        _cid = company_id
        if _cid is None and inventory_id:
            _inv_row = db.query(Inventory.company_id).filter(Inventory.id == inventory_id).first()
            _cid = _inv_row[0] if _inv_row else None
        # kech45 (13-band, 6-qadam): `create_return_item` brak xomashyosini
        # yechayotganda sessiyaga brak yozuvi raqamini qo'yadi — shu oraliqda
        # yozilgan HAR harakat (penoplast, tayyor loy, loy ingredientlari —
        # `services` ichidagi chuqur chaqiruvlar ham) unga bog'lanadi.
        _brak_rid = db.info.get("_brak_qaytarish_id") if movement_type == "out" else None
        if is_brak is None:
            _brak = movement_type == "out" and (_brak_rid is not None
                                                or bool(db.info.get("_brak_harakat")))
        else:
            _brak = bool(is_brak)
        # kech46 (13-band, 2-qadam): chiqim paytidagi 1 birlik narxi muzlatiladi.
        # `db.get` — sessiyadagi (hali yozilmagan) o'zgarishni ham ko'radi.
        # Narx belgilanmagan material — 0 (hisobot ham 0 deb hisoblardi).
        # Material topilmasa (o'chirilgan) — NULL. Narxni o'qish yiqilsa ham
        # harakat YOZILADI (narxsiz — hisobot joriy narxni oladi): tashqi
        # `except` butun harakatni tashlab yuborardi (kech46 M04 da O'LCHANDI).
        _narx = None
        if movement_type == "out" and inventory_id:
            try:
                _inv_narx = db.get(Inventory, inventory_id)
                if _inv_narx is not None:
                    _narx = float(_inv_narx.price_per_unit or 0)
            except Exception:
                _narx = None
        db.add(InventoryMovement(
            company_id=_cid,
            inventory_id=inventory_id, item_name=item_name, movement_type=movement_type,
            quantity=abs(float(quantity)), unit=unit, reason=reason,
            order_id=order_id, supplier_id=supplier_id,
            performed_by=performed_by, notes=notes,
            return_item_id=_brak_rid,
            unit_cost=_narx,
            is_brak=_brak
        ))
    except Exception as e:
        try:
            log_error(db, str(e), endpoint="log_movement")
        except Exception:
            pass


# Qo'lda qoldiq tuzatish (`POST /api/inventory/{id}/stock`) tanasi —
# 19-band (2026-09-21). Harakat jurnali `reason` ustuni String(200):
# uzunroq izoh PostgreSQL da commit paytida 500 berardi.
_STOCK_REASON_MAX = 200


def _jurnal_sabab(matn) -> str:
    """20-band (2026-09-21): ombor jurnali `reason` ustuni String(200).
    Nom qo'shiladigan sabablar (mahsulot nomi 150 belgigacha) ustundan oshsa
    PostgreSQL COMMIT paytida yiqiladi (`log_movement` ichidagi try/except
    uni USHLAMAYDI — `db.add` o'tadi, xato keyin chiqadi). Shuning uchun
    sabab 200 belgiga xavfsiz qisqartiriladi."""
    matn = "" if matn is None else str(matn)
    return matn if len(matn) <= _STOCK_REASON_MAX else matn[:_STOCK_REASON_MAX - 1] + "…"


def _stock_son(value):
    """`quantity_change` — ishorali (musbat = kirim, manfiy = chiqim), chekli,
    0 emas, `true/false` emas, sig'imdan katta emas. Aks holda ValueError."""
    import math
    if value is None:
        raise ValueError("'quantity_change' bo'sh bo'lishi mumkin emas")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("'quantity_change' son bo'lishi kerak")
    v = float(value)
    if math.isnan(v) or math.isinf(v):
        raise ValueError("'quantity_change' son bo'lishi kerak")
    if v == 0:
        raise ValueError("'quantity_change' 0 bo'lishi mumkin emas")
    if abs(v) > _UPD_SON_CHEGARA:
        raise ValueError("'quantity_change' juda katta")
    return v


def _clean_stock_change(data) -> dict:
    """Marshrut tanasi (xom JSON) → {"quantity_change", "reason"}.
    Ruxsat ro'yxati + qat'iy turlar; buzilsa ValueError (→ 400)."""
    if not isinstance(data, dict):
        raise ValueError("Noto'g'ri so'rov")
    notogri = sorted(str(k)[:40] for k in data if k not in ("quantity_change", "reason"))
    if notogri:
        raise ValueError("Noma'lum maydon: " + ", ".join(notogri[:10]))
    qc = _stock_son(data.get("quantity_change"))
    reason = data.get("reason")
    if reason is not None:
        if not isinstance(reason, str):
            raise ValueError("'reason' matn bo'lishi kerak")
        if len(reason) > _STOCK_REASON_MAX:
            raise ValueError(f"'reason' juda uzun ({_STOCK_REASON_MAX} belgidan ko'p)")
    return {"quantity_change": qc, "reason": reason}


# kech52 (13-band, 3-qadam, 38-band qarori "C"): Omborxonadagi qo'lda "Chiqim" izohi shu
# so'z bilan boshlansa — o'sha chiqim brak xarajati hisoblanadi (`update_stock`).
QOLDA_BRAK_BOSHI = "Brak"


def update_stock(db: Session, item_id: int, quantity_change: float, performed_by: Optional[str] = None,
                 notes: Optional[str] = None, company_id: int = None) -> Optional[Inventory]:
    """Mahsulot qoldig'ini yangilaydi (musbat = qo'shish, manfiy = ayirish).
    Narxsiz oddiy tuzatish uchun (masalan inventarizatsiya). Xarid uchun
    purchase_stock() dan foydalaning — u narxni ham hisobga oladi.

    19-band (2026-09-21, O'LCHANGAN): ilgari chiqim qoldiqdan ko'p bo'lsa
    qoldiq JIMGINA 0 ga qirqilardi, jurnalga esa so'ralgan to'liq miqdor
    yozilardi (qoldiq 100, chiqim 1000 → 0, harakat "out 1000"). Loy
    qoldig'i endi manfiy bo'lishi mumkin (foydalanuvchi qarori) — bu
    qirqish MANFIY qoldiqdagi qarzni o'chirib yuborardi (-30 da 5 chiqim →
    0, ya'ni +30). Endi: chiqim mavjud qoldiqdan (manfiy bo'lsa — 0 dan)
    ko'p bo'lsa ValueError (→ 400), hech narsa yozilmaydi; kirim (musbat)
    arifmetik — manfiy qoldiqni qoplaydi. Qiymat HECH NARSA yozilmasdan
    OLDIN qat'iy tekshiriladi (NaN/cheksiz/bool/0 — ValueError)."""
    qc = _stock_son(quantity_change)
    if notes is not None and len(str(notes)) > _STOCK_REASON_MAX:
        raise ValueError(f"'reason' juda uzun ({_STOCK_REASON_MAX} belgidan ko'p)")
    db_item = get_item_locked(db, item_id, company_id)
    if not db_item:
        return None
    current = float(db_item.stock_quantity or 0)
    if qc < 0:
        mavjud = max(current, 0.0)
        if -qc > mavjud + 1e-9:
            if current < 0:
                raise ValueError(
                    f"{db_item.item_name}: qoldiq manfiy ({current:g} {db_item.unit}) — "
                    f"chiqim qilib bo'lmaydi, avval kirim qiling")
            raise ValueError(
                f"{db_item.item_name}: omborda {current:g} {db_item.unit} bor — "
                f"{-qc:g} {db_item.unit} chiqim qilib bo'lmaydi")
    new_qty = current + qc
    if -1e-9 < new_qty < 0:
        new_qty = 0.0
    db_item.stock_quantity = new_qty
    log_movement(
        db, db_item.id, db_item.item_name,
        movement_type="in" if qc > 0 else "out",
        quantity=qc, unit=db_item.unit,
        reason=notes or "Qo'lda tuzatish (inventarizatsiya)", performed_by=performed_by,
        # kech52 (13-band, 3-qadam) — FOYDALANUVCHI QARORI (38-band, tugma bilan): "C — izoh
        # 'Brak' bilan boshlansa, brak hisoblansin (hozirgidek)". Qo'lda CHIQIM izohi
        # QOLDA_BRAK_BOSHI bilan boshlansa — brak xarajati (Moliya, sof foyda). Katta-kichik
        # harfga SEZGIR — Railway (PostgreSQL) dagi avvalgi `LIKE 'Brak%'` xulqi bilan AYNAN
        # (kichik harfli "brak" avval SQLite da brak, PG da brak EMAS edi — endi ikkala bazada
        # bir xil: EMAS). Belgi YOZISH paytida bir marta aniqlanadi, keyin matnga qaralmaydi.
        is_brak=(qc < 0 and str(notes or "").startswith(QOLDA_BRAK_BOSHI))
    )
    db.commit()
    db.refresh(db_item)
    return db_item


def guess_category(item_name: str, is_penoplast: bool = False) -> str:
    """Material nomidan kategoriyani taxmin qiladi.

    3 asosiy guruh:
    1) Penoplast — penoplast xomashyosi
    2) Kimyoviy qo'shimchalar — suyuq/kimyoviy moddalar (akril, pva, zagustitel, penogasitel)
    3) Qattiq qotishmalar — qum, mel, kroshka va shunga o'xshash quruq materiallar
    """
    name = (item_name or '').lower()
    if is_penoplast or 'penoplast' in name or 'penopleks' in name:
        return "Penoplast"
    if any(k in name for k in ['akril', 'pva', 'zagustitel', 'penogasitel', 'texanol', 'biosid', 'hpmc']):
        return "Kimyoviy qo'shimchalar"
    if any(k in name for k in ['qum', 'kroshka', "shag'al", 'mel', 'kvars', 'mikroklasit', 'mikrokalsit']):
        return "Qattiq qotishmalar"
    return "Boshqa"


def purchase_stock(db: Session, item_id: int, quantity: float, price_per_unit: float,
                   purchased_by: str = None, notes: str = None,
                   supplier_id: int = None, is_credit: bool = False,
                   volume_per_unit: float = None, payment_due_date: str = None,
                   is_opening_stock: bool = False, extra_cost_per_unit: float = 0.0):
    """Ombor kirimi — xarid narxi bilan (DARHOL commit qiladi — ORQAGA MOSLIK
    uchun saqlangan, hozirgi barcha eski chaqiruvchilar shu funksiyani
    ishlatadi). Ko'p mahsulotli, BITTA tranzaksiya kerak bo'lgan hollarda
    (masalan Ombor Kirim hujjati) — o'rniga _purchase_stock_no_commit()
    ishlatiladi, va commit FAQAT oxirida, bir marta qilinadi."""
    result = _purchase_stock_no_commit(
        db, item_id, quantity, price_per_unit, purchased_by, notes,
        supplier_id, is_credit, volume_per_unit, payment_due_date,
        is_opening_stock, extra_cost_per_unit
    )
    if result is None:
        return None
    db.commit()
    db.refresh(result["item"])
    result["new_price"] = float(result["item"].price_per_unit)
    result["new_volume"] = float(result["item"].volume_per_unit)
    return result


def _purchase_stock_no_commit(db: Session, item_id: int, quantity: float, price_per_unit: float,
                   purchased_by: str = None, notes: str = None,
                   supplier_id: int = None, is_credit: bool = False,
                   volume_per_unit: float = None, payment_due_date: str = None,
                   is_opening_stock: bool = False, extra_cost_per_unit: float = 0.0,
                   company_id: int = None):
    """Ombor kirimi — xarid narxi bilan. COMMIT QILMAYDI (chaqiruvchi
    o'zi, barcha ishlar tugagach, bitta marta commit qilishi kerak).
    O'rtacha vaznli narx hisoblanadi (eski qoldiq qayta baholanmaydi):

        yangi_narx = (eski_qty × eski_narx + yangi_qty × xarid_narxi) / (eski_qty + yangi_qty)

    Penoplast uchun volume_per_unit (1 blok necha m³) ham partiyadan partiyaga
    farq qilishi mumkin — shu sabab u ham xuddi shu tarzda o'rtacha vaznli hisoblanadi,
    aks holda tan narx/hajm hisob-kitobi noto'g'ri chiqib qoladi.

    is_credit=True bo'lsa — nasiya (keyin to'lash), Supplierga qarz sifatida yoziladi.
    supplier_id — kredit bo'lmasa ham saqlanadi (tarix uchun, "kimdan olganimiz" bilinsin).
    is_opening_stock=True bo'lsa — bu "boshlang'ich (mavjud) ombor" sifatida belgilanadi:
    ombor miqdori/narxi ODATDAGIDEK qo'shiladi, LEKIN Kassa balansi hisobida bu
    "naqd sarflangan pul" deb HISOBLANMAYDI (chunki bu — yangi xarid emas, tizimni
    ishlata boshlashda mavjud xomashyoni hisobga olish).

    extra_cost_per_unit — Ombor Kirim hujjatidagi qo'shimcha xarajatlar (Transport,
    Tushirish, Yuklash, Boshqa) shu material uchun taqsimlangan ulushi (1 birlikka).
    MUHIM: bu, faqat OMBORDAGI O'RTACHA TANNARXni oshirish uchun ishlatiladi —
    InventoryPurchase yozuvidagi price_per_unit/total_amount esa, ASL (tashqi
    hisobot, yetkazib beruvchi qarzi uchun) narxda, o'zgarishsiz qoladi.
    """
    from models import InventoryPurchase

    # 2026-09-21 (12-sizish): company_id berilsa material FAQAT shu
    # korxonadan (aks holda None → chaqiruvchi "Material topilmadi").
    db_item = get_item_locked(db, item_id, company_id)
    if not db_item:
        return None

    old_qty = float(db_item.stock_quantity or 0)
    old_price = float(db_item.price_per_unit or 0)
    old_volume = float(db_item.volume_per_unit or 1.0)

    # O'rtacha tannarx hisoblanadiganda — ASL narx EMAS, "samarali narx"
    # (asl narx + shu birlikka to'g'ri kelgan qo'shimcha xarajat) ishlatiladi.
    effective_price_for_avg = price_per_unit + (extra_cost_per_unit or 0.0)

    total_qty = old_qty + quantity
    if old_qty > 0 and total_qty > 0:
        # Oddiy holat — eski qoldiq HAM ijobiy, shuning uchun to'g'ri,
        # haqiqiy o'rtacha vaznli narxni hisoblaymiz.
        weighted_price = (old_qty * old_price + quantity * effective_price_for_avg) / total_qty
    else:
        # MUHIM (2026-08-18): eski qoldiq MANFIY yoki "0" bo'lsa — eski
        # narxni O'RTACHAGA UMUMAN QO'SHMAYMIZ. Sabab: manfiy miqdorning
        # haqiqiy tannarx asosi yo'q (u — hali kelmagan, "qarzga" ishlatilgan
        # xomashyo). Agar shunday holatda ham eski narxni qo'shsak, natija
        # HAR IKKALA (eski va yangi) narxdan ham chetga chiqib ketardi —
        # masalan -5 dona (785 000 so'm) + 20 dona (900 000 so'm) qo'shilsa,
        # to'g'ri formula 938 333 so'm (ikkalasidan ham QIMMAT!) berardi.
        # Shuning uchun, bunday holatda, faqat YANGI xarid narxi ishlatiladi.
        weighted_price = effective_price_for_avg

    db_item.stock_quantity = total_qty
    db_item.price_per_unit = round(weighted_price, 2)

    volume_changed = False
    if db_item.is_penoplast and volume_per_unit and volume_per_unit > 0:
        if abs(volume_per_unit - old_volume) > 0.001:
            volume_changed = True
        if total_qty > 0:
            weighted_volume = (old_qty * old_volume + quantity * volume_per_unit) / total_qty
        else:
            weighted_volume = volume_per_unit
        db_item.volume_per_unit = round(weighted_volume, 4)

    if not db_item.category:
        db_item.category = guess_category(db_item.item_name, db_item.is_penoplast)

    due_date_parsed = None
    if payment_due_date:
        try:
            due_date_parsed = datetime.strptime(payment_due_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            due_date_parsed = None

    # 17g (2026-09-22): narx va jami BAZADAGIDEK yaxlitlanadi — jami SHU
    # (yaxlitlangan) narxdan hisoblanadi (sababi `_xarid_narx_jami` izohida;
    # HAQIQIY PostgreSQL da O'LCHANGAN: 333 × 10.335 → narx 10.34, jami
    # 3441.56). Ombordagi o'rtacha narx hisobiga tegilmaydi.
    _narx2, _jami2 = _xarid_narx_jami(quantity, price_per_unit)
    purchase = InventoryPurchase(
        inventory_id=db_item.id,
        item_name=db_item.item_name,
        quantity=quantity,
        unit=db_item.unit,
        price_per_unit=_narx2,
        total_amount=_jami2,
        purchased_by=purchased_by,
        notes=notes,
        supplier_id=supplier_id,
        is_credit=is_credit,
        category=db_item.category,
        payment_due_date=due_date_parsed,
        is_opening_stock=is_opening_stock,
        extra_cost_per_unit=round(extra_cost_per_unit or 0.0, 4)
    )
    db.add(purchase)
    supplier_name = None
    if supplier_id:
        from models import Supplier
        sup = db.query(Supplier).filter(Supplier.id == supplier_id).first()
        supplier_name = sup.name if sup else None
    log_movement(
        db, db_item.id, db_item.item_name, movement_type="in",
        quantity=quantity, unit=db_item.unit,
        reason=f"Yetkazib beruvchi: {supplier_name}" if supplier_name else "Xarid",
        supplier_id=supplier_id, performed_by=purchased_by, notes=notes
    )
    db.flush()

    return {
        "item": db_item,
        "purchase": purchase,
        "old_price": old_price,
        "new_price": float(db_item.price_per_unit),
        "old_qty": old_qty,
        "purchase_total": _jami2,
        "old_volume": old_volume,
        "new_volume": float(db_item.volume_per_unit),
        "volume_changed": volume_changed
    }


def create_inventory_receipt(db: Session, items: list, transport_cost: float = 0.0,
                              tushirish_cost: float = 0.0, yuklash_cost: float = 0.0,
                              boshqa_cost: float = 0.0, add_to_cost: bool = False,
                              supplier_id: int = None, document_number: str = None,
                              paid_now: float = 0.0, notes: str = None, created_by: str = None,
                              production_type: str = None, company_id: int = None) -> dict:
    """Ombor Kirim hujjati — bir nechta mahsulotni, qo'shimcha xarajatlar
    (Transport, Tushirish/Grushchik, Yuklash, Boshqa) bilan birga, BITTA
    yagona tranzaksiya sifatida saqlaydi. Xato bo'lsa — HAMMASI (barcha
    mahsulotlar, barcha xarajatlar) ROLLBACK qilinadi, hech narsa
    yarim-yorti saqlanib qolmaydi.

    items — har biri: {inventory_id, quantity, price_per_unit, volume_per_unit
    (ixtiyoriy), is_opening_stock (ixtiyoriy), notes (ixtiyoriy)}

    add_to_cost=True bo'lsa — 4 ta qo'shimcha xarajat, mahsulotlarning
    QIYMATIGA (quantity × price_per_unit) NISBATAN PROPORSIONAL taqsimlanadi,
    va ombordagi o'rtacha tannarxga qo'shiladi. False bo'lsa — bu xarajatlar
    faqat Moliyada, alohida ko'rinadi, tannarxga ta'sir qilmaydi.

    paid_now — MUHIM: soddalashtirilgan yondashuv (Xomashyo ta'minoti
    sahifasidagi bilan bir xil mantiq). Har bir mahsulot ALOHIDA-ALOHIDA
    qisman to'lov taqsimlanmaydi — barcha mahsulotlar TO'LIQ NASIYA
    (is_credit=True) sifatida yoziladi (agar boshlang'ich ombor bo'lmasa),
    so'ngra, agar paid_now>0 bo'lsa, YAGONA, umumiy SupplierPayment
    yaratiladi — bu, yetkazib beruvchi qarzidan avtomatik ayiriladi.

    SaaS uchun kengaytiriladigan: kelajakda yangi xarajat turi qo'shish uchun,
    shu funksiyaga yangi parametr va extra_costs ro'yxatiga yangi qator
    qo'shish kifoya."""
    from models import InventoryReceipt, ExpenseTransaction

    if not items:
        return {"success": False, "error": "Hech qanday mahsulot kiritilmagan"}

    try:
        # M8/F1: `InventoryReceipt`ning yagona ota-FK si (`supplier_id`)
        # NULL bo'lishi mumkin — ta'minotchisiz kirim. U holda model
        # qo'riqchisi korxonani aniqlay olmaydi, shuning uchun tenant
        # ANIQ beriladi. (Ilgari vaqtinchalik `DEFAULT 1` to'ldirardi.)
        receipt = InventoryReceipt(
            company_id=company_id,
            supplier_id=supplier_id, document_number=document_number,
            transport_cost=transport_cost or 0, tushirish_cost=tushirish_cost or 0,
            yuklash_cost=yuklash_cost or 0, boshqa_cost=boshqa_cost or 0,
            add_to_cost=add_to_cost, notes=notes, created_by=created_by,
            production_type=production_type
        )
        db.add(receipt)
        db.flush()  # receipt.id kerak bo'ladi

        total_extra = float(transport_cost or 0) + float(tushirish_cost or 0) + \
                      float(yuklash_cost or 0) + float(boshqa_cost or 0)

        # Barcha mahsulotlarning BAZA (xomashyoning o'zi) qiymati — proporsional
        # taqsimlash uchun "og'irlik" sifatida ishlatiladi.
        items_total_value = sum(float(it["quantity"]) * float(it["price_per_unit"]) for it in items)

        created_results = []
        purchase_ids = []
        for it in items:
            base_value = float(it["quantity"]) * float(it["price_per_unit"])
            extra_share = 0.0
            if add_to_cost and total_extra > 0 and items_total_value > 0:
                extra_share = total_extra * (base_value / items_total_value)
            extra_per_unit = (extra_share / float(it["quantity"])) if float(it["quantity"]) > 0 else 0.0

            is_opening = bool(it.get("is_opening_stock", False))
            # Boshlang'ich ombor bo'lmasa — HAMMASI, soddalik uchun, to'liq
            # nasiya sifatida yoziladi (pastda, yagona to'lov ayiriladi).
            item_is_credit = (not is_opening) and bool(supplier_id)

            result = _purchase_stock_no_commit(
                db, it["inventory_id"], float(it["quantity"]), float(it["price_per_unit"]),
                purchased_by=created_by, notes=it.get("notes") or notes,
                supplier_id=supplier_id, is_credit=item_is_credit,
                volume_per_unit=it.get("volume_per_unit"),
                payment_due_date=it.get("payment_due_date"),
                is_opening_stock=is_opening,
                extra_cost_per_unit=extra_per_unit,
                company_id=company_id,
            )
            if result is None:
                raise ValueError(f"Material topilmadi (id={it['inventory_id']})")

            result["purchase"].receipt_id = receipt.id
            created_results.append(result)
            purchase_ids.append(result["purchase"].id)

        # 4 ta qo'shimcha xarajat turini, Moliyada ALOHIDA ko'rinishi uchun,
        # ExpenseTransaction sifatida yozamiz (add_to_cost holatidan qat'i
        # nazar — bu, "qancha transportga ketdi" kabi statistik ko'rinish
        # uchun, hisob-kitobga qo'sh marta qo'shilib ketmaydi, chunki
        # get_monthly_report o'zi buni alohida qatorga chiqaradi).
        # MUHIM: agar BUTUN hujjatdagi barcha mahsulotlar "Ombordagi mavjud
        # xomashyo" (boshlang'ich ombor) deb belgilangan bo'lsa — bu haqiqiy
        # xarid/tranzaksiya EMAS, shunchaki mavjud zaxirani tizimga kiritish.
        # Shu sabab, qo'shimcha xarajatlar (Transport/Tushirish/Yuklash/
        # Boshqa) ham — xomashyoning o'zi kabi — Moliyada xarajat sifatida
        # YOZILMAYDI. Agar hujjatda aralash (ba'zisi yangi xarid, ba'zisi
        # boshlang'ich ombor) bo'lsa — xavfsizlik uchun, xarajatlar odatdagidek
        # yoziladi (chunki hujjatning bir qismi haqiqiy xarid hisoblanadi).
        all_opening_stock = all(bool(it.get("is_opening_stock", False)) for it in items)

        cost_categories = [
            ("transport_kirim", transport_cost, "Transport (kirim)"),
            ("tushirish_kirim", tushirish_cost, "Tushirish (Grushchik)"),
            ("yuklash_kirim", yuklash_cost, "Yuklash"),
            ("kirim_boshqa", boshqa_cost, "Boshqa xarajat (kirim)"),
        ]
        if not all_opening_stock:
            for cat, amount, label in cost_categories:
                amount = float(amount or 0)
                if amount <= 0:
                    continue
                # M8/F1: `ExpenseTransaction` tenant ildiz modeli — ota-zanjiri
                # yo'q, shuning uchun `company_id` ANIQ berilishi SHART
                # (ilgari vaqtinchalik `DEFAULT 1` uni to'ldirardi).
                tx = ExpenseTransaction(
                    company_id=company_id,
                    date=receipt.receipt_date, category=cat, amount=amount,
                    notes=f"{label} — Kirim #{receipt.id}" + (f" ({document_number})" if document_number else ""),
                    created_by=created_by, source="inventory_receipt",
                    production_type=production_type
                )
                db.add(tx)

        # Yagona, umumiy to'lov (agar kiritilgan bo'lsa)
        payment_created = None
        if paid_now and float(paid_now) > 0 and supplier_id:
            from models import SupplierPayment
            payment_created = SupplierPayment(
                supplier_id=supplier_id, amount=float(paid_now),
                paid_by=created_by,
                notes=f"Kirim to'lovi — #{receipt.id}" + (f" ({document_number})" if document_number else "")
            )
            db.add(payment_created)

        db.commit()
        db.refresh(receipt)

        return {
            "success": True,
            "receipt_id": receipt.id,
            "purchase_ids": purchase_ids,
            "items_total_value": round(items_total_value),
            "total_extra_cost": round(total_extra),
            "add_to_cost": add_to_cost,
            "paid_now": float(paid_now or 0),
            "results": [{"item_id": r["item"].id, "item_name": r["item"].item_name,
                         "old_price": r["old_price"], "new_price": r["new_price"]} for r in created_results]
        }
    except Exception:
        db.rollback()
        raise


def update_item(db: Session, item_id: int, item_data: InventoryUpdate) -> Optional[Inventory]:
    """Xomashyo ma'lumotlarini yangilaydi."""
    db_item = get_item(db, item_id)
    if not db_item:
        return None
    update_data = item_data.model_dump(exclude_unset=True)
    # 14-band: qat'iy tekshiruv — HECH NARSA yozilmasdan OLDIN (ValueError → 400).
    update_data = _clean_update("Inventory", update_data)
    # Asosiy penoplast "penoplast emas" deb belgilansa, `default_id`
    # penoplast bo'lmagan materialga ishora qilib qoladi.
    if update_data.get("is_penoplast") is False and db_item.is_default_penoplast:
        raise ValueError("Asosiy penoplastni oddiy materialga aylantirib bo'lmaydi — "
                         "avval boshqa penoplastni asosiy qiling")
    for field, value in update_data.items():
        setattr(db_item, field, value)
    db.commit()
    db.refresh(db_item)
    return db_item


def delete_item(db: Session, item_id: int) -> dict:
    """Xomashyoni o'chiradi.
    Agar bu xomashyo biror buyurtma/harakat/xarid tarixida ISHLATILGAN bo'lsa —
    bazadan butunlay o'chirib bo'lmaydi (eski hisobotlar buziladi). Shunday holatda
    XAVFSIZ tarzda 'yumshoq o'chirish' qilinadi — Omborxona ro'yxatidan yo'qoladi,
    lekin eski buyurtmalarda ko'rinishda davom etadi."""
    from sqlalchemy.exc import IntegrityError, ProgrammingError

    db_item = get_item(db, item_id)
    if not db_item:
        return {"success": False, "message": "Xomashyo topilmadi"}

    # kech37 (18-band, K37-1 — O'LCHANGAN, asl kod): asosiy penoplast bemalol
    # o'chirilardi (200). Keyin korxonada "★ Asosiy" belgili penoplast qolmasdi,
    # `/api/penoplasts` `default_id` esa tasodifiy qolgan penoplastga tushardi; PG da
    # (tarixi bor → YASHIRILADI) yashirin qator `is_default_penoplast = True` ni
    # saqlagani uchun keyin yaratilgan penoplast ham asosiy bo'lmasdi. Endi
    # `update_item` / `add_item` dagi qoida bilan bir xil: boshqa ko'rinadigan
    # penoplast bo'lsa — rad ("avval boshqa penoplastni asosiy qiling"); yagona
    # penoplast bo'lsa — o'chiriladi / yashiriladi va belgisi olib tashlanadi
    # (keyingi yangi penoplast avtomatik asosiy bo'ladi).
    if db_item.is_default_penoplast:
        _boshqa_peno = db.query(Inventory).filter(
            Inventory.company_id == db_item.company_id,
            Inventory.id != db_item.id,
            Inventory.is_penoplast == True,
            Inventory.is_deleted.isnot(True)
        ).first()
        if _boshqa_peno:
            raise ValueError("Asosiy penoplastni o'chirib bo'lmaydi — avval boshqa penoplastni "
                             "asosiy qiling (\"☆ Asosiy qilish\" tugmasi)")

    try:
        db.delete(db_item)
        db.commit()
        return {"success": True, "soft": False, "message": "Xomashyo butunlay o'chirildi"}
    except (IntegrityError, ProgrammingError):
        db.rollback()
        db_item = get_item(db, item_id)
        db_item.is_deleted = True
        # kech37 (18-band): yashirilgan qator asosiy penoplast bo'lib QOLMAYDI
        db_item.is_default_penoplast = False
        db.commit()
        return {
            "success": True, "soft": True,
            "message": "Bu xomashyo eski buyurtma/harakatlarda ishlatilgan — butunlay o'chirib bo'lmadi. "
                       "Shuning uchun ro'yxatdan YASHIRILDI (eski hisobotlar buzilmasligi uchun)."
        }


def get_low_stock_items(db: Session, company_id: int = None) -> List[Inventory]:
    """Qoldiq min_stock dan kam bo'lgan xomashyolar (ogohlantirish).

    MUHIM: "Tayyor loy (...)" yozuvlari — bu, sotib olinadigan xomashyo
    EMAS, balki buyurtmalardan ORTGAN, avtomatik yaratiladigan zaxira
    (get_or_create_loy_stock orqali). U, tabiiy ravishda, to'liq
    ishlatilib, aniq "0"ga tushishi — kutilgan, normal holat (xarid
    qilish kerak degani EMAS). Shuning uchun, bu turkum, "kam qoldi"
    ogohlantirishidan chiqarib tashlanadi — ombordagi haqiqiy miqdorning
    o'ziga (va keyingi buyurtmalar uchun ishlatilishiga) bu SIRA tegmaydi.
    """
    # 2026-09-22 (kech34, K34-1): yashirilgan (o'chirilgan) material Telegram
    # "kam qoldi" xabarlariga (qo'lda ogohlantirish, kunlik cron, buyurtma va
    # ishlab chiqarishdan keyingi ogohlantirish) tushmaydi.
    q = db.query(Inventory).filter(
        Inventory.is_deleted.isnot(True),
        Inventory.stock_quantity <= Inventory.min_stock,
        ~Inventory.item_name.like('Tayyor loy (%')
    )
    # 2026-09-21: QAT'IY filtr — korxona noma'lum (None) bo'lsa bo'sh ro'yxat
    # (`company_id IS NULL` hech narsa topmaydi). Ilgari shartli edi: None da
    # BARCHA korxonalarning kam qolgan xomashyosi qaytib, Telegram xabariga
    # aralashib ketardi (4 marshrut korxonasiz chaqirardi).
    q = q.filter(Inventory.company_id == company_id)
    return q.all()


# ============================================================
# RECIPE CRUD
# ============================================================

from models import Recipe, RecipeIngredient
from schemas import RecipeCreate


def get_recipe_insights(db: Session, recipe_id: int) -> Dict:
    """Retsept uchun qo'shimcha ma'lumot — faqat ko'rsatish uchun, hech narsani o'zgartirmaydi.
    - cost_per_kg: 1 kg tayyor aralashma tannarxi (ombordagi joriy narxlar bo'yicha)
    - used_in: shu retseptni ishlatgan buyurtma detallari (nomi bo'yicha noyob)
    """
    from models import Recipe, Inventory, OrderItem, Order

    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        return {"cost_per_kg": 0, "used_in": []}

    total_cost = 0.0
    for ing in recipe.ingredients:
        if not ing.quantity_kg or ing.quantity_kg <= 0:
            continue
        if ing.inventory and ing.inventory.price_per_unit:
            total_cost += float(ing.quantity_kg) * float(ing.inventory.price_per_unit)

    batch = float(recipe.batch_size_kg or 1)
    cost_per_kg = total_cost / batch if batch > 0 else 0

    items = db.query(OrderItem.name).join(Order, OrderItem.order_id == Order.id).filter(
        OrderItem.recipe_id == recipe_id
    ).distinct().limit(12).all()
    used_in = [i[0] for i in items]

    return {"cost_per_kg": round(cost_per_kg, 2), "used_in": used_in}


def _require_inventory_of_company(db: Session, inventory_ids, company_id: int) -> None:
    """2026-09-21 (12-sizish) — berilgan materiallarning HAMMASI shu
    korxonaniki ekanini QAT'IY tekshiradi, aks holda 404.

    Nima uchun 404 (409 emas): begona korxona materiali \"mavjud emas\" deb
    ko'rinishi kerak — 409 uning borligini oshkor qilardi (oracle)."""
    from fastapi import HTTPException
    ids = {int(i) for i in inventory_ids if i}
    if not ids:
        return
    topildi = {r[0] for r in db.query(Inventory.id).filter(
        Inventory.id.in_(ids), Inventory.company_id == company_id).all()}
    yoq = sorted(ids - topildi)
    if yoq:
        raise HTTPException(status_code=404,
                            detail=f"Material topilmadi (ID {yoq[0]})")


def create_recipe(db: Session, recipe_data: RecipeCreate, company_id: int = None) -> Recipe:
    """Yangi retsept qo'shadi. Nomi ISTALGAN bo'lishi mumkin,
    tarkibi Omborxonadagi istalgan materiallardan (ingredients ro'yxati) tuziladi.

    2026-09-18 — M8/F1a: `company_id` berilmasdi (vaqtinchalik `DEFAULT 1`
    ga tayanardi). Endi tenant ANIQ beriladi. Tarkib (`RecipeIngredient`)
    esa avvalgidek retsept orqali `_TENANT_RULES` bilan to'ldiriladi."""
    # 2026-09-21 (12-sizish): tarkibdagi HAR bir material shu korxonaniki
    # bo'lishi SHART — hech narsa yozilishidan OLDIN tekshiriladi.
    if company_id is not None:
        _require_inventory_of_company(
            db, [ing.inventory_id for ing in recipe_data.ingredients], company_id)
    db_recipe = Recipe(
        company_id=company_id,
        name=recipe_data.name.strip(),
        batch_size_kg=recipe_data.batch_size_kg,
        notes=recipe_data.notes
    )
    db.add(db_recipe)
    db.flush()

    for ing in recipe_data.ingredients:
        db.add(RecipeIngredient(
            recipe_id=db_recipe.id,
            inventory_id=ing.inventory_id,
            quantity_kg=ing.quantity_kg
        ))

    db.commit()
    db.refresh(db_recipe)
    return db_recipe


def update_recipe(db: Session, recipe_id: int, recipe_data: RecipeCreate,
                  company_id: int = None) -> Optional[Recipe]:
    """Mavjud retseptni tahrirlaydi — nomi, hajmi va BUTUN tarkibini
    (eski ingredientlar o'chirilib, yangilari yoziladi) yangilaydi.

    2026-09-21 (12-sizish): `company_id` berilsa retsept FAQAT shu
    korxonadan. Tarkibdagi materiallar esa HAR DOIM retseptning O'Z
    korxonasiga tekshiriladi (berilmasa ham) — eski tarkib o'chirilishidan
    OLDIN, aks holda yarim-o'zgargan retsept qolardi."""
    db_recipe = get_recipe(db, recipe_id, company_id)
    if not db_recipe:
        return None
    if db_recipe.company_id is not None:
        _require_inventory_of_company(
            db, [ing.inventory_id for ing in recipe_data.ingredients],
            db_recipe.company_id)

    db_recipe.name = recipe_data.name.strip()
    db_recipe.batch_size_kg = recipe_data.batch_size_kg
    db_recipe.notes = recipe_data.notes
    db_recipe.updated_at = datetime.utcnow()

    # Eski tarkibni butunlay almashtiramiz
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    for ing in recipe_data.ingredients:
        db.add(RecipeIngredient(
            recipe_id=recipe_id,
            inventory_id=ing.inventory_id,
            quantity_kg=ing.quantity_kg
        ))

    db.commit()
    db.refresh(db_recipe)
    return db_recipe


def get_recipes(db: Session, company_id: int = None) -> List[Recipe]:
    """Barcha retseptlarni qaytaradi."""
    q = db.query(Recipe)
    if company_id is not None:
        q = q.filter(Recipe.company_id == company_id)
    return q.all()


def get_recipe(db: Session, recipe_id: int, company_id: int = None) -> Optional[Recipe]:
    """ID bo'yicha bitta retseptni qaytaradi."""
    q = db.query(Recipe).filter(Recipe.id == recipe_id)
    if company_id is not None:
        q = q.filter(Recipe.company_id == company_id)
    return q.first()


# ============================================================
# PROJECT CRUD
# ============================================================

from models import Project, Order, OrderItem, OrderItemSubDetail, ProjectStatus, OrderStatus, OrderType, FinishedProduct, StockSource, OrderGipsAdditive
from schemas import ProjectCreate, OrderCreate


def create_project(db: Session, project_data: ProjectCreate, company_id: int = None) -> Project:
    """Yangi loyiha qo'shadi.

    2026-09-18 — M8/F1a: `company_id` berilmasdi (vaqtinchalik `DEFAULT 1`
    ga tayanardi) — B korxonaning loyihasi A ga yozilardi. Endi tenant
    ANIQ beriladi. Loyiha raqami (`PRJ-NNN`) hisoblash mantig'i
    O'ZGARTIRILMADI."""
    # 2026-09-20 — raqam endi KORXONA BO'YICHA ketma-ket.
    #
    # Ilgari: `last.id + 1`, ya'ni `projects` jadvalining GLOBAL id
    # ketma-ketligi. Ikkinchi mijozning birinchi loyihasi `PRJ-023`
    # bo'lib chiqardi — u sizda yana 22 ta boshqa loyiha borligini
    # payqardi. Endi har bir korxona o'zining `PRJ-001` idan boshlaydi.
    #
    # Baza buni allaqachon qo'llab-quvvatlaydi: W2b da `project_number`
    # global noyoblikdan `UNIQUE(company_id, project_number)` ga
    # o'tkazilgan, ya'ni ikki korxonada bir xil raqam bemalol yashaydi.
    #
    # MAVJUD ma'lumotga ta'sir qilmaydi: 1-korxonada eng katta raqam
    # nechada bo'lsa, keyingisi o'shandan davom etadi.
    # 15-band: qat'iy tekshiruv — HECH NARSA yozilmasdan OLDIN (ValueError → 400).
    _toza_pr = _clean_create("Project", project_data.model_dump(exclude_unset=True))
    import re as _re_pn
    _pq = db.query(Project.project_number)
    if company_id is not None:
        _pq = _pq.filter(Project.company_id == company_id)
    _raqamlar = []
    for (_pn,) in _pq.all():
        _m = _re_pn.search(r"(\d+)", _pn or "")
        if _m:
            _raqamlar.append(int(_m.group(1)))
    next_num = (max(_raqamlar) + 1) if _raqamlar else 1

    # Agar shu raqam SHU KORXONADA band bo'lsa, keyingisini olamiz
    def _band(n):
        q = db.query(Project).filter(Project.project_number == f"PRJ-{n:03d}")
        if company_id is not None:
            q = q.filter(Project.company_id == company_id)
        return q.first() is not None

    while _band(next_num):
        next_num += 1
    project_number = f"PRJ-{next_num:03d}"

    db_project = Project(
        company_id=company_id,
        project_number=project_number,
        project_name=project_data.project_name,
        client_name=project_data.client_name,
        client_phone=project_data.client_phone,
        client_address=project_data.client_address,
        description=project_data.description,
        total_budget=project_data.total_budget or 0,
        # 15-band (O'LCHANGAN): yaratish formasidagi "Muddati" sxemada yo'q
        # edi va JIMGINA tashlab yuborilardi — hech bir yo'l uni yozmasdi.
        deadline=_toza_pr.get("deadline"),
        notes=project_data.notes,
        status=ProjectStatus.ACTIVE
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


def get_projects(db: Session, company_id: int = None) -> List[Project]:
    q = db.query(Project).filter(Project.is_deleted.isnot(True))
    if company_id is not None:
        q = q.filter(Project.company_id == company_id)
    return q.order_by(Project.start_date.desc()).all()


def get_projects_dashboard_stats(db: Session, company_id: int = None) -> dict:
    """Loyihalar sahifasi uchun KPI ko'rsatkichlari — faqat o'qish, mavjud hisob-kitoblarga
    (get_projects_with_stats, calculate_order_profit) tegmaydi, faqat ulardan foydalanadi."""
    import services
    from models import Order, OrderStatus
    from datetime import datetime

    _dq = db.query(Project).filter(Project.is_deleted.isnot(True))
    if company_id is not None:
        _dq = _dq.filter(Project.company_id == company_id)
    projects = _dq.all()
    now = datetime.utcnow()

    active = sum(1 for p in projects if p.status == ProjectStatus.ACTIVE)
    completed = sum(1 for p in projects if p.status == ProjectStatus.COMPLETED)
    on_hold = sum(1 for p in projects if p.status == ProjectStatus.ON_HOLD)
    started_this_month = sum(1 for p in projects if p.start_date and p.start_date.year == now.year and p.start_date.month == now.month)
    completed_this_month = sum(1 for p in projects if p.completed_at and p.completed_at.year == now.year and p.completed_at.month == now.month)

    total_profit = 0.0
    for p in projects:
        for o in (p.orders or []):
            if o.status == OrderStatus.READY:
                try:
                    total_profit += float(services.calculate_order_profit(db, o.id).get("foyda", 0))
                except Exception as e:
                    db.rollback()
                    try:
                        log_error(db, str(e), endpoint=f"get_projects_dashboard_stats:calculate_order_profit order#{o.id}")
                    except Exception:
                        pass

    return {
        "active": active,
        "completed": completed,
        "on_hold": on_hold,
        "started_this_month": started_this_month,
        "completed_this_month": completed_this_month,
        "total_profit": round(total_profit),
    }


def get_projects_with_stats(db: Session, company_id: int = None) -> List:
    """Loyihalar + buyurtmalar summasi + qarz hisobi (orders ham qo'shilgan)."""
    _pq = db.query(Project).filter(Project.is_deleted.isnot(True))
    if company_id is not None:
        _pq = _pq.filter(Project.company_id == company_id)
    projects = _pq.order_by(Project.start_date.desc()).all()
    for p in projects:
        orders_count = len(p.orders) if p.orders else 0
        orders_sum = sum(float(o.total_amount or 0) for o in (p.orders or []))
        budget = float(p.total_budget or 0)
        paid = float(p.total_paid or 0)
        actual = budget if budget > 0 else orders_sum
        debt = actual - paid

        # Atributlar qo'shamiz (template uchun)
        p.orders_count = orders_count
        p.orders_sum = orders_sum
        p.debt = debt
        p.actual_sum = actual
    return projects


def _loyiha_tolangan_yangila(db: Session, project) -> None:
    """17c (2026-09-21): `Project.total_paid` ni HAQIQIY to'lovlardan qayta
    hisoblaydi — loyiha buyurtmalaridagi BARCHA `Payment` yozuvlari
    yig'indisi (qaytarilgan pulning manfiy yozuvi ham, yumshoq o'chirilgan
    buyurtmaning to'lovlari ham — ular bazada qoladi va ilgari ham shu
    formula bilan hisoblanardi).

    NIMA UCHUN (O'LCHANGAN, `work/probe17c.py` va jonli sayt):
      * `total_paid` ni faqat `create_payment` / `delete_payment`
        yangilardi. Yuk xati orqali to'lov (`create_delivery`), pul
        qaytarish (`mark_refunded`) va buyurtmani butunlay o'chirish (unga
        bog'liq to'lovlar ham o'chadi) uni YANGILAMASDI. Jonli: PRJ-033
        buyurtmasi to'liq to'langan (2 560 000), loyiha esa "To'langan: 0".
      * Loyihaga to'g'ridan-to'g'ri "zaklat" (`add_payment`) to'lov
        YOZUVISIZ `total_paid` ga qo'shilardi va keyingi buyurtma to'lovida
        izsiz o'chib ketardi. Foydalanuvchi qarori "1" (2026-09-21):
        bu yo'l OLIB TASHLANDI, to'lov faqat buyurtma orqali.
    Endi `total_paid` — to'lovlar keshi, va uni o'zgartiradigan HAR BIR
    yo'l shu yordamchini chaqiradi.

    TENANT: yig'indi loyiha korxonasi bo'yicha QAT'IY cheklanadi (ota —
    buyurtma — orqali; `Payment` da `company_id` yo'q). Sessiya
    `autoflush=False` — shuning uchun avval `flush`.
    Commit QILMAYDI — chaqiruvchining tranzaksiyasi ichida ishlaydi."""
    if project is None:
        return
    from models import Payment as _Pay_lt
    from sqlalchemy import func as _func_lt
    db.flush()
    jami = db.query(_func_lt.coalesce(_func_lt.sum(_Pay_lt.amount), 0)).join(
        Order, Order.id == _Pay_lt.order_id).filter(
        Order.project_id == project.id,
        Order.company_id == project.company_id).scalar()
    project.total_paid = round(float(jami or 0), 2)


# ============================================================
# ORDER CRUD
# ============================================================

def create_order(db: Session, order_data: OrderCreate, performed_by: str = None,
                 company_id: int = None) -> Order:
    """Yangi buyurtma + detallar qo'shadi.

    Mantiq:
    - is_coated=True bo'lsa, narx 2 barobar qilinadi (qoplama qo'shimcha xizmat)
    - Har bir item ning total_price = quantity * unit_price (qoplamali bo'lsa x2)
    - Buyurtma umumiy summasi avtomatik hisoblanadi
    """
    # Order raqami: ORD-{project_id}-{seq}
    # Bir necha kishi AYNAN BIR VAQTDA shu loyihaga buyurtma yaratsa,
    # ikkalasi bir xil raqamni olib qolishi mumkin — shu holatni xavfsiz
    # tarzda avtomatik qayta urinib, o'zi tuzatib qo'yadi.
    from sqlalchemy.exc import IntegrityError

    # 2026-09-21 — TENANT (11-sizish). Buyurtmaning korxonasi LOYIHADAN
    # olinadi (pastda `_company_id = _project.company_id`). Chaqiruvchi
    # korxonasi berilsa, loyiha AYNAN shu korxonaniki bo'lishi shart —
    # aks holda B A ning `project_id` sini yuborib, buyurtmani A
    # korxonasida yaratar va A omboridan xomashyo ayirar edi (qo'riqchi
    # ushlamasdi: buyurtma, detal, penoplast — hammasi "A niki").
    # MUHIM: bu tekshiruv takroriy-yuborish himoyasidan va advisory
    # qulfdan OLDIN turadi — aks holda B ga A ning yaqinda yaratilgan
    # buyurtmasi (narxlari bilan) "dublikat" sifatida qaytib ketardi.
    if company_id is not None:
        if not db.query(Project.id).filter(
                Project.id == order_data.project_id,
                Project.company_id == company_id).first():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Loyiha topilmadi")

    # 17d (2026-09-21): rejalashtirilgan loy (kg) — HECH NARSA yozilishidan
    # OLDIN tekshiriladi. O'LCHANGAN: `loy_kg: Infinity` → loy xomashyosi
    # qoldig'i −∞, `1e20` → −5×10¹⁹, `true` → 1 kg. Sxema (pydantic) ham
    # rad etadi — bu ildiz to'sig'i sxemani chetlab chaqirilganda ishlaydi.
    _json_loy("loy_kg", getattr(order_data, 'loy_kg', None))

    # 2026-09-17 (audit topilmasi — haqiqiy, nozik xato): pastdagi
    # "so'nggi soniyalarda bir xil buyurtma bormi" tekshiruvi o'zi
    # ATOMIK EMAS edi — ikkita so'rov AYNAN BIR VAQTDA kelsa (masalan
    # tarmoq ikki marta jo'natib yuborsa), ikkalasi ham "yo'q" javobini
    # olib, ikkalasi ham YANGI, DUBLIKAT buyurtma yaratib qo'yishi
    # mumkin edi (4 ta bir vaqtdagi so'rovdan 2 tasi shunday dublikat
    # bo'lib qolgani sinovda aniq ko'rsatildi). Yechim: shu loyiha
    # uchun bir vaqtning o'zida faqat BITTA buyurtma yaratish jarayoni
    # davom etishini ta'minlaydigan, tranzaksiya davomida ushlab
    # turiladigan qulf (faqat PostgreSQL'da; mahalliy sinov uchun
    # ishlatiladigan SQLite'da bunday funksiya yo'q, shuning uchun
    # xavfsiz tarzda o'tkazib yuboriladi — u yerda haqiqiy bir vaqtlilik
    # muammosi ham yo'q).
    try:
        if db.bind.dialect.name == "postgresql":
            from sqlalchemy import text
            db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": order_data.project_id})
    except Exception:
        pass

    # QO'SHIMCHA XAVFSIZLIK QATLAMI (server tomonida): brauzerda tugmani
    # ikki marta bosishdan himoya allaqachon bor, lekin bu — faqat
    # ekranda, va sekin internet/tarmoq takrorlashi kabi holatlarda
    # yetarli bo'lmasligi mumkin. Shuning uchun bu yerda ham tekshiramiz:
    # agar shu loyihaga, so'nggi bir necha soniya ichida, XUDDI SHUNDAY
    # tarkibli (bir xil nomdagi/turdagi/miqdordagi detallar) buyurtma
    # ALLAQACHON yaratilgan bo'lsa — bu, deyarli aniq, tasodifan ikki
    # marta yuborilgan SO'ROV. Yangisini yaratish o'rniga, mavjudining
    # o'zini qaytaramiz.
    from datetime import timedelta as _td_dup
    _recent_cutoff = datetime.utcnow() - _td_dup(seconds=8)
    _recent_order = db.query(Order).filter(
        Order.project_id == order_data.project_id,
        Order.created_at >= _recent_cutoff
    ).order_by(Order.created_at.desc()).first()
    if _recent_order:
        _new_sig = sorted([(i.name, i.category, round(float(i.quantity or 0), 4)) for i in order_data.items])
        _old_sig = sorted([(it.name, it.category, round(float(it.quantity or 0), 4)) for it in _recent_order.items])
        if _new_sig and _new_sig == _old_sig:
            _recent_order._is_duplicate_submit = True  # main.py shu belgini tekshirib, qayta ombor yechishning oldini oladi
            return _recent_order

    # OrderType ni aniqlash
    order_type = OrderType.PRODUCT if order_data.order_type == "product" else OrderType.SERVICE

    is_draft = getattr(order_data, 'is_draft', False)

    # 2026-09-18 — SaaS ko'p-tenantlilik (3-to'lqin).
    # Buyurtma QAYSI KORXONANIKI ekani o'z loyihasidan olinadi.
    # NIMA UCHUN ANIQ YOZILADI: bazada company_id ustunida vaqtinchalik
    # DEFAULT 1 turibdi. Agar bu yerda qiymat berilmasa, 2-korxonaning
    # loyihasiga yaratilgan buyurtma ham JIMGINA 1-korxonaga tushib qoladi
    # — jonli sinovda aynan shunday bo'ldi. Bitta korxona bo'lganda bu
    # sezilmaydi, ikkinchi mijoz qo'shilganda esa boshqa korxonaning
    # ma'lumoti aralashib ketadi.
    _project = db.query(Project).filter(Project.id == order_data.project_id).first()
    if not _project:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    _company_id = _project.company_id

    # 2026-09-20 — buyurtma raqamidagi prefiks endi GLOBAL `project_id`
    # emas.
    #
    # Ilgari: `ORD-{project_id:03d}-{seq}`. `project_id` butun platforma
    # bo'yicha ketma-ket bo'lgani uchun, ikkinchi mijozning birinchi
    # buyurtmasi `ORD-023-1` bo'lib chiqardi — loyiha raqamini korxona
    # bo'yicha qilganimiz ham buni tuzatmasdi, chunki bu yerda loyihaning
    # RAQAMI emas, ichki `id` si ishlatilardi.
    #
    # Yangi qoida, uch bosqichli (eski hujjatlarga TEGMASLIK uchun):
    #   1) Loyihada allaqachon buyurtma bo'lsa — o'shalarning prefiksi
    #      aynan davom ettiriladi. Ya'ni mavjud loyihalarning yangi
    #      buyurtmalari ilgarigidek raqamlanadi, uzilish bo'lmaydi.
    #   2) Buyurtma yo'q bo'lsa — loyihaning O'Z raqamidan olinadi
    #      (`PRJ-007` -> `ORD-007-1`), bu hujjatda ko'rinadigan raqam.
    #   3) Ikkalasi ham bo'lmasa — eski usul, `project_id`.
    import re as _re_on
    _mavjud = db.query(Order.order_number).filter(
        Order.project_id == order_data.project_id
    ).order_by(Order.id.asc()).first()

    _prefiks = None
    if _mavjud and _mavjud[0]:
        _m = _re_on.match(r"ORD-(\d+)-", _mavjud[0])
        if _m:
            _prefiks = _m.group(1)
    if _prefiks is None and getattr(_project, "project_number", None):
        _m = _re_on.search(r"(\d+)", _project.project_number)
        if _m:
            _prefiks = f"{int(_m.group(1)):03d}"
    if _prefiks is None:
        _prefiks = f"{order_data.project_id:03d}"

    db_order = None
    max_attempts = 5
    for attempt in range(max_attempts):
        seq = db.query(Order).filter(Order.project_id == order_data.project_id).count() + 1 + attempt
        order_number = f"ORD-{_prefiks}-{seq}"
        db_order = Order(
            company_id=_company_id,
            order_number=order_number,
            project_id=order_data.project_id,
            order_type=order_type,
            status=OrderStatus.DRAFT if is_draft else OrderStatus.IN_PROGRESS,
            master_id=order_data.master_id,
            deadline=getattr(order_data, 'deadline', None),
            notes=order_data.notes,
            total_amount=0
        )
        db.add(db_order)
        try:
            db.flush()  # ID olish uchun
            break  # Muvaffaqiyatli — raqam band emas edi
        except IntegrityError:
            db.rollback()
            if attempt == max_attempts - 1:
                raise  # 5 marta urinib bo'lmasa, haqiqiy xato bor demak

    # Detallarni qo'shamiz va umumiy summani hisoblaymiz
    total_amount = 0
    for item_data in order_data.items:
        # unit_price allaqachon frontend tomonida YAKUNIY (qoplamali bo'lsa
        # allaqachon ×2 qilingan) holda yuboriladi — bu barcha turlar
        # (profil/panel/dona/blok) uchun bir xil, izchil qoida.
        # MUHIM TUZATISH (2026-09 audit): oldin bu yerda "dona" turi uchun
        # yana QO'SHIMCHA ×2 qilinardi — chunki bu kod "dona"ning frontendi
        # xom (qoplamasiz) narx yuboradi deb noto'g'ri faraz qilgan edi.
        # Aslida frontend "dona" uchun ham (Blok/Profil kabi) ALLAQACHON
        # yakuniy, qoplamali narxni yuboradi (shu jumladan "hajmni qulflab"
        # rejimida ham) — natijada qoplamali Donali detallar narxi REAL
        # buyurtmalarda 2 baravar ORTIQCHA yozilib kelgan (jonli test bilan
        # tasdiqlangan: 1000 so'm/dona yuborilsa, 2000 so'm/dona saqlanardi).
        # Endi — boshqa barcha turlar kabi, unit_price O'ZGARTIRILMASDAN
        # ishlatiladi.
        _stored_unit_price = item_data.unit_price
        item_total = _stored_unit_price * item_data.quantity
        total_amount += item_total

        db_item = OrderItem(
            order_id=db_order.id,
            name=item_data.name,
            category=item_data.category,
            width=item_data.width,
            thickness=item_data.thickness,
            length=item_data.length,
            quantity=item_data.quantity,
            is_coated=item_data.is_coated,
            recipe_id=(getattr(item_data, 'recipe_id', None) or order_data.recipe_id),
            penoplast_id=getattr(item_data, 'penoplast_id', None),
            price_per_m3=getattr(item_data, 'price_per_m3', None),
            finished_product_id=getattr(item_data, 'finished_product_id', None),
            unit_price=_stored_unit_price,
            unit_price_for_volume=getattr(item_data, 'unit_price_for_volume', None),
            product_type_id=getattr(item_data, 'product_type_id', None),
            total_price=item_total,
            notes=item_data.notes
        )
        db.add(db_item)

        # Ichki qo'shimcha detallar (masalan karniz ichidagi rebristo
        # qism) — faqat Profil turidagi detallarda bo'ladi. Alohida
        # ombor zaxirasi yo'q: hajmi shu OrderItem'ning o'z hajmiga
        # _item_volume_m3() ichida avtomatik qo'shiladi (parent bilan
        # bir xil penoplast_id/price_per_m3 orqali). Narxi — frontend
        # tomonidan ALLAQACHON parent unit_price'ga qo'shib yuborilgan
        # (Yuk xatida alohida qator chiqmasin uchun); bu yerda faqat
        # audit/qayta-tahrirlash uchun saqlanadi.
        import services as _svc_create
        _sub_base_price = float(getattr(item_data, 'price_per_m3', None) or order_data.base_price or 0)
        for sub_data in (getattr(item_data, 'sub_details', None) or []):
            sub_vol, sub_price = _svc_create._calc_dim_volume_price(
                sub_data.category, sub_data.width, sub_data.thickness,
                sub_data.length, sub_data.quantity, _sub_base_price, sub_data.is_coated
            )
            db_item.sub_details.append(OrderItemSubDetail(
                name=sub_data.name,
                category=sub_data.category,
                width=sub_data.width,
                thickness=sub_data.thickness,
                length=sub_data.length,
                quantity=sub_data.quantity,
                is_coated=sub_data.is_coated,
                volume_m3=sub_vol,
                total_price=sub_price
            ))


    db_order.total_amount = total_amount
    # Kelishilgan summa — boshida jami summaga teng (chegirmasiz)
    db_order.agreed_amount = getattr(order_data, 'agreed_amount', None) or total_amount
    db_order.base_price = getattr(order_data, 'base_price', None)
    if total_amount > 0 and float(db_order.agreed_amount) < total_amount:
        db_order.discount_percent = round((total_amount - float(db_order.agreed_amount)) / total_amount * 100, 2)

    db.flush()

    # "Loy miqdori" (Reja) — HAR DOIM saqlanadi (qoralama bo'lsa ham),
    # chunki keyinroq "Jarayonga olish" bosilganda shu qiymat kerak bo'ladi.
    import services as _services
    _planned_loy_direct = float(getattr(order_data, 'loy_kg', None) or 0)
    _services._set_planned_loy(db_order, _planned_loy_direct)

    # kech58 (K58-1 / K58-2): buyurtma UMUMIY loyi retsepti — yaratishda BIR MARTA belgilanadi
    # (qoralama ham). Yechish / qaytarish / foyda / brak — hammasi shu retseptdan.
    db.expire(db_order, ['items'])
    _qr58 = _services.buyurtma_qoplama_retseptini_tanla(db, db_order)
    db_order.qoplama_retsept_id = _qr58.id if _qr58 else None

    # Tayyor mahsulotlardan yechamiz (qoralama bo'lmasa)
    if not is_draft:
        _take_finished_for_order(db, db_order)

        # "Loy sotish" detallari — har biri o'z retseptiga ko'ra, alohida
        # ombordan yechiladi (buyurtma to'g'ridan-to'g'ri, qoralamasiz
        # yaratilganda ham ishlashi kerak — avval bu yerda YO'Q edi)
        for item in db_order.items:
            if (item.category or '').lower() == 'loy_sotish':
                if item.recipe_id and item.quantity:
                    _services.deduct_loy_ingredients(db, db_order, float(item.quantity), recipe_id=item.recipe_id)
                elif item.quantity:
                    # MUHIM: retsept tanlanmagan "Loy sotish" detali —
                    # xomashyo AYIRILMAYDI. Frontend endi buni oldindan
                    # tekshiradi, lekin API to'g'ridan-to'g'ri chaqirilsa ham
                    # (masalan SaaS mijozi tomonidan) — bu holat KUZATILISHI
                    # kerak, shuning uchun xato jurnaliga yozamiz.
                    try:
                        log_error(db, f"Loy sotish detali (#{item.id}, {item.name}) — retsept tanlanmagan, xomashyo ayirilmadi!",
                                  endpoint="create_order:loy_sotish_missing_recipe")
                    except Exception:
                        pass

        # UMUMIY QOPLAMA uchun Rejalashtirilgan Loy — MUHIM: bu ham avval
        # BUTUNLAY YO'Q edi (faqat qoralama faollashtirish va tiklashda bor
        # edi). To'g'ridan-to'g'ri yaratilgan buyurtmada, umumiy qoplama
        # uchun xomashyo HECH QACHON ayirilmasdi.
        _planned_loy_general = _planned_loy_direct
        if _planned_loy_general > 0:
            _services.deduct_loy_ingredients(db, db_order, _planned_loy_general)

    db.commit()
    db.refresh(db_order)

    # AUDIT: buyurtma yaratilgani qayd etiladi — kim, qachon, qancha
    # summaga, nechta detal bilan. Kelajakda "bu buyurtmada nima
    # o'zgargan edi" degan savolga tezda javob topish uchun.
    try:
        log_activity(
            db, "created", "order", db_order.id, db_order.order_number, performed_by,
            new_value=f"Jami: {float(db_order.total_amount or 0):,.0f} so'm, {len(db_order.items)} ta detal".replace(',', ' '),
            company_id=getattr(db_order, 'company_id', None)
        )
    except Exception:
        pass

    return db_order


# ============================================================
# M4 (2026-09-18) — TAYYOR MAHSULOT: TENANT-XAVFSIZ MARKAZIY QIDIRUV
# ============================================================
# Ilgari butun fayl bo'ylab `db.query(FinishedProduct).filter(
# FinishedProduct.id == fp_id)` shaklidagi 17 ta joy bor edi — hammasi
# korxona filtrisiz. Ya'ni A korxona xodimi B korxonaning mahsulot
# ID sini yuborsa, uni ko'rardi, tahrirlardi, sotardi, o'chirardi.
#
# Endi ikkita markaziy funksiya bor:
#   • get_finished_product()  — "topilmasa None" (endpointlar uchun → 404)
#   • _fp_for_tenant()        — "boshqa korxonaniki bo'lsa RAD ET"
#     (buyurtmaga biriktirish/allocation uchun — u yerda jimgina
#      o'tkazib yuborish XAVFLI: miqdor yechilmay, buyurtma esa
#      yaratilib ketardi).
#
# `company_id=None` — filtrsiz, ESKI xatti-harakat. Bu ataylab: ichki
# chaqiruvchilar bosqichma-bosqich o'tkaziladi, hech narsa birdan
# buzilmaydi. Barcha `/api/finished/*` endpointlari company_id ni
# ANIQ uzatadi.

def get_finished_product(db: Session, fp_id: int, company_id: int = None,
                         lock: bool = False):
    """Tayyor mahsulotni FAQAT shu korxona ichidan topadi (M4).

    company_id berilmasa — filtrsiz (orqaga moslik uchun).
    lock=True — `.with_for_update()` bilan qatorni qulflaydi (sotuv,
    brak kabi miqdor o'zgartiradigan amallar uchun)."""
    q = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id)
    if company_id is not None:
        q = q.filter(FinishedProduct.company_id == company_id)
    if lock:
        q = q.with_for_update()
    return q.first()


def _fp_for_tenant(db: Session, fp_id: int, company_id: int = None):
    """Buyurtmaga biriktirish (allocation) uchun QAT'IY qidiruv.

    • Mahsulot umuman yo'q (o'chirilgan) — None qaytaradi, chaqiruvchi
      avvalgidek o'tkazib yuboradi (bu — eski, uzilgan havola).
    • Mahsulot BOR, lekin BOSHQA korxonaniki — TenantMismatchError.
      Bu yerda jimgina `continue` qilish mumkin emas edi: buyurtma
      yaratilaverardi, B korxonaning qoldig'i esa o'qilardi/yechilardi."""
    from models import TenantMismatchError
    fp = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()
    if fp is None:
        return None
    if company_id is not None and fp.company_id != company_id:
        raise TenantMismatchError(
            f"Tayyor mahsulot #{fp_id} boshqa korxonaga tegishli — "
            f"buyurtmaga biriktirib bo'lmaydi."
        )
    return fp


def _fp_item_qty(item) -> float:
    """Detalning tayyor mahsulotdan olinadigan miqdori."""
    cat = (item.category or '').lower()
    if cat == 'profil':
        return float(item.length or 0)
    return float(item.quantity or 0)


def _fp_stable_unit_cost(db, fp) -> float:
    """Tayyor mahsulotning BARQAROR "1 birlik tan narxi"ni qaytaradi.
    unit_volume_m3 (penoplast) va unit_loy_kg (loy) — bular ishlab
    chiqarilganda saqlanadi va HECH QACHON o'zgarmaydi. Shuning uchun
    bulardan hisoblangan tan narx — sotish/qaytarishdan qat'i nazar
    barqaror qoladi (take va return simmetrik bo'ladi).

    M4 (2026-09-18) — TENANT: bu yerdagi BARCHA Inventory qidiruvlari
    endi mahsulotning O'Z korxonasi (`fp.company_id`) bilan cheklangan.
    Ilgari `penoplast_id` faqat id
    bo'yicha olinardi — eski yoki buzilgan yozuvlarda A korxona
    mahsulotining tannarxi B korxonaning material narxidan
    hisoblanishi mumkin edi. Material boshqa korxonaniki bo'lsa, endi
    u umuman topilmaydi va tannarxga QO'SHILMAYDI (noto'g'ri raqam
    berishdan ko'ra, qo'shmaslik xavfsizroq)."""
    # QO'SHILDI 2026-09-20 — MRP mahsuloti uchun barqaror narx ALOHIDA
    # saqlanadi (`unit_cost_stable`), chunki MRP `unit_volume_m3` /
    # `unit_loy_kg` maydonlarini to'ldirmaydi va pastdagi hisob u uchun
    # 0 qaytarardi. Bo'lsa — ENG USTUN manba.
    _ucs = getattr(fp, 'unit_cost_stable', None)
    if _ucs:
        return float(_ucs)

    import services as _svc
    from models import Inventory
    _fp_cid = getattr(fp, 'company_id', None)

    def _inv(inv_id, lock=False):
        """Materialni FAQAT shu mahsulotning korxonasidan oladi."""
        if not inv_id:
            return None
        _q = db.query(Inventory).filter(Inventory.id == inv_id)
        if _fp_cid is not None:
            _q = _q.filter(Inventory.company_id == _fp_cid)
        if lock:
            _q = _q.with_for_update()
        return _q.first()

    unit_vol = float(getattr(fp, 'unit_volume_m3', None) or 0)
    unit_loy = float(getattr(fp, 'unit_loy_kg', None) or 0)
    cost = 0.0
    # Penoplast qismi
    if unit_vol > 0 and fp.penoplast_id:
        p = _inv(fp.penoplast_id)
        if p and p.price_per_unit and p.volume_per_unit:
            narx_per_m3 = float(p.price_per_unit) / float(p.volume_per_unit)
            cost += unit_vol * narx_per_m3
    # Loy qismi
    if unit_loy > 0:
        # 2026-09-21 — TENANT: korxona mahsulotning O'ZIDAN olinadi. Oldin
        # berilmasdi: `fp.recipe_id` bo'sh bo'lsa BOSHQA korxonaning
        # retsepti bo'yicha tan narx hisoblanardi (o'lchangan).
        loy_info = _svc.get_loy_cost_per_kg(
            db, fp.recipe_id, company_id=getattr(fp, 'company_id', None))
        cost += unit_loy * float(loy_info.get("cost_per_kg", 0) or 0)
    return cost


def _take_finished_for_order(db: Session, order, company_id: int = None) -> list:
    """Buyurtmadagi tayyor mahsulot detallarini ombordan yechadi.

    M4 (2026-09-18) — TENANT: mahsulot buyurtmaning O'Z korxonasiga
    tegishli bo'lishi SHART. Boshqa korxonaniki bo'lsa — butun amal
    rad etiladi (TenantMismatchError), chunki bu yerda jimgina
    o'tkazib yuborish A korxonaning buyurtmasi B korxonaning
    qoldig'ini yechishiga olib kelardi."""
    log = []
    cid = company_id if company_id is not None else getattr(order, 'company_id', None)
    for it in order.items:
        fpid = getattr(it, 'finished_product_id', None)
        if not fpid:
            continue
        qty = _fp_item_qty(it)
        if qty <= 0:
            continue
        fp = _fp_for_tenant(db, fpid, cid)
        if not fp:
            continue
        # MUHIM: quantity kamayganda, cost_price ham kamayishi shart. Buni
        # BARQAROR "1 birlik tan narxi"dan hisoblaymiz (unit_volume/unit_loy
        # asosida — bular o'zgarmaydi), shunda take va return simmetrik bo'ladi
        # va qolgan qoldiqning foydasi to'g'ri qoladi.
        old_qty = float(fp.quantity or 0)
        take = min(qty, old_qty)
        unit_cost = _fp_stable_unit_cost(db, fp)
        if unit_cost > 0:
            fp.cost_price = max(0, float(fp.cost_price or 0) - (unit_cost * take))
        elif old_qty > 0 and fp.cost_price:
            # orqaga moslik (unit ma'lumot yo'q bo'lsa)
            fp.cost_price = float(fp.cost_price) - (float(fp.cost_price) / old_qty * take)
        fp.quantity = old_qty - qty
        log.append(f"🏭 {fp.name}: -{qty:g} {fp.unit} (tayyor mahsulotdan)")
    if log:
        db.flush()
    return log


def _return_finished_for_order(db: Session, order, sign: float = 1.0,
                               company_id: int = None) -> list:
    """Buyurtma o'chirilganda tayyor mahsulotlarni qaytaradi.
    sign=-1.0 — buyurtma tiklanganda qayta ombordan yechish uchun.

    MUHIM: hech narsa topshirilmagan bo'lsa — detalning TO'LIQ miqdori
    qaytadi/qayta yechiladi (item.remaining_qty = order_qty_normalized,
    chunki delivered_qty=0). QISMAN topshirilgan bo'lsa — faqat QOLGAN
    (hali mijozga topshirilmagan) qismi qaytadi/qayta yechiladi, chunki
    topshirilgan qismi allaqachon mijozda va ombor hisobiga tegishli emas.
    To'liq YETKAZILGAN buyurtmalar uchun bu funksiya chaqiruvchi tomonidan
    umuman chaqirilmaydi (remaining_qty=0 bo'lardi, farqi yo'q)."""
    log = []
    verb = "qaytarildi" if sign > 0 else "qayta yechildi"
    # M4 (2026-09-18) — TENANT: _take bilan AYNAN bir xil qoida.
    cid = company_id if company_id is not None else getattr(order, 'company_id', None)
    for it in order.items:
        fpid = getattr(it, 'finished_product_id', None)
        if not fpid:
            continue
        qty = it.remaining_qty
        if qty <= 0:
            continue
        fp = _fp_for_tenant(db, fpid, cid)
        if not fp:
            continue
        delta = qty * sign
        # cost_price BARQAROR birlik tan narxidan to'g'rilanadi — _take bilan
        # AYNAN SIMMETRIK (unit_volume/unit_loy asosida, o'zgarmas). Shuning
        # uchun olish→qaytarish siklida cost_price aniq asl holiga qaytadi va
        # foyda sun'iy ko'tarilib/tushib ketmaydi.
        cur_qty = float(fp.quantity or 0)
        unit_cost = _fp_stable_unit_cost(db, fp)
        if unit_cost > 0:
            fp.cost_price = max(0, float(fp.cost_price or 0) + (unit_cost * delta))
        elif cur_qty > 0 and fp.cost_price:
            fp.cost_price = float(fp.cost_price) + (float(fp.cost_price) / cur_qty * delta)
        fp.quantity = cur_qty + delta
        log.append(f"🏭 {fp.name}: {delta:+.2f} {fp.unit} {verb}")
    if log:
        db.flush()
    return log


def _adjust_finished_diff(db: Session, old_items, new_items,
                          company_id: int = None) -> list:
    """Tayyor mahsulot farqini to'g'rilaydi (buyurtma TAHRIRLANGANDA).

    MUHIM: avval bu yerda faqat `fp.quantity` to'g'rilanardi, `fp.cost_price`
    esa HECH QACHON tegilmasdi — masalan 100m dan 70m ga tushirilsa, 30m
    omborga qaytardi, lekin uning tan narxi hech qachon qaytmasdan, "yo'qolib"
    qolardi (bu — buyurtma O'CHIRILGANDA ishlaydigan _return_finished_for_order
    funksiyasida to'g'ri qilingan edi, lekin TAHRIRLASHDA unutilgan ekan).
    Endi ikkalasi ham, bir xil BARQAROR formuladan foydalanadi."""
    def _group(items):
        out = {}
        for d in items:
            fpid = d.get('finished_product_id') if isinstance(d, dict) else getattr(d, 'finished_product_id', None)
            if not fpid:
                continue
            cat = (d.get('category') if isinstance(d, dict) else d.category) or ''
            if cat.lower() == 'profil':
                q = float((d.get('length') if isinstance(d, dict) else d.length) or 0)
            else:
                q = float((d.get('quantity') if isinstance(d, dict) else d.quantity) or 0)
            out[fpid] = out.get(fpid, 0.0) + q
        return out

    old_g = _group(old_items)
    new_g = _group(new_items)
    log = []

    for fpid in set(old_g) | set(new_g):
        diff = new_g.get(fpid, 0.0) - old_g.get(fpid, 0.0)
        if abs(diff) < 0.001:
            continue
        # M4 (2026-09-18) — TENANT: boshqa korxonaning mahsuloti bo'lsa rad etiladi.
        fp = _fp_for_tenant(db, fpid, company_id)
        if not fp:
            continue
        # diff > 0: buyurtmaga YANA olindi (ombordan yechiladi, tan narx kamayadi)
        # diff < 0: buyurtmadan qaytdi (omborga qaytadi, tan narx ham qaytadi)
        cur_qty = float(fp.quantity or 0)
        unit_cost = _fp_stable_unit_cost(db, fp)
        cost_delta = -unit_cost * diff if unit_cost > 0 else (
            -(float(fp.cost_price) / cur_qty * diff) if cur_qty > 0 and fp.cost_price else 0
        )
        fp.cost_price = max(0, float(fp.cost_price or 0) + cost_delta)
        if diff > 0:
            fp.quantity = max(0, cur_qty - diff)
            log.append(f"🏭 {fp.name}: -{diff:g} {fp.unit}")
        else:
            fp.quantity = cur_qty + abs(diff)
            log.append(f"🏭 {fp.name}: +{abs(diff):g} {fp.unit} qaytdi")

    if log:
        db.flush()
    return log


def check_finished_for_order(db: Session, items, company_id: int = None) -> dict:
    """Tayyor mahsulot yetadimi — tekshiradi.

    M4 (2026-09-18) — TENANT: company_id berilsa, mahsulot faqat SHU
    korxonadan qidiriladi; boshqa korxonaniki bo'lsa "topilmadi" deb
    hisoblanadi (uning qoldig'i O'QILMAYDI ham)."""
    shortages = []
    need = {}

    for it in items:
        fpid = getattr(it, 'finished_product_id', None)
        if not fpid:
            continue
        cat = (it.category or '').lower()
        qty = float(it.length or 0) if cat == 'profil' else float(it.quantity or 0)
        if qty <= 0:
            continue
        need[fpid] = need.get(fpid, 0.0) + qty

    for fpid, qty in need.items():
        fp = get_finished_product(db, fpid, company_id)
        if not fp:
            shortages.append("Tayyor mahsulot topilmadi")
            continue
        if float(fp.quantity or 0) < qty - 0.001:
            shortages.append(
                f"🏭 {fp.name}: omborda {float(fp.quantity):g} {fp.unit}, kerak {qty:g} {fp.unit}"
            )

    return {"enough": len(shortages) == 0, "shortages": shortages}


def get_orders(db: Session, project_id: Optional[int] = None,
               company_id: int = None) -> List[Order]:
    query = db.query(Order).filter(Order.is_deleted.isnot(True))
    if company_id is not None:
        query = query.filter(Order.company_id == company_id)
    if project_id:
        query = query.filter(Order.project_id == project_id)
    return query.order_by(Order.created_at.desc()).all()


def get_orders_for_main_page(db: Session, days: int = 90, show_all: bool = False,
                             company_id: int = None) -> List[Order]:
    """Buyurtmalar sahifasining ASOSIY ro'yxati uchun — tezlik uchun,
    faqat SO'NGGI `days` kunlik yakunlangan buyurtmalarni ko'rsatadi.

    MUHIM: hali TUGALLANMAGAN (draft/yangi/jarayonda/qoplamada) buyurtmalar
    — necha kunlik bo'lishidan qat'i nazar, DOIM ko'rsatiladi, chunki ular
    hali ishlanishi kerak bo'lgan, e'tibor talab qiladigan ish.

    show_all=True bo'lsa — barcha (eski) buyurtmalar ham qo'shiladi
    ("Eski buyurtmalarni ko'rish" tugmasi uchun)."""
    from models import OrderStatus
    from datetime import timedelta

    _mq = db.query(Order)
    if company_id is not None:
        _mq = _mq.filter(Order.company_id == company_id)
    base = _mq.filter(Order.is_deleted.isnot(True))

    if show_all:
        return base.order_by(Order.created_at.desc()).all()

    cutoff = datetime.utcnow() - timedelta(days=days)
    unfinished_statuses = [OrderStatus.DRAFT, OrderStatus.NEW, OrderStatus.IN_PROGRESS, OrderStatus.COATING]

    result = base.filter(
        (Order.created_at >= cutoff) | (Order.status.in_(unfinished_statuses))
    ).order_by(Order.created_at.desc()).all()
    return result


def get_order(db: Session, order_id: int, company_id: int = None) -> Optional[Order]:
    """2026-09-18 — M2: company_id berilsa, buyurtma FAQAT o'sha korxonadan
    qidiriladi. Berilmasa — eski xatti-harakat (ichki chaqiruvlar uchun).
    Tashqi (API) chaqiruvlarning HAMMASI company_id uzatadi."""
    q = db.query(Order).filter(Order.id == order_id)
    if company_id is not None:
        q = q.filter(Order.company_id == company_id)
    return q.first()


# MUHIM (2026-09 — Fasa 4, tozalash): bu yerda avval mark_order_ready()
# funksiyasi bo'lgan — ESKI, buyurtmani "Tayyor" qiladigan mexanizm.
# 2026-09 chuqur auditda aniqlandiki, bu funksiya allaqachon DEAD CODE
# edi: buyurtmani "Tayyor" qiladigan HAQIQIY, jonli endpoint (main.py:
# api_mark_order_ready) buni EMAS, services.complete_order() ni
# chaqiradi — shuning uchun bu kod HECH QACHON ishga tushmasdi. Ustiga
# ustak, u qoplama xomashyosini services.complete_order() dan BUTUNLAY
# BOSHQACHA, qattiq kodlangan (kg_per_meter=0.5) formula bilan hisoblardi
# — agar kimdir kelajakda uni qayta chaqirsa, xomashyo IKKI MARTA
# ayirilib qolishi mumkin edi ("loaded trap"). Shu xavf tufayli,
# foydalanuvchi tasdig'i bilan, funksiya BUTUNLAY OLIB TASHLANDI.
# Buyurtmani tayyorlashning HAQIQIY, yagona yo'li — services.complete_order().


# ============================================================
# ORDER edit/delete
# ============================================================

# 2026-09-21 (13-sizish) — `PUT /api/order-items/{id}` tanasidagi HAR
# qanday kalit tekshiruvsiz `setattr` bilan detalga yozilardi (O'LCHANGAN):
#   * `company_id` + `order_id` + `penoplast_id` BIRGA A korxonaniki qilib
#     yuborilsa, model qo'riqchisi hammasini "A niki" deb ko'rib o'tkazardi:
#     B ning detali A ning buyurtmasiga ko'chardi. Filtr o'chiq: A penoplasti
#     kamayib, A da ombor harakati yozilardi. Filtr yoniq: A ombori
#     o'zgarmasa ham A buyurtmasi ichiga begona detal tushardi. Yolg'iz
#     kalitlarni qo'riqchi 409 bilan ushlardi — faqat uchalasi birga ochiq.
#   * `id` (asosiy kalit) o'zgarardi (200); `sub_details` ro'yxati omborni
#     to'g'rilamasdan o'chardi; `order`, `delivered_qty` → 500.
# Endi FAQAT detalning o'z xususiyatlari o'zgaradi. Bog'lanishlar
# (korxona, buyurtma, tayyor mahsulot, retsept, mahsulot turi, rasm —
# o'z marshruti bor) bu yo'l bilan O'ZGARMAYDI.
_ORDER_ITEM_UPDATE_FIELDS = {
    "name", "category", "width", "thickness", "length", "quantity",
    "is_coated", "unit_price", "unit_price_for_volume", "price_per_m3",
    "penoplast_id", "notes",
}
# Bazadagi Numeric(12,2) sig'imi — schemas.OrderItemCreate dagi bilan bir xil.
_ORDER_ITEM_MAX_MONEY = 9_999_999_999.99
# 17f (2026-09-22): Numeric(12,2) ustunidagi ENG KICHIK musbat qiymat — 1 tiyin.
# HAQIQIY PostgreSQL 16 da O'LCHANGAN (`work/probe17f_pg.py`): musbat bo'lishi
# SHART bo'lgan 12 ta pul yo'lining HAMMASI `0.001` ni 200 bilan qabul qilardi,
# baza esa uni 0.00 ga yaxlitlardi — ya'ni "musbat" qoidasi jimgina buzilardi:
# 0 so'mlik xarajat / avans / ta'minotchiga to'lov / mijoz to'lovi / transport,
# 0 so'mlik oylik majburiyat va sovg'a bosqichi, 1 tiyinlik xarid jami bilan
# 0 so'mlik narx, kelishilgan summa 0 (chegirma 100 %, qarz esa JAMI summadan —
# 17e aynan to'sgan ikki talqin). SQLite yaxlitlamaydi, shuning uchun lokal
# testlar buni ko'rmasdi. Qoida: `chegara` = pul sig'imi bo'lgan (ya'ni 2 xonali
# pul ustuniga yoziladigan) MUSBAT son 2 xonagacha yaxlitlanganda ham kamida
# 1 tiyin bo'lsin. Manfiy bo'lmasligi kifoya qiladigan (0 ruxsat) maydonlarga
# tegilmaydi — ular uchun 0.00 ga yaxlitlanish qonuniy qiymat.
_PUL_ENG_KAM = 0.01
# 17f (2026-09-22) — 0 RUXSAT etilgan, lekin 0 dan katta bo'lsa HOSILA yozuv
# yaratadigan pul maydonlari: 0 yoki kamida 1 tiyin. HAQIQIY PostgreSQL 16 da
# O'LCHANGAN (`work/probe17f_hosila.py`):
#   * xarid (`POST /api/inventory/{id}/purchase`) `paid_now: 0.001` — 17e da
#     0.00 so'mlik ta'minotchiga to'lov yozilardi; ta'minotchi to'lovi ildizi
#     17f da qat'iy bo'lgach esa xarid SAQLANIB (ombor +miqdor), keyin 500
#     chiqardi (to'lov yozilmay qolardi — YARIM saqlanish), chunki marshrut
#     to'lovni xarid COMMIT qilingandan KEYIN yozadi; `transport_payer: self`
#     bilan `transport_cost: 0.001` — 0.00 so'mlik kirish transporti (transport
#     ildizi qat'iy bo'lgach — xuddi shu yarim saqlanish bo'lardi);
#   * kirim hujjati (`POST /api/inventory/receipt`) transport / tushirish /
#     yuklash / boshqa xarajat `0.001` — Moliyada 0.00 so'mlik xarajat,
#     `paid_now: 0.001` — 0.00 so'mlik ta'minotchiga to'lov.
# Tana tekshiruvi har qanday yozuvdan OLDIN ishlaydi, shuning uchun bu yerda
# to'sish yarim saqlanishni ham, 0 so'mlik hosila yozuvni ham yo'q qiladi.
# Aniq 0 — ruxsat (to'lov / xarajat yo'q degani).
_NOL_YOKI_TIYIN = {
    "Purchase": ("paid_now", "transport_cost"),
    "Receipt": ("paid_now", "transport_cost", "tushirish_cost", "yuklash_cost",
                "boshqa_cost"),
    # 17g (2026-09-22) — HAQIQIY PostgreSQL 16 da O'LCHANGAN (`work/probe17g_pg.py`,
    # asl kod = 17f): yetkazishdagi to'lov `0.001` → 0.00 so'mlik `Payment`
    # yozuvi; qaytarish summasi `0.001` → 0.00 saqlanardi (0 esa "server o'zi
    # hisoblasin" degani — ya'ni foydalanuvchi bergan summa jimgina yo'qolardi);
    # yetkazish transporti `0.001` → 0.00.
    "Delivery": ("payment_amount", "transport_cost"),
    "Return": ("refund_amount",),
}


def _pul2_decimal(v):
    """Pul qiymatini PostgreSQL `Numeric(12,2)` bilan AYNAN bir xil yaxlitlaydi
    va `Decimal` qaytaradi (17g, 2026-09-22).

    HAQIQIY PostgreSQL 16 da O'LCHANGAN: baza sonni uning o'nlik yozuvi
    bo'yicha, 0.5 ni YUQORIGA yaxlitlaydi — `10.335` → 10.34, `1000.005` →
    1000.01, `0.125` → 0.13. Python ning `round(10.335, 2)` esa 10.33 beradi
    (ikkilik kasr + "bankir" yaxlitlashi), ya'ni `round()` bilan hisoblangan
    jami bazadagi narxdan boshqa narxga tayanardi. Shuning uchun bu yerda
    `repr` (eng qisqa aniq o'nlik yozuv) + `ROUND_HALF_UP`."""
    from decimal import Decimal, ROUND_HALF_UP
    return Decimal(repr(float(v))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _pul2(v) -> float:
    """`_pul2_decimal` — `float` ko'rinishida (bazaga yoziladigan qiymat)."""
    return float(_pul2_decimal(v))


def _xarid_narx_jami(miqdor, narx):
    """Xarid qatorining bazaga yoziladigan (narx, jami) juftligi (17g).

    HAQIQIY PostgreSQL 16 da O'LCHANGAN (asl kod = 17f): narx va jami ALOHIDA
    yaxlitlanardi — `3 × 1234.567` → narx 1234.57, jami 3703.70 (3 × 1234.57 =
    3703.71); `333 × 10.335` → narx 10.34, jami 3441.56 (to'g'risi 3443.22 —
    1.66 so'm farq, miqdor oshgani sari o'sadi); `7 × 0.125` → narx 0.13, jami
    0.88. Ya'ni xarid tarixida ko'rinadigan "miqdor × narx" ta'minotchi
    qarzidagi (jami yig'indisi) summadan farq qilardi. UI foydalanuvchidan
    AYNAN 1 birlik narxini oladi (jamini o'zi hisoblaydi), shuning uchun:
    avval narx bazadagidek 2 xonaga yaxlitlanadi, jami SHU narxdan hisoblanadi.
    Foydalanuvchi to'xtatilmaydi; farq 1 birlikka yarim tiyindan oshmaydi."""
    from decimal import Decimal, ROUND_HALF_UP
    narx2 = _pul2_decimal(narx)
    jami2 = (Decimal(repr(float(miqdor))) * narx2).quantize(Decimal("0.01"),
                                                              rounding=ROUND_HALF_UP)
    return float(narx2), float(jami2)


def _json_son(key, value, bosh_mumkin, musbat, chegara=None):
    """JSON tanasidan kelgan sonni QAT'IY tekshiradi (2026-09-21).

    Matn, `true/false`, NaN/cheksizlik, manfiy (va `musbat` da nol) yoki
    `chegara` dan katta qiymat — `ValueError` (marshrutlar uni 400 ga
    aylantiradi). Ilgari bunday qiymatlar yo 500 berardi (`float("abc")`,
    PostgreSQL da Numeric sig'imidan oshish), yo jimgina yozilardi
    (manfiy narx, `true` → 1.0)."""
    import math
    if value is None:
        if bosh_mumkin:
            return None
        raise ValueError(f"'{key}' bo'sh bo'lishi mumkin emas")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"'{key}' son bo'lishi kerak")
    v = float(value)
    if math.isnan(v) or math.isinf(v):
        raise ValueError(f"'{key}' son bo'lishi kerak")
    if musbat and v <= 0:
        raise ValueError(f"'{key}' musbat bo'lishi kerak")
    if v < 0:
        raise ValueError(f"'{key}' manfiy bo'lishi mumkin emas")
    if chegara is not None and v > chegara:
        raise ValueError(f"'{key}' juda katta")
    # 17f: 2 xonali pul ustuniga yoziladigan MUSBAT son 0.00 ga aylanmasin.
    if musbat and chegara == _ORDER_ITEM_MAX_MONEY and round(v, 2) < _PUL_ENG_KAM:
        raise ValueError(f"'{key}' kamida {_PUL_ENG_KAM} bo'lishi kerak "
                         "(1 tiyindan kichik summa bazada 0 ga aylanadi)")
    return v


# ── 17c (2026-09-21): SO'ROV QATORIDAGI (query) sonlar ──────────────────
# Pul miqdori URL ning o'zida keladigan marshrutlar (avans, oylik
# tuzatish, oylik qarzini yopish) FastAPI `float` ga o'girilardi va
# `inf` / `nan` / `-5` / `1e20` ni JIMGINA qabul qilardi (O'LCHANGAN,
# `work/probe17c.py`): cheksiz avans avanslar ro'yxatini (500), cheksiz
# bonus "Qarzdorlar" sahifasini (500) BUZARDI, manfiy bonus esa mavjud
# bonusni jimgina o'chirardi. UI `parseFloat` / `parseNum` natijasini
# to'g'ridan-to'g'ri URL ga qo'yadi — `Infinity` ham brauzerdan KELADI.
# Shuning uchun marshrut qiymatni MATN sifatida oladi va bu yerda QAT'IY
# o'qiladi: faqat oddiy o'nlik yozuv (`12`, `12.5`, `1e3`), boshqa hamma
# narsa (`inf`, `Infinity`, `nan`, `true`, `12abc`, bo'sh — agar majburiy
# bo'lsa) — `ValueError` (marshrut → 400, hech narsa yozilmaydi).
_QUERY_SON_NAQSH = __import__("re").compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def _query_son(key, qiymat, bosh_mumkin, musbat, chegara=None):
    """So'rov qatoridagi sonni QAT'IY o'qiydi. `qiymat` — marshrutdan MATN
    (yoki `None`), crud ildizidan esa son ham bo'lishi mumkin (u holda
    to'g'ridan-to'g'ri `_json_son`). Bo'sh matn — `None` kabi."""
    if isinstance(qiymat, str):
        q = qiymat.strip()
        if q == "":
            qiymat = None
        elif not _QUERY_SON_NAQSH.match(q):
            raise ValueError(f"'{key}' son bo'lishi kerak")
        else:
            qiymat = float(q)
    return _json_son(key, qiymat, bosh_mumkin=bosh_mumkin, musbat=musbat,
                     chegara=chegara)


def _query_butun(key, qiymat, kichik, katta):
    """So'rov qatoridagi MAJBURIY butun sonni `kichik`–`katta` oralig'ida
    o'qiydi (yil, oy). Crud ildizidan `int` ham qabul qilinadi (`bool` —
    yo'q)."""
    if isinstance(qiymat, bool):
        raise ValueError(f"'{key}' butun son bo'lishi kerak")
    if isinstance(qiymat, str):
        q = qiymat.strip()
        if not q or not q.lstrip("+-").isdigit() or len(q) > 12:
            raise ValueError(f"'{key}' butun son bo'lishi kerak")
        qiymat = int(q)
    if not isinstance(qiymat, int):
        raise ValueError(f"'{key}' butun son bo'lishi kerak")
    if qiymat < kichik or qiymat > katta:
        raise ValueError(f"'{key}' {kichik}–{katta} oralig'ida bo'lishi kerak")
    return qiymat


def _query_matn(key, qiymat, uzunlik):
    """Ixtiyoriy izoh matni: `None` / matn, `uzunlik` belgidan oshmasin."""
    if qiymat is None:
        return None
    if not isinstance(qiymat, str):
        raise ValueError(f"'{key}' matn bo'lishi kerak")
    if len(qiymat) > uzunlik:
        raise ValueError(f"'{key}' juda uzun ({uzunlik} belgidan ko'p)")
    return qiymat


# Yil oralig'i — `_clean_by_rules` dagi "sana" qoidasi bilan bir xil.
_YIL_KICHIK, _YIL_KATTA = 2000, 2100


def _clean_avans(amount, notes=None, adv_date=None) -> dict:
    """17c: hodim avansi. `amount` — MUSBAT, chekli, `Numeric(12,2)` sig'imi
    ichida; `notes` — matn (Text ustun, oqilona chegara); `adv_date` —
    `YYYY-MM-DD` matni yoki `datetime`, bo'sh / `None` — bugun (UI sana
    maydoni bo'sh bo'lsa `adv_date=` yuboradi — bu SAQLANADI).
    Ilgari noto'g'ri sana (`abc`, `2026-13-45`) JIMGINA bugungi sanaga
    aylanardi — avans boshqa oyga tushib, o'sha oy oyligi noto'g'ri
    hisoblanardi (O'LCHANGAN)."""
    toza = {
        "amount": _query_son("amount", amount, bosh_mumkin=False, musbat=True,
                             chegara=_ORDER_ITEM_MAX_MONEY),
        "notes": _query_matn("notes", notes, _UPD_MATN_CHEGARA),
        "adv_date": None,
    }
    if isinstance(adv_date, datetime):
        sana = adv_date
    elif adv_date is None or (isinstance(adv_date, str) and adv_date.strip() == ""):
        sana = None
    elif isinstance(adv_date, str):
        try:
            sana = datetime.strptime(adv_date.strip(), "%Y-%m-%d")
        except ValueError:
            raise ValueError("'adv_date' YYYY-MM-DD ko'rinishidagi haqiqiy sana bo'lishi kerak")
    else:
        raise ValueError("'adv_date' YYYY-MM-DD ko'rinishidagi haqiqiy sana bo'lishi kerak")
    if sana is not None and not (_YIL_KICHIK <= sana.year <= _YIL_KATTA):
        raise ValueError(f"'adv_date' {_YIL_KICHIK}–{_YIL_KATTA} yillar oralig'ida bo'lishi kerak")
    toza["adv_date"] = sana
    return toza


def _clean_oylik_tuzatish(year, month, reduction_amount=None, reason=None,
                          bonus_amount=None, bonus_reason=None) -> dict:
    """17c: hodimning oylik qo'lda kamaytirishi / bonusi.
    `year` 2000–2100, `month` 1–12 (ilgari 13-oy, 0-oy, 1-yil, 99999-yil
    yozilardi — hech bir hisobotda ko'rinmaydigan "yetim" yozuvlar).
    Summalar — `None` (tegilmaydi), 0 (o'chiriladi — UI "Bo'sh/0 qoldirsangiz
    o'chadi" deydi, bu SAQLANADI) yoki MUSBAT, chekli, sig'im ichida.
    Manfiy summa ilgari mavjud bonusni JIMGINA o'chirardi — endi 400."""
    return {
        "year": _query_butun("year", year, _YIL_KICHIK, _YIL_KATTA),
        "month": _query_butun("month", month, 1, 12),
        "reduction_amount": _query_son("reduction_amount", reduction_amount,
                                       bosh_mumkin=True, musbat=False,
                                       chegara=_ORDER_ITEM_MAX_MONEY),
        "reason": _query_matn("reason", reason, _UPD_MATN_CHEGARA),
        "bonus_amount": _query_son("bonus_amount", bonus_amount,
                                   bosh_mumkin=True, musbat=False,
                                   chegara=_ORDER_ITEM_MAX_MONEY),
        "bonus_reason": _query_matn("bonus_reason", bonus_reason, _UPD_MATN_CHEGARA),
    }


def _clean_oylik_yopish(year, month, amount) -> dict:
    """17c: "Qarzdorlar" sahifasidagi hodim oylik qarzini yopish
    (`services.close_employee_debt` — avans yozuvi yaratadi). `month` 13
    ilgari `datetime(year, 13, …)` da 500 berardi; `amount` avans bilan bir
    xil qoida (musbat, chekli, sig'im ichida)."""
    return {
        "year": _query_butun("year", year, _YIL_KICHIK, _YIL_KATTA),
        "month": _query_butun("month", month, 1, 12),
        "amount": _query_son("amount", amount, bosh_mumkin=False, musbat=True,
                             chegara=_ORDER_ITEM_MAX_MONEY),
    }


# ── 17d (2026-09-21): LOY miqdori va doimiy majburiyat ──────────────────
# O'LCHANGAN (`work/probe17d.py`, har prob alohida toza bazada, asl kod =
# kech19): buyurtmaning loy miqdori 7 marshrutda URL da keladi va FastAPI
# `float` uni tekshiruvsiz o'tkazardi:
#   * `inf` → loy xomashyosi qoldig'i −Infinity SAQLANARDI, buyurtma
#     kartasi (`/api/orders/{id}`) va "Qarzdorlar" / biznes-salomatlik
#     sahifalari 500 (`/ready` va `PUT /loy` javobi 500 bo'lsa ham qiymat
#     yozilib qolardi; `DELETE` esa 200 qaytarib buyurtmani o'chirardi);
#   * manfiy reja / haqiqiy loy → omborga olinganidan KO'P qaytarilardi
#     (5 kg olingan, −5 bilan 7.5 kg qaytdi);
#   * `1e20` → qoldiq −5×10¹⁹; `nan` → `PUT /api/orders/{id}` detallarni
#     saqlab bo'lgach 500 (yarim yozuv); `1_000` → 1000.
# Tanadagi `loy_kg` (buyurtma yaratish) ham: `Infinity` → −∞, `true` → 1 kg,
# `"5"` → 5 kg. Loy — og'irlik (kg): manfiy EMAS, chekli, `_UPD_SON_CHEGARA`
# dan katta emas (17a `Produce.loy_kg` bilan bir xil chegara). 0 — ruxsat
# ("loy yo'q" / rejani bekor qilish).
def _query_loy(key, qiymat, bosh_mumkin):
    """So'rov qatoridagi loy miqdori (kg) — MATN (marshrutdan) yoki son
    (crud ildizidan). `bosh_mumkin` bo'lsa bo'sh / `None` → `None`."""
    return _query_son(key, qiymat, bosh_mumkin=bosh_mumkin, musbat=False,
                      chegara=_UPD_SON_CHEGARA)


def _json_loy(key, qiymat):
    """Tanadagi (JSON) ixtiyoriy loy miqdori: `None` yoki haqiqiy son.
    Matn (`"5"`) va `true` RAD etiladi — `_query_son` matnni o'qirdi."""
    return _json_son(key, qiymat, bosh_mumkin=True, musbat=False,
                     chegara=_UPD_SON_CHEGARA)


# `recurring_obligations` ustunlari: category String(30), label String(60),
# icon String(10). PostgreSQL uzun matnni RAD etadi → 500 (JONLI O'LCHANGAN:
# `debts.html` kodni nomdan yasaydi — 35 belgili nom → 40 belgili kod → 500,
# hech narsa saqlanmadi). `monthly_target`: `inf` → "Qarzdorlar" sahifasi
# va majburiyatlar ro'yxati 500; `nan` → NULL; manfiy / 0 / 1e20 qabul.
# `due_day` (oyning nechanchi kuni): 0, −3, 32, 99999 qabul qilinardi.
_MAJBURIYAT_KOD_MAX = 30
_MAJBURIYAT_NOM_MAX = 60
_MAJBURIYAT_BELGI_MAX = 10


def _clean_majburiyat(category, label, monthly_target, icon=None, due_day=None) -> dict:
    """17d: doimiy majburiyat (`POST /api/obligations/recurring`).
    `category` — 1–30 belgi, `label` — 1–60 belgi (bo'sh / faqat bo'shliq —
    yo'q), `icon` — 0–10 belgi (bo'sh → 📦), `monthly_target` — MUSBAT
    (UI 0 ni o'zi rad etadi), chekli, `Numeric(12,2)` sig'imi ichida,
    `due_day` — 1–31 (bo'sh → 5, UI ham shunday qiladi)."""
    def _matn(key, v, uzunlik, majburiy):
        if v is None:
            if majburiy:
                raise ValueError(f"'{key}' bo'sh bo'lishi mumkin emas")
            return None
        if not isinstance(v, str):
            raise ValueError(f"'{key}' matn bo'lishi kerak")
        v = v.strip()
        if majburiy and not v:
            raise ValueError(f"'{key}' bo'sh bo'lishi mumkin emas")
        if len(v) > uzunlik:
            raise ValueError(f"'{key}' juda uzun ({uzunlik} belgidan ko'p)")
        return v

    kun = due_day
    if kun is None or (isinstance(kun, str) and kun.strip() == ""):
        kun = 5
    return {
        "category": _matn("category", category, _MAJBURIYAT_KOD_MAX, True),
        "label": _matn("label", label, _MAJBURIYAT_NOM_MAX, True),
        "icon": _matn("icon", icon, _MAJBURIYAT_BELGI_MAX, False) or "📦",
        "monthly_target": _query_son("monthly_target", monthly_target,
                                     bosh_mumkin=False, musbat=True,
                                     chegara=_ORDER_ITEM_MAX_MONEY),
        "due_day": _query_butun("due_day", kun, 1, 31),
    }


# 2026-09-21 (14-band) — `setattr` sikllari: tahrir marshrutlari tanasi.
# Material / tayyor mahsulot / usta / hodim / loyiha / ta'minotchi tahriri
# tanadagi maydonni TEKSHIRUVSIZ yozardi (O'LCHANGAN, lokal va jonli):
#   * `PUT /api/inventory/{id}` — manfiy narx (jonli: -5000 SAQLANDI; 13.3
#     da `/price` yopilgan edi, lekin shu ikkinchi yo'l ochiq qolgan edi),
#     hajm 0 / manfiy, manfiy min qoldiq, `stock_quantity` to'g'ridan
#     (999 / -50, ombor HARAKATISIZ), `is_default_penoplast` ikkinchi
#     materialga, bo'sh nom;
#   * tayyor mahsulot — manfiy / 1e20 miqdor va narx, NaN → 500 (lekin
#     qiymat baribir yozilgan);
#   * usta — cashback -10 / 500 %, bo'sh ism; hodim — manfiy oylik, 500 %,
#     noto'g'ri `pay_type` JIM e'tiborsiz qolardi (200);
#   * loyiha — manfiy to'langan / byudjet, `total_paid` qo'lda (to'lovlardan
#     hisoblanadigan qiymat buzilardi), noto'g'ri `status` → 500 (SQLite da
#     qator yozilib, BUTUN loyihalar ro'yxati 500 berardi; PostgreSQL rad
#     etadi); ta'minotchi — bo'sh nom, `null` nom → 500.
# Kirish sxemasi (pydantic) bu qiymatlarning hech birini cheklamaydi va
# `true` → 1.0 kabi JIM o'giradi. Endi: ruxsat ro'yxati + qat'iy turlar +
# ustun sig'imi (PostgreSQL da uzun matn / katta son → 500) + ma'noli
# chegara. Qoida buzilsa `ValueError` (marshrut → 400), hech narsa
# yozilmaydi. Hisob yozuvi bilan o'zgarishi SHART bo'lgan maydonlar
# (`stock_quantity`, tayyor mahsulot `quantity`, `total_paid`,
# `is_default_penoplast`) bu yo'ldan umuman O'ZGARMAYDI — o'z yo'li bor.
_UPD_MATN_CHEGARA = 10_000          # Text ustunlar uchun oqilona chegara
_UPD_SON_CHEGARA = 1_000_000_000_000.0   # Float ustunlar (miqdor, hajm)

# Qoida shakllari:
#   ("matn", majburiy, uzunlik)        — majburiy: None/bo'sh rad
#   ("son", bosh_mumkin, musbat, chegara)
#   ("bool", bosh_mumkin)
#   ("tanlov", bosh_mumkin, {qabul qilinadigan: kanonik})
#   ("butun", bosh_mumkin, eng_kichik, eng_katta)
#   ("tg",)                            — Telegram ID: matn yoki butun son


def _upd_rules():
    """Model nomi → {maydon: qoida}. Funksiya ichida — enum lar modul
    oxirida import qilinadi, chaqiruv paytida esa hammasi tayyor."""
    from models import PayType as _PT, ProjectStatus as _PS
    pay = {}
    for m in _PT:
        pay[m.value] = m.value
        pay[m.name] = m.value
        pay[m.name.lower()] = m.value
    st = {}
    for m in _PS:
        st[m.name] = m.name
        st[m.value] = m.name
        st[m.name.lower()] = m.name
    money = _ORDER_ITEM_MAX_MONEY
    return {
        "Inventory": {
            "item_name": ("matn", True, 100),
            "unit": ("matn", True, 20),
            "min_stock": ("son", True, False, _UPD_SON_CHEGARA),
            "price_per_unit": ("son", True, False, money),
            "volume_per_unit": ("son", True, True, _UPD_SON_CHEGARA),
            "is_penoplast": ("bool", False),
            "category": ("matn", False, 50),
            "notes": ("matn", False, _UPD_MATN_CHEGARA),
            "base_unit": ("matn", False, 20),
            "conversion_factor": ("son", True, True, _UPD_SON_CHEGARA),
        },
        "FinishedProduct": {
            "name": ("matn", True, 150),
            "unit_price": ("son", True, False, money),
            "notes": ("matn", False, _UPD_MATN_CHEGARA),
        },
        "Master": {
            "name": ("matn", True, 100),
            "phone": ("matn", True, 20),
            "cashback_percent": ("son", True, False, 100.0),
            "kpi_percent": ("son", True, False, 100.0),
            "telegram_id": ("tg",),
            "is_active": ("bool", False),
            "region": ("matn", False, 50),
            "notes": ("matn", False, _UPD_MATN_CHEGARA),
        },
        "Employee": {
            "name": ("matn", True, 100),
            "position": ("matn", False, 100),
            "pay_type": ("tanlov", False, pay),
            "fixed_amount": ("son", True, False, money),
            "percent_value": ("son", True, False, 100.0),
            "per_unit_rate": ("son", True, False, money),
            "per_unit_type": ("tanlov", False, {"blok": "blok", "metr": "metr", "dona": "dona"}),
            "extra_monthly": ("son", True, False, money),
            "production_type": ("tanlov", True, {"penoplast": "penoplast", "gips": "gips",
                                                 "umumiy": "umumiy"}),
            "is_active": ("bool", False),
            "notes": ("matn", False, _UPD_MATN_CHEGARA),
            "effective_year": ("butun", True, 2000, 2100),
            "effective_month": ("butun", True, 1, 12),
            "reason": ("matn", False, _UPD_MATN_CHEGARA),
        },
        "Project": {
            "project_name": ("matn", True, 200),
            "client_name": ("matn", True, 100),
            "client_phone": ("matn", False, 20),
            "client_address": ("matn", False, _UPD_MATN_CHEGARA),
            "description": ("matn", False, _UPD_MATN_CHEGARA),
            "total_budget": ("son", True, False, money),
            "status": ("tanlov", False, st),
            "notes": ("matn", False, _UPD_MATN_CHEGARA),
        },
        "Supplier": {
            "name": ("matn", True, 150),
            "phone": ("matn", False, 20),
            "notes": ("matn", False, _UPD_MATN_CHEGARA),
            "is_active": ("bool", False),
        },
    }


# Hisob yozuvi bilan o'zgarishi shart bo'lgan maydonlar — aniq sabab bilan.
_UPD_TAQIQ = {
    "Inventory": {
        "stock_quantity": "Qoldiq faqat kirim / chiqim orqali o'zgaradi (ombor harakati yoziladi)",
        "is_default_penoplast": "Asosiy penoplast alohida tugma orqali belgilanadi",
    },
    "FinishedProduct": {
        "quantity": "Miqdor faqat qo'shish / kamaytirish / sotish orqali o'zgaradi",
    },
    "Project": {
        "total_paid": "To'langan summa to'lovlardan hisoblanadi — qo'lda o'zgartirib bo'lmaydi",
    },
}


def _clean_update(model: str, data) -> dict:
    """Tahrir tanasini QAT'IY tekshiradi va tozalangan nusxasini qaytaradi.

    `data` — xom JSON (marshrut) yoki `model_dump(exclude_unset=True)`
    (crud ildizi). Noma'lum / taqiqlangan kalit, noto'g'ri tur, bo'sh
    majburiy maydon, ustun sig'imidan uzun matn yoki chegaradan tashqari
    son — `ValueError`. Matnlar O'ZGARTIRILMAYDI (faqat tekshiriladi);
    tanlov maydonlari kanonik qiymatga keltiriladi (`status` → enum NOMI,
    `pay_type` → enum QIYMATI) — pastdagi crud o'giruvchilari shuni kutadi."""
    return _clean_by_rules(_upd_rules()[model], _UPD_TAQIQ.get(model, {}), data,
                           "Bu maydonni o'zgartirib bo'lmaydi: ")


def _clean_by_rules(rules: dict, taqiq: dict, data, notogri_xabar: str) -> dict:
    """`_clean_update` va `_clean_create` ning umumiy yadrosi (2026-09-21,
    15-band): qoida shakllari `_upd_rules` tepasidagi izohda. Qo'shimcha
    shakl — ("sana", bosh_mumkin): `YYYY-MM-DD` yoki ISO sana-vaqt matni
    (yoki crud ildizida `datetime`), 2000–2100 yillar; bo'sh matn → None."""
    if not isinstance(data, dict):
        raise ValueError("Noto'g'ri so'rov")
    for key in data:
        if key in taqiq:
            raise ValueError(taqiq[key])
    notogri = sorted(str(k)[:40] for k in data if k not in rules)
    if notogri:
        raise ValueError(notogri_xabar + ", ".join(notogri[:10]))

    toza = {}
    for key, value in data.items():
        qoida = rules[key]
        tur = qoida[0]
        if tur == "matn":
            majburiy, uzunlik = qoida[1], qoida[2]
            if value is None:
                if majburiy:
                    raise ValueError(f"'{key}' bo'sh bo'lishi mumkin emas")
                toza[key] = None
                continue
            if not isinstance(value, str):
                raise ValueError(f"'{key}' matn bo'lishi kerak")
            if majburiy and not value.strip():
                raise ValueError(f"'{key}' bo'sh bo'lishi mumkin emas")
            if len(value) > uzunlik:
                raise ValueError(f"'{key}' juda uzun ({uzunlik} belgidan ko'p)")
            toza[key] = value
        elif tur == "son":
            toza[key] = _json_son(key, value, bosh_mumkin=qoida[1],
                                  musbat=qoida[2], chegara=qoida[3])
        elif tur == "bool":
            if value is None and qoida[1]:
                toza[key] = None
                continue
            if not isinstance(value, bool):
                raise ValueError(f"'{key}' true yoki false bo'lishi kerak")
            toza[key] = value
        elif tur == "tanlov":
            bosh_mumkin, qabul = qoida[1], qoida[2]
            if value is None:
                if not bosh_mumkin:
                    raise ValueError(f"'{key}' bo'sh bo'lishi mumkin emas")
                toza[key] = None
                continue
            if isinstance(value, str) and value.strip() == "" and bosh_mumkin:
                toza[key] = None
                continue
            if not isinstance(value, str) or value.strip() not in qabul:
                raise ValueError(f"'{key}' noto'g'ri qiymat")
            toza[key] = qabul[value.strip()]
        elif tur == "butun":
            bosh_mumkin, kichik, katta = qoida[1], qoida[2], qoida[3]
            if value is None:
                if not bosh_mumkin:
                    raise ValueError(f"'{key}' bo'sh bo'lishi mumkin emas")
                toza[key] = None
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"'{key}' butun son bo'lishi kerak")
            if value < kichik or value > katta:
                raise ValueError(f"'{key}' {kichik}–{katta} oralig'ida bo'lishi kerak")
            toza[key] = value
        elif tur == "tg":
            if value is None:
                toza[key] = None
                continue
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                raise ValueError(f"'{key}' matn yoki son bo'lishi kerak")
            v = str(value).strip()
            if len(v) > 50:
                raise ValueError(f"'{key}' juda uzun (50 belgidan ko'p)")
            toza[key] = v or None
        elif tur == "id":
            # 17-band: bog'lanish ID si — musbat butun son (bool emas).
            if value is None:
                if not qoida[1]:
                    raise ValueError(f"'{key}' bo'sh bo'lishi mumkin emas")
                toza[key] = None
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"'{key}' butun son bo'lishi kerak")
            if value < 1 or value > 2_147_483_647:
                raise ValueError(f"'{key}' noto'g'ri qiymat")
            toza[key] = value
        elif tur == "royxat":
            # 17-band: ichki qatorlar ro'yxati — har qator o'z qoidalari
            # bilan (`_clean_val`) to'liq tekshiriladi.
            ichki, eng_kam, eng_kop = qoida[1], qoida[2], qoida[3]
            if not isinstance(value, list):
                raise ValueError(f"'{key}' ro'yxat bo'lishi kerak")
            if len(value) < eng_kam:
                raise ValueError(f"'{key}' kamida {eng_kam} ta qatordan iborat bo'lishi kerak")
            if len(value) > eng_kop:
                raise ValueError(f"'{key}' juda ko'p qator ({eng_kop} tadan ko'p)")
            qatorlar = []
            for i, el in enumerate(value):
                try:
                    qatorlar.append(_clean_val(ichki, el))
                except ValueError as e:
                    raise ValueError(f"'{key}' {i + 1}-qator: {e}")
            toza[key] = qatorlar
        elif tur == "sana":
            if value is None or (isinstance(value, str) and value.strip() == ""):
                if not qoida[1]:
                    raise ValueError(f"'{key}' bo'sh bo'lishi mumkin emas")
                toza[key] = None
                continue
            if isinstance(value, datetime):
                sana = value
            elif isinstance(value, str) and len(value.strip()) <= 40:
                try:
                    sana = datetime.fromisoformat(value.strip())
                except ValueError:
                    raise ValueError(f"'{key}' sana bo'lishi kerak (YYYY-MM-DD)")
            else:
                raise ValueError(f"'{key}' sana bo'lishi kerak (YYYY-MM-DD)")
            if sana.tzinfo is not None:
                sana = sana.replace(tzinfo=None)
            if sana.year < 2000 or sana.year > 2100:
                raise ValueError(f"'{key}' 2000–2100 yillar oralig'ida bo'lishi kerak")
            toza[key] = sana
    return toza


# 2026-09-21 (15-band) — YARATISH (POST) marshrutlari tanasi.
# O'LCHANGAN (asl kod, lokal TestClient): `POST /api/inventory | masters |
# employees | projects | suppliers` sxemalari deyarli cheklovsiz edi —
# manfiy narx / byudjet / qo'shimcha oylik SAQLANARDI; `1e13` va `1e20`
# (PostgreSQL Numeric(12,2) da 500); Infinity SAQLANARDI, NaN yo 500, yo
# JIMGINA bo'sh qiymat; `true` → 1.0, "5000" → 5000 JIM o'girilardi; ustun
# sig'imidan uzun matn (PostgreSQL da 500); faqat bo'shliqdan iborat nom /
# birlik / telefon SAQLANARDI (hodim va ta'minotchida `strip()` dan keyin
# BO'SH nom); noto'g'ri `pay_type` JIMGINA "fixed" ga aylanardi (200),
# noto'g'ri `per_unit_type` / `production_type` yozilardi. Funksional xato:
# `create_master` `kpi_percent` ni umuman yozmasdi (7 → 0.0), loyiha
# yaratish formasidagi "Muddati" (`deadline`) sxemada yo'q edi — JIMGINA
# tashlab yuborilardi (jonli: 23 loyihaning birortasida muddat yo'q).
# Begona korxonaga sizish YO'Q: `company_id` / `id` kalitlari e'tiborsiz
# qolardi, korxona sessiyadan olinadi — endi ular 400 (noma'lum maydon).
# Qoidalar tahrir qoidalaridan (`_upd_rules`) olinadi — farqlar pastda.
_CREATE_MAJBURIY = {
    # model → {maydon: eng kam uzunlik (bo'shliqsiz) yoki None — faqat bor bo'lsin}
    "Inventory": {"item_name": 2, "unit": 1},
    "Master": {"name": 2, "phone": 7},
    "Employee": {"name": 2, "pay_type": None},
    "Project": {"project_name": 2, "client_name": 2},
    "Supplier": {"name": 2},
}

_CREATE_TAQIQ = {
    "Project": {
        "total_paid": "To'langan summa to'lovlardan hisoblanadi — qo'lda kiritib bo'lmaydi",
        "status": "Yangi loyiha har doim faol holatda yaratiladi",
    },
}


def _create_rules():
    """Model nomi → {maydon: qoida} — YARATISH uchun. Tahrir qoidalaridan
    farqi: boshlang'ich qoldiq (`stock_quantity`) va `is_default_penoplast`
    yaratishda RUXSAT (hisob yozuvi `add_item` ichida); sxemada majburiy
    son bo'lgan maydonlar bo'sh (null) bo'la olmaydi; `is_active`, hodim
    `effective_*` / `reason` va loyiha `status` yaratishda yo'q; loyiha
    `deadline` qo'shiladi."""
    r = _upd_rules()
    inv = dict(r["Inventory"])
    inv["stock_quantity"] = ("son", False, False, _UPD_SON_CHEGARA)
    inv["min_stock"] = ("son", False, False, _UPD_SON_CHEGARA)
    inv["volume_per_unit"] = ("son", False, True, _UPD_SON_CHEGARA)
    inv["is_default_penoplast"] = ("bool", False)
    ms = dict(r["Master"])
    ms.pop("is_active")
    ms["cashback_percent"] = ("son", False, False, 100.0)
    em = dict(r["Employee"])
    for k in ("is_active", "effective_year", "effective_month", "reason"):
        em.pop(k)
    for k in ("fixed_amount", "percent_value", "per_unit_rate"):
        em[k] = (em[k][0], False, em[k][2], em[k][3])
    em["per_unit_type"] = ("tanlov", False, {"blok": "blok", "metr": "metr", "dona": "dona"})
    pr = dict(r["Project"])
    pr.pop("status")
    pr["deadline"] = ("sana", True)
    sp = dict(r["Supplier"])
    sp.pop("is_active")
    return {"Inventory": inv, "Master": ms, "Employee": em, "Project": pr, "Supplier": sp}


def _clean_create(model: str, data) -> dict:
    """Yaratish tanasini QAT'IY tekshiradi va tozalangan nusxasini qaytaradi
    (15-band). `data` — xom JSON (marshrut) yoki `model_dump(exclude_unset=
    True)` (crud ildizi). Qoida buzilsa — `ValueError`, hech narsa yozilmaydi.
    Matnlar O'ZGARTIRILMAYDI; tanlov maydonlari kanonik qiymatga keladi."""
    toza = _clean_by_rules(_create_rules()[model], _CREATE_TAQIQ.get(model, {}),
                           data, "Noma'lum maydon: ")
    for key, eng_kam in _CREATE_MAJBURIY[model].items():
        if toza.get(key) is None:
            raise ValueError(f"'{key}' kiritilishi shart")
        if eng_kam and len(toza[key].strip()) < eng_kam:
            raise ValueError(f"'{key}' kamida {eng_kam} belgidan iborat bo'lishi kerak")
    if model == "Inventory":
        # Boshlang'ich qoldiq xarid yozuviga (`total_amount` Numeric(12,2))
        # sig'ishi shart — aks holda PostgreSQL da material yaratilib, xarid
        # yozuvi 500 bilan yiqilardi (material qoldiqli, xarajatsiz qolardi).
        miqdor = toza.get("stock_quantity") or 0
        narx = toza.get("price_per_unit") or 0
        if miqdor > 0 and narx > 0 and round(miqdor * narx, 2) > _ORDER_ITEM_MAX_MONEY:
            raise ValueError("Boshlang'ich qoldiq summasi (miqdor × narx) juda katta")
    return toza


# 2026-09-21 (17-band) — TAYYOR MAHSULOT qiymat yo'llari.
# O'LCHANGAN (asl kod, lokal TestClient, har prob toza bazada):
#   * `POST /api/finished/produce` — manfiy kenglik → hajm manfiy, penoplast
#     YECHILMAYDI, mahsulot BEPUL paydo bo'ladi; noto'g'ri `category` →
#     xomashyosiz "dona"; `unit_price` Infinity → 500, LEKIN yozuv qoladi va
#     `/finished` + `/api/finished` BUTUNLAY 500; NaN uzunlik → 500 + yozuv;
#     `loy_kg` Infinity → 500 + yozuv; 1e20 narx / miqdor; `true` → 1,
#     `"5"` → 5 JIM o'giriladi; nom `"    "` → strip → BO'SH nom; manfiy
#     `price_per_m3`; `penoplast_id` sifatida ODDIY material (penoplast
#     emas) ombordan "blok" deb yechiladi;
#   * `/{id}/add`, `/loss` — `true` → 1; JARAYONDAGI (in_progress)
#     mahsulotga qo'shish / brak (UI buni faqat TAYYOR mahsulotga beradi);
#   * `/sell` — narx 1e20 SAQLANDI (PostgreSQL Numeric(12,2) da 500),
#     Infinity → 500 + yozuv + `/api/finished/sales` BUTUNLAY 500;
#     noto'g'ri `payment_method` (ustun 20 belgi), 500 belgili xaridor
#     (ustun 150), mavjud bo'lmagan `master_id` (FK) SAQLANDI; jarayondagi
#     mahsulot SOTILDI;
#   * `/sell-batch` — BIR mahsulot ikki qatorda (6 + 6, qoldiq 10) → har qator
#     alohida tekshirilib, qoldiq -2 ga TUSHDI; Infinity narx → sotuv
#     yozuvi qolib, `/api/finished/sales` 500;
#   * `/production-brak` — `gips_*` maydonlari marshrutda e'tiborsiz edi.
# Endi: ruxsat ro'yxati + qat'iy turlar (`_clean_val`) marshrutda HAM crud
# ildizida HAM; hisob butunligi (savatcha yig'indisi, penoplast turi,
# tayyor holat, usta korxonada, summa sig'imi) crud ildizida.
_FP_KATEGORIYA = {"profil": "profil", "panel": "panel", "dona": "dona", "blok": "blok"}
_TOLOV_USULI = {"naqd": "naqd", "karta": "karta", "bank": "bank"}
# 17b (2026-09-21) — ombor kirimi va kirim hujjati tanlovlari.
# `transport_payer`: kim to'laydi — hech kim / o'zimiz / ta'minotchi
# (`suppliers.html` shu uchtasini yuboradi; boshqa qiymat JIM e'tiborsiz
# qolardi, ya'ni "o'z hisobimdan" deb belgilangan transport xarajati
# YOZILMASDAN qolishi mumkin edi).
_TRANSPORT_TOLOVCHI = {"none": "none", "self": "self", "supplier": "supplier"}
# `production_type`: kirim qaysi yo'nalishga tegishli. `supplier_receive.html`
# "Umumiy" uchun `null` yuboradi; `services.get_monthly_report` faqat
# 'penoplast' va 'gips' qiymatlarini taniydi, boshqa har qanday matn
# hisobotdan JIMGINA tushib qolardi.
_ISHLAB_CHIQARISH_TURI = {"umumiy": "umumiy", "penoplast": "penoplast",
                          "gips": "gips"}
# 17f (2026-09-22) — mijoz to'lovi tanlovlari: `models.PaymentType` va
# `models.PaymentMethod` qiymatlari (`orders.html` to'lov oynasidagi
# `pf-type` / `pf-method` va zaklat usuli AYNAN shular). Tayyor mahsulot
# sotuvining `_TOLOV_USULI` (naqd/karta/bank) — BOSHQA ro'yxat.
_TOLOV_TURI = {"zaklat": "zaklat", "partial": "partial", "final": "final"}
_TOLOV_USULI_MIJOZ = {"naqd": "naqd", "plastik": "plastik", "o'tkazma": "o'tkazma"}
# 17g (2026-09-22) — qaytarish sababi: `models.ReturnReason` qiymatlari
# (`returns.html` AYNAN "Ortiqcha" / "Brak" yuboradi). HAQIQIY PostgreSQL da
# O'LCHANGAN: noma'lum sabab (`"xyz"`) JIMGINA "Brak" ga aylanardi — ya'ni
# ombordan xomashyo yechilar va mahsulot omborga qaytmasdi.
_QAYTARISH_SABABI = {"Brak": "Brak", "Ortiqcha": "Ortiqcha",
                     "Notog'ri o'lcham": "Notog'ri o'lcham",
                     "Mijoz iltimosi": "Mijoz iltimosi"}
# kech53 (13-band, 1-qadam) — brak BOSQICHLARI (foydalanuvchi ro'yxati, kech45:
# "Kesish, Qoplash (loy tortish), Quritish, Saqlash / tashish"). Kod → yorliq.
# YAGONA manba: `returns.html` / `finished.html` tanlovi va ro'yxatdagi yorliq
# shu lug'atdan chiziladi (marshrut kontekstida `brak_bosqichlari`); sxemalardagi
# `Literal` ro'yxati bilan mosligi testda tekshiriladi. Bosqich IXTIYORIY —
# tanlanmasa NULL, brak yozish oqimi (miqdor, qiymat, xomashyo) O'ZGARMAYDI.
BRAK_BOSQICHLARI = {
    "kesish": "Kesish (penoplast kesish)",
    "qoplash": "Qoplash (loy tortish)",
    "quritish": "Quritish",
    "saqlash_tashish": "Saqlash / tashish",
}
_BRAK_BOSQICHI = {k: k for k in BRAK_BOSQICHLARI}
# kech56 (13-band, 7-qadam) — brak SABABLARI (foydalanuvchi qarori, kech56: "Ha, taklif
# qilingan ro'yxat bilan"). Kod → yorliq; YAGONA manba (UI tanlovi, ro'yxat yorlig'i,
# tahlil). Sabab IXTIYORIY — tanlanmasa NULL; brak yozish oqimi O'ZGARMAYDI.
BRAK_SABABLARI = {
    "xomashyo": "Xomashyo sifati",
    "ishchi": "Ishchi xatosi",
    "uskuna": "Uskuna / stanok nosozligi",
    "olcham": "O'lcham / qolip xatosi",
    "boshqa": "Boshqa",
}
_BRAK_SABABI = {k: k for k in BRAK_SABABLARI}
# kech56 (13-band, 7-qadam) — brak ME'YORI (foydalanuvchi qarori, kech56: "5 %"): oylik
# brak ulushi (Moliyadagi brak xarajati ÷ ishlab chiqarish tan narxi) shundan OSHSA —
# ogohlantirish (`services.get_brak_tahlil`, `/returns` va `/dashboard`).
BRAK_MEYORI_FOIZ = 5.0


def _brak_javobgar_tekshir(db, hodim_id, company_id):
    """kech56: brakka javobgar hodim — FAQAT shu korxonaning o'chirilmagan hodimi.
    Berilmasa (None) — hech narsa. Topilmasa `ValueError` (marshrut → 400), hech
    narsa yozilishidan OLDIN chaqiriladi."""
    if hodim_id is None:
        return None
    _q = db.query(Employee.id).filter(Employee.id == hodim_id,
                                      Employee.is_deleted.isnot(True))
    if company_id is not None:
        _q = _q.filter(Employee.company_id == company_id)
    if _q.first() is None:
        raise ValueError("Javobgar hodim topilmadi")
    return hodim_id


def hodim_nomlari(db, company_id=None) -> dict:
    """kech56: {hodim id: ism} — brak ro'yxatidagi javobgar yorlig'i uchun
    (o'chirilgan hodimlar ham — tarixiy yozuv nomsiz qolmasin)."""
    _q = db.query(Employee.id, Employee.name)
    if company_id is not None:
        _q = _q.filter(Employee.company_id == company_id)
    return {i: n for i, n in _q.all()}
# 17g — yetkazish transporti kim hisobidan (`models.Delivery.company_transport_cost`
# / `client_transport_cost` AYNAN shu to'rttasini taniydi; `orders.html`
# `dlv-transport-payer` tanlovi ham shular). O'LCHANGAN: noma'lum qiymat
# saqlanardi va transport summasi Moliyadan butunlay tushib qolardi (na
# korxona, na mijoz hisobiga); 21+ belgi — String(20) → 500.
_YETKAZISH_TOLOVCHI = {"none": "none", "client": "client", "company": "company",
                       "split": "split"}

# ── 17e (2026-09-22): kunlik xarajat va kelishilgan summa ───────────────
# O'LCHANGAN (`work/probe17e.py`, har prob alohida toza bazada, asl kod =
# 17d): `POST`/`PUT /api/finance/transactions` sxemasida summa uchun faqat
# `ge=0` bor edi:
#   * `Infinity` → javob 500, LEKIN yozuv SAQLANARDI va shundan keyin
#     `/api/finance/history` hamda xarajatlar ro'yxati BUTUNLAY 500;
#   * `1e20` (PostgreSQL da Numeric(12,2) → 500), `true` → 1 so'm,
#     `"5000"` → 5000, 0 so'm — qabul;
#   * kategoriya bo'sh / faqat bo'shliq / 31–300 belgi (PostgreSQL da
#     String(30) → 500) — qabul; noto'g'ri `production_type` ("xyz") —
#     qabul, oylik hisobotdan JIMGINA tushib qolardi; 21 belgili — PG 500;
#   * sana 0001-yil, 1999-yil, `12345` (→ 1970-yil) — qabul.
# `PUT /api/orders/{id}/agreed-amount` (`OrderAgreedUpdate`, faqat `ge=0`):
#   * `Infinity` → 500 (SQLite da SAQLANARDI, JONLI PostgreSQL da 500 va
#     `/logs` ga yozuv); `1e20` saqlanardi; `true` → 1 so'm (chegirma
#     99.9 %); `"800"` → 800; 0 → chegirma 100 %, lekin qarz JAMI summadan.
# Endi: ruxsat ro'yxati + qat'iy turlar (`_clean_val`) marshrutda HAM crud
# ildizida HAM (17b/17c naqshi).
_XARAJAT_KATEGORIYA_MAX = 30


def _val_rules():
    """17-band qoidalari: model (tana turi) → {maydon: qoida}."""
    money = _ORDER_ITEM_MAX_MONEY
    son = _UPD_SON_CHEGARA
    matn = _UPD_MATN_CHEGARA
    sotuv = {
        "finished_product_id": ("id", False),
        "quantity": ("son", False, True, son),
        "unit_price": ("son", False, False, money),
    }
    return {
        "Produce": {
            "name": ("matn", True, 150),
            "category": ("tanlov", False, _FP_KATEGORIYA),
            # O'lchamlar: manfiy EMAS (0 — "berilmagan": UI \"Blok\" turida
            # `length: _blokKerak || 0` yuboradi; hajm hisobi 0 ni e'tiborsiz
            # qoldiradi). Manfiy o'lcham → manfiy hajm → penoplast yechilmasdi.
            "width": ("son", True, False, son),
            "thickness": ("son", True, False, son),
            "length": ("son", True, False, son),
            "quantity": ("son", True, False, son),
            "is_coated": ("bool", False),
            "penoplast_id": ("id", True),
            "price_per_m3": ("son", True, False, money),
            "unit_price": ("son", False, False, money),
            "unit_price_for_volume": ("son", True, False, money),
            "loy_kg": ("son", False, False, son),
            "recipe_id": ("id", True),
            "notes": ("matn", False, matn),
        },
        "StockAdjust": {
            "quantity": ("son", False, True, son),
            "reason": ("matn", False, matn),
        },
        "Loss": {
            "finished_product_id": ("id", False),
            "quantity": ("son", False, True, son),
            "reason": ("matn", False, matn),
            # kech53 (13-band, 1-qadam): ixtiyoriy brak bosqichi
            "brak_bosqich": ("tanlov", True, _BRAK_BOSQICHI),
            # kech56 (13-band, 7-qadam): ixtiyoriy sabab va javobgar hodim
            "brak_sabab": ("tanlov", True, _BRAK_SABABI),
            "brak_javobgar_id": ("id", True),
        },
        "ProductionBrak": {
            "finished_product_id": ("id", False),
            "brak_qty": ("son", False, True, son),
            "notes": ("matn", False, matn),
            # kech53 (13-band, 1-qadam): ixtiyoriy brak bosqichi
            "brak_bosqich": ("tanlov", True, _BRAK_BOSQICHI),
            # kech56 (13-band, 7-qadam): ixtiyoriy sabab va javobgar hodim
            "brak_sabab": ("tanlov", True, _BRAK_SABABI),
            "brak_javobgar_id": ("id", True),
        },
        "Sale": dict(sotuv, **{
            "buyer_name": ("matn", False, 150),
            "payment_method": ("tanlov", False, _TOLOV_USULI),
            "notes": ("matn", False, matn),
            "master_id": ("id", True),
            "confirm_below_cost": ("bool", False),
        }),
        "SaleBatchItem": dict(sotuv),
        "SaleBatch": {
            "items": ("royxat", "SaleBatchItem", 1, 200),
            "buyer_name": ("matn", False, 150),
            "payment_method": ("tanlov", False, _TOLOV_USULI),
            "notes": ("matn", False, matn),
            "agreed_amount": ("son", True, False, money),
            "master_id": ("id", True),
            "confirm_below_cost": ("bool", False),
        },

        # ── 17b (2026-09-21): ombor kirimi, kirim hujjati, retseptlar ──
        # Maydonlar `suppliers.html` (632), `supplier_receive.html` (861) va
        # `recipes.html` (395/408) YUBORADIGAN tanalarga AYNAN mos: UI ning
        # birorta qonuniy so'rovi rad etilmaydi.
        "Purchase": {
            "quantity": ("son", False, True, son),
            "price_per_unit": ("son", False, True, money),
            "notes": ("matn", False, matn),
            "supplier_id": ("id", True),
            # Server `is_credit` ni O'ZI hisoblaydi (main.py) — tanadagisi
            # e'tiborsiz qoladi, lekin sxemada bor, shuning uchun turi
            # tekshiriladi.
            "is_credit": ("bool", False),
            "paid_now": ("son", True, False, money),
            "transport_cost": ("son", True, False, money),
            "transport_payer": ("tanlov", True, _TRANSPORT_TOLOVCHI),
            # Penoplast uchun "1 blok necha m³" — MUSBAT bo'lishi shart.
            # `Infinity` bu yerdan o'tib, `/api/penoplasts` sahifasini
            # BUTUNLAY buzardi (o'lchandi: 500 va qiymat SAQLANARDI).
            # UI penoplast bo'lmasa `null` yuboradi.
            "volume_per_unit": ("son", True, True, son),
            "payment_due_date": ("sana", True),
            "is_opening_stock": ("bool", False),
        },
        "ReceiptItem": {
            "inventory_id": ("id", False),
            "quantity": ("son", False, True, son),
            "price_per_unit": ("son", False, True, money),
            "volume_per_unit": ("son", True, True, son),
            "is_opening_stock": ("bool", False),
            "notes": ("matn", False, matn),
        },
        "Receipt": {
            "items": ("royxat", "ReceiptItem", 1, 200),
            "supplier_id": ("id", True),
            # `inventory_receipts.document_number` — String(50).
            # 500 belgilik hujjat raqami PostgreSQL da COMMIT da yiqilardi.
            "document_number": ("matn", False, 50),
            "paid_now": ("son", True, False, money),
            "transport_cost": ("son", True, False, money),
            "tushirish_cost": ("son", True, False, money),
            "yuklash_cost": ("son", True, False, money),
            "boshqa_cost": ("son", True, False, money),
            "add_to_cost": ("bool", False),
            "notes": ("matn", False, matn),
            "production_type": ("tanlov", True, _ISHLAB_CHIQARISH_TURI),
        },
        "RecipeIngredient": {
            "inventory_id": ("id", False),
            "quantity_kg": ("son", False, True, son),
        },
        # 17c (2026-09-21): ta'minotchiga to'lov — `suppliers.html` 906 va
        # `supplier_receive.html` 518 AYNAN shu to'rt kalitni yuboradi.
        # `supplier_id` tanada bo'lishi mumkin (UI yuboradi), lekin marshrut
        # uni YO'L parametridan oladi.
        "SupplierPayment": {
            "supplier_id": ("id", True),
            "amount": ("son", False, True, money),
            "notes": ("matn", False, matn),
            "confirm_overpay": ("bool", False),
        },
        "RecipeBody": {
            "name": ("matn", True, 100),
            "batch_size_kg": ("son", True, True, son),
            "notes": ("matn", False, matn),
            # Kamida 1 ta tarkibiy qism — UI ham shuni talab qiladi
            # ("Kamida bitta tarkibiy qism kiriting!"). Ilgari bo'sh
            # ro'yxat bilan PUT yuborilsa retsept TARKIBI BUTUNLAY
            # o'chib ketardi (o'lchandi).
            "ingredients": ("royxat", "RecipeIngredient", 1, 100),
        },
        # 17e (2026-09-22): kunlik xarajat tranzaksiyasi — `finance.html`
        # (qo'shish VA tahrirlash), `kunlik_xarajat.html`, `debts.html`
        # (majburiyatni to'lash) AYNAN shu besh kalitdan foydalanadi.
        # `expense_transactions`: category String(30), amount Numeric(12,2),
        # notes Text, production_type String(20). Kategoriya ERKIN matn —
        # `debts.html` majburiyat KODINI (≤ 30) kategoriya qilib yuboradi.
        "ExpenseTransaction": {
            "date": ("sana", True),
            "category": ("matn", True, _XARAJAT_KATEGORIYA_MAX),
            "amount": ("son", False, True, money),
            "notes": ("matn", False, matn),
            "production_type": ("tanlov", True, _ISHLAB_CHIQARISH_TURI),
        },
        # 17e: buyurtmaning kelishilgan summasi (`orders.html`
        # `editAgreedAmount` — faqat shu bitta kalit). MUSBAT: 0 ikki xil
        # talqin qilinardi (chegirma 100 %, lekin `_update_order_payment_status`
        # 0 ni "berilmagan" deb JAMI summaga qaytaradi); UI ham 0 ni rad etadi.
        "OrderAgreed": {
            "agreed_amount": ("son", False, True, money),
        },

        # ── 17f (2026-09-22) ──
        # Kirish transporti (`POST /api/transport-expenses`). Hech bir sahifa
        # bu marshrutga YOZMAYDI (faqat API) — shuning uchun qoidalar ustunlardan:
        # amount Numeric(12,2), materials_note String(255), notes Text,
        # production_type String(20) (kunlik xarajat bilan bir xil tanlov).
        "TransportExpense": {
            "amount": ("son", False, True, money),
            "materials_note": ("matn", False, 255),
            "notes": ("matn", False, matn),
            "production_type": ("tanlov", True, _ISHLAB_CHIQARISH_TURI),
        },
        # Mijoz to'lovi (`POST /api/payments`) — `orders.html` (to'lov oynasi
        # va zaklat), `debts.html` (qarzni yopish) AYNAN shu kalitlarni
        # yuboradi. Ilgari noto'g'ri `payment_type` / `payment_method` JIMGINA
        # "partial" / "naqd" ga aylanardi, `true` → 1 so'mlik to'lov,
        # `"5"` → 5 so'm, `order_id: true` → 1-buyurtma; PostgreSQL da
        # `Infinity` / `1e20` takror-tekshiruv so'rovida 500 (O'LCHANGAN).
        "Payment": {
            "order_id": ("id", False),
            "amount": ("son", False, True, money),
            "payment_type": ("tanlov", True, _TOLOV_TURI),
            "payment_method": ("tanlov", True, _TOLOV_USULI_MIJOZ),
            "received_by": ("matn", False, 100),
            "notes": ("matn", False, matn),
            "confirm_overpay": ("bool", False),
        },
        # Sovg'a davri bosqichi (`kpi.html` — faqat shu ikki kalit).
        # `gift_period_tiers.gift_name` String(100), threshold Numeric(12,2).
        "GiftTier": {
            "gift_name": ("matn", True, 100),
            "threshold_amount": ("son", False, True, money),
        },
        "GiftPeriodOpen": {
            "tiers": ("royxat", "GiftTier", 1, 50),
        },
        # 17g (2026-09-22) — qaytarish (`POST /api/returns`). `returns.html`
        # (qaytarish oynasi va "brak" oynasi) AYNAN shu kalitlarni yuboradi.
        # HAQIQIY PostgreSQL da O'LCHANGAN (asl kod = 17f): miqdor manfiy / 0 /
        # `1e20` — saqlanardi; `Infinity` / `NaN` — SAQLANARDI va tayyor
        # mahsulot qoldig'ini cheksiz / "son emas" qilib qo'yardi (javob 500,
        # keyin qoldiqni JSON ga aylantirib bo'lmaydi); summa `NaN` — bazaga
        # "NaN" bo'lib yozilardi; `Infinity` / `1e20` — 500; nom 151 belgi,
        # birlik 21 belgi — 500; `true` → 1, `"2"` matni — qabul.
        # `ReturnItem`: item_name String(150), unit String(20), refund Numeric(12,2).
        "Return": {
            "order_id": ("id", False),
            "order_item_id": ("id", True),
            "item_name": ("matn", True, 150),
            "quantity": ("son", False, True, son),
            "unit": ("matn", False, 20),
            "reason": ("tanlov", False, _QAYTARISH_SABABI),
            "refund_amount": ("son", True, False, money),
            "to_stock": ("bool", False),
            "notes": ("matn", False, matn),
            "coating_applied": ("bool", False),
            "gips_kg_used": ("son", True, False, son),
            # kech53 (13-band, 1-qadam): ixtiyoriy brak bosqichi (faqat "Brak")
            "brak_bosqich": ("tanlov", True, _BRAK_BOSQICHI),
            # kech56 (13-band, 7-qadam): ixtiyoriy sabab va javobgar hodim (faqat "Brak")
            "brak_sabab": ("tanlov", True, _BRAK_SABABI),
            "brak_javobgar_id": ("id", True),
        },
        # 17g — yetkazish (`POST /api/deliveries`). `orders.html` ("Yetkazish"
        # oynasi va "Bir yo'la to'liq topshirish") AYNAN shu kalitlarni
        # yuboradi; `confirm_overpay` — 409 tasdig'idan keyingi qayta yuborish.
        # O'LCHANGAN: to'lov / transport `Infinity` / `1e20` — 500; to'lov `true`
        # → 1 so'm, `"7"` matni; noma'lum usul JIMGINA "naqd"; qabul qiluvchi
        # 101, tashuvchi 151, to'lovchi 21 belgi — 500.
        # `Delivery`: received_by String(100), transport_carrier String(150),
        # transport_payer String(20), transport_cost Numeric(12,2).
        "Delivery": {
            "order_id": ("id", False),
            # kech25: chegara 500 edi — O'LCHANGAN: 501 detalli buyurtmada
            # "Tayyor" belgisi (servisdagi avtomatik yetkazish) 500 xato,
            # "bir yo'la to'liq topshirish" 400 berardi (17f da ishlardi;
            # buyurtma detallari soni cheklanmagan). Bir detal ikki marta
            # berilmagani uchun (pastda) haqiqiy yetkazish qatorlari soni
            # buyurtma detallari sonidan oshmaydi; bu chegara faqat
            # bema'ni tanaga qarshi.
            "items": ("royxat", "DeliveryItem", 1, 100_000),
            "received_by": ("matn", False, 100),
            "notes": ("matn", False, matn),
            "transport_carrier": ("matn", False, 150),
            "transport_cost": ("son", True, False, money),
            "transport_payer": ("tanlov", True, _YETKAZISH_TOLOVCHI),
            "payment_amount": ("son", True, False, money),
            "payment_method": ("tanlov", True, _TOLOV_USULI_MIJOZ),
            "confirm_overpay": ("bool", False),
        },
        "DeliveryItem": {
            "order_item_id": ("id", False),
            "quantity": ("son", False, True, son),
        },
    }


# model → {majburiy maydon: eng kam uzunlik (bo'shliqsiz, matn uchun) yoki None}
_VAL_MAJBURIY = {
    "Produce": {"name": 2},
    "StockAdjust": {"quantity": None},
    "Loss": {"finished_product_id": None, "quantity": None},
    "ProductionBrak": {"finished_product_id": None, "brak_qty": None},
    "Sale": {"finished_product_id": None, "quantity": None, "unit_price": None},
    "SaleBatchItem": {"finished_product_id": None, "quantity": None, "unit_price": None},
    "SaleBatch": {"items": None},
    # 17b (2026-09-21)
    "Purchase": {"quantity": None, "price_per_unit": None},
    "ReceiptItem": {"inventory_id": None, "quantity": None, "price_per_unit": None},
    "Receipt": {"items": None},
    "RecipeIngredient": {"inventory_id": None, "quantity_kg": None},
    "RecipeBody": {"name": 1, "ingredients": None},
    # 17c (2026-09-21)
    "SupplierPayment": {"amount": None},
    # 17e (2026-09-22)
    "ExpenseTransaction": {"category": 1, "amount": None},
    "OrderAgreed": {"agreed_amount": None},
    # 17f (2026-09-22)
    "TransportExpense": {"amount": None},
    "Payment": {"order_id": None, "amount": None},
    "GiftTier": {"gift_name": 1, "threshold_amount": None},
    "GiftPeriodOpen": {"tiers": None},
    # 17g (2026-09-22)
    "Return": {"order_id": None, "item_name": 1, "quantity": None, "reason": None},
    "Delivery": {"order_id": None, "items": None},
    "DeliveryItem": {"order_item_id": None, "quantity": None},
}


def _takror_material_yoq(qatorlar, kalit: str, ro_yxat_nomi: str,
                         nima: str = "material"):
    """17b (2026-09-21): bitta materialni ro'yxatda IKKI MARTA ko'rsatishni
    rad etadi.

    Retseptda bu ANIQ xato: `services.deduct_loy_ingredients` har qatorni
    alohida ayiradi, ya'ni bir material ikki qatorda bo'lsa ombordan IKKI
    BARAVAR yechiladi, retsept oynasida esa bu ikki alohida qator bo'lib
    ko'rinadi (o'lchandi: 200 va ikkala qator ham saqlanardi).

    ⚠ Kirim HUJJATIDA (`Receipt`) bu ATAYLAB tekshirilmaydi: bir xil
    materialni bitta hujjatda ikki xil narxda olish MUMKIN (ikki partiya),
    va har qator o'z o'rtacha narxini to'g'ri hisoblaydi."""
    korilgan = set()
    for i, q in enumerate(qatorlar):
        v = q.get(kalit) if isinstance(q, dict) else getattr(q, kalit, None)
        if v in korilgan:
            raise ValueError(f"'{ro_yxat_nomi}' {i + 1}-qator: bu {nima} "
                             f"ro'yxatda allaqachon bor")
        korilgan.add(v)


def _clean_val(model: str, data) -> dict:
    """17-band tanasini QAT'IY tekshiradi va tozalangan nusxasini qaytaradi.
    `data` — xom JSON (marshrut) yoki `model_dump(exclude_unset=True)`
    (crud ildizi). Noma'lum kalit, noto'g'ri tur, NaN / cheksizlik, manfiy
    yoki chegaradan katta son, ustun sig'imidan uzun matn, noto'g'ri tanlov —
    `ValueError` (marshrut → 400), hech narsa yozilmaydi."""
    toza = _clean_by_rules(_val_rules()[model], {}, data, "Noma'lum maydon: ")
    for key, eng_kam in _VAL_MAJBURIY.get(model, {}).items():
        if toza.get(key) is None:
            raise ValueError(f"'{key}' kiritilishi shart")
        if eng_kam and len(toza[key].strip()) < eng_kam:
            raise ValueError(f"'{key}' kamida {eng_kam} belgidan iborat bo'lishi kerak")
    # 17b: retsept tarkibida bir material IKKI MARTA bo'lmasin (kirim
    # hujjatida — ataylab RUXSAT, sababi `_takror_material_yoq` izohida).
    if model == "RecipeBody":
        _takror_material_yoq(toza.get("ingredients") or [], "inventory_id",
                             "ingredients")
    # 17g (kech25, 2026-09-22): yetkazishda BIR detal ikki qatorda bo'lmasin.
    # O'LCHANGAN (asl kod = 17f va 17g WIP): 10 metrlik detal [6, 6] qatorlar
    # bilan berilganda 200 qaytib, 12 metr topshirilgan deb yozilardi —
    # `create_delivery` har qatorni detalning bazadagi qoldig'i bilan ALOHIDA
    # solishtiradi (shu so'rovdagi boshqa qatorlarni hisobga olmaydi).
    # `orders.html` har detalni bir marta yuboradi; servis ("Tayyor")
    # ham har detal uchun bitta qator tuzadi.
    if model == "Delivery":
        _takror_material_yoq(toza.get("items") or [], "order_item_id", "items",
                             nima="detal")
    # 17b: miqdor va narx ALOHIDA chegaradan o'tsa ham, KO'PAYTMASI
    # `InventoryPurchase.total_amount` (Numeric(12,2)) sig'imidan oshishi
    # mumkin (o'lchandi: 1e9 × 1e6 = 1e15 → 200, PostgreSQL da COMMIT da
    # 500). Shuning uchun jami summa ham tekshiriladi.
    if model in ("Purchase", "ReceiptItem"):
        _miq, _nar = toza.get("quantity"), toza.get("price_per_unit")
        if _miq is not None and _nar is not None:
            # 17g: jami bazaga YAXLITLANGAN narxdan hisoblanib yoziladi
            # (`_xarid_narx_jami`), shuning uchun sig'im ham SHU jamiga
            # nisbatan tekshiriladi — xom ko'paytma sig'im ichida bo'lsa-da,
            # yaxlitlangan narx bilan oshib ketishi mumkin (2 ×
            # 4 999 999 999.995 → narx 5 000 000 000.00, jami 10 000 000 000.00).
            if _miq * _nar > _ORDER_ITEM_MAX_MONEY or \
                    _xarid_narx_jami(_miq, _nar)[1] > _ORDER_ITEM_MAX_MONEY:
                raise ValueError("'quantity' × 'price_per_unit' juda katta "
                                 "(jami summa sig'imdan oshdi)")
    # 17f: 0 ruxsat etilgan, lekin hosila yozuv yaratadigan pul maydonlari —
    # 0 yoki kamida 1 tiyin (sababi `_NOL_YOKI_TIYIN` izohida).
    for _nk in _NOL_YOKI_TIYIN.get(model, ()):
        _nv = toza.get(_nk)
        if _nv is not None and _nv > 0 and round(_nv, 2) < _PUL_ENG_KAM:
            raise ValueError(f"'{_nk}' 0 yoki kamida {_PUL_ENG_KAM} bo'lishi kerak "
                             "(1 tiyindan kichik summa bazada 0 ga aylanadi)")
    # 17b: "sana" qoidasi matnni `datetime` ga o'giradi, lekin bu yo'lda
    # `schemas.StockPurchase.payment_due_date` — MATN (`Optional[str]`) va
    # `_purchase_stock_no_commit` uni `strptime(..., "%Y-%m-%d")` bilan
    # o'qiydi. Shuning uchun tekshiruvdan keyin AYNAN shu shaklga
    # qaytariladi (sana haqiqiyligi allaqachon tasdiqlangan).
    if model == "Purchase" and isinstance(toza.get("payment_due_date"), datetime):
        toza["payment_due_date"] = toza["payment_due_date"].strftime("%Y-%m-%d")
    return toza


def _val_dump(data, model: str) -> dict:
    """crud ildizi uchun: tana → faqat BERILGAN maydonlar lug'ati.
    pydantic obyekt — `model_dump(exclude_unset=True)`; boshqa obyekt
    (ichki chaqiruv / test) — `model` qoidalaridagi atributlari; ichki
    ro'yxat qatorlari ham lug'atga aylantiriladi."""
    if isinstance(data, dict):
        return data
    if hasattr(data, "model_dump"):
        return data.model_dump(exclude_unset=True)
    qoidalar = _val_rules()[model]
    out = {}
    for k, q in qoidalar.items():
        if not hasattr(data, k):
            continue
        v = getattr(data, k)
        if q[0] == "royxat" and isinstance(v, list):
            v = [_val_dump(el, q[1]) for el in v]
        out[k] = v
    return out


def _penoplastmi(item) -> bool:
    """Material penoplastmi — `services.get_default_penoplast` bilan BIR XIL
    ta'rif: `is_penoplast` belgisi YOKI nomida \"penoplast\" (belgisi
    qo'yilmagan eski yozuvlar uchun tizimning o'zi shunday hisoblaydi)."""
    if getattr(item, "is_penoplast", False):
        return True
    return "penoplast" in (getattr(item, "item_name", "") or "").lower()


def _fp_tayyormi(fp) -> bool:
    """Mahsulot OMBORDAN CHIQADIGAN amal (sotish, savatcha, zaxiradan
    kamaytirish) uchun tayyormi. Jarayondagi (IN_PROGRESS) — yo'q: UI ham
    bu tugmalarni faqat tayyoriga beradi (`finished.html` — jarayondagida
    faqat \"✓ Sotuv\"). Ishlab chiqarish amallari (qo'shish, ishlab chiqarish
    braki) jarayondagiga ham RUXSAT — ular ishlab chiqarishning o'zi."""
    from models import ProductionStatus
    # UI bilan AYNAN bir xil: `inProgress = source === 'produced' &&
    # production_status === 'in_progress'`. Qaytarilgan (RETURNED) mahsulot
    # holati belgilanmay yaratiladi (bazada standart IN_PROGRESS) — u doim
    # sotiladi.
    return not (fp.source == StockSource.PRODUCED
                and fp.production_status == ProductionStatus.IN_PROGRESS)


_FP_JARAYONDA_XABAR = "Mahsulot hali ishlab chiqarilmoqda — avval \"Tayyor\" deb belgilang"


def _clean_order_item_update(item_data) -> dict:
    """Detal tahriri tanasini tekshiradi va tozalangan nusxasini qaytaradi.

    Noma'lum yoki ruxsat etilmagan kalit, noto'g'ri tur yoki chegara
    tashqarisidagi qiymat — `ValueError` (marshrut uni 400 ga aylantiradi).
    Hech narsa yozilmasdan OLDIN chaqiriladi."""
    _son = _json_son
    if not isinstance(item_data, dict):
        raise ValueError("Noto'g'ri so'rov")
    notogri = sorted(str(k)[:40] for k in item_data
                     if k not in _ORDER_ITEM_UPDATE_FIELDS)
    if notogri:
        raise ValueError("Bu maydonni o'zgartirib bo'lmaydi: " + ", ".join(notogri[:10]))

    toza = {}
    for key, value in item_data.items():
        if key == "name":
            if not isinstance(value, str) or len(value.strip()) < 2:
                raise ValueError("Detal nomi kamida 2 belgi bo'lishi kerak")
            toza[key] = value.strip()
        elif key == "category":
            if value is not None and not isinstance(value, str):
                raise ValueError("'category' matn bo'lishi kerak")
            toza[key] = value
        elif key == "notes":
            if value is not None and not isinstance(value, str):
                raise ValueError("'notes' matn bo'lishi kerak")
            toza[key] = value
        elif key == "is_coated":
            if not isinstance(value, bool):
                raise ValueError("'is_coated' true yoki false bo'lishi kerak")
            toza[key] = value
        elif key == "penoplast_id":
            if value is None:
                toza[key] = None
            elif isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("'penoplast_id' musbat butun son bo'lishi kerak")
            else:
                toza[key] = value
        elif key in ("width", "thickness", "length"):
            toza[key] = _son(key, value, bosh_mumkin=True, musbat=False)
        elif key == "quantity":
            toza[key] = _son(key, value, bosh_mumkin=False, musbat=True)
        elif key == "unit_price":
            toza[key] = _son(key, value, bosh_mumkin=False, musbat=False,
                             chegara=_ORDER_ITEM_MAX_MONEY)
        elif key in ("unit_price_for_volume", "price_per_m3"):
            toza[key] = _son(key, value, bosh_mumkin=True, musbat=False,
                             chegara=_ORDER_ITEM_MAX_MONEY)
    return toza


def update_order_item(db: Session, item_id: int, item_data: dict,
                      company_id: int = None) -> Optional[OrderItem]:
    """Buyurtma detalini yangilash — ombor farq bo'yicha to'g'rilanadi.

    2026-09-21 (13-sizish): faqat `_ORDER_ITEM_UPDATE_FIELDS` dagi maydonlar
    o'zgaradi; boshqa kalit yoki noto'g'ri qiymat — `ValueError`.
    `penoplast_id` HAR DOIM detalning O'Z korxonasiga QAT'IY tekshiriladi
    (`company_id` berilmasa ham) — begona material 404."""
    import services

    _q = db.query(OrderItem).filter(OrderItem.id == item_id)
    if company_id is not None:
        _q = _q.filter(OrderItem.company_id == company_id)
    db_item = _q.first()
    if not db_item:
        return None
    # kech41 (5-bo'lim 14-band, K41-1) — QULF (101, buyurtma), yetkazish /
    # to'lov / qaytarish bilan BIR fazo. HAQIQIY PostgreSQL da O'LCHANGAN
    # (asl kod, `work/probe41.py`, 3 / 3 urinish): qulfsiz "topshirilgan"
    # tekshiruvi bir vaqtdagi yetkazishni ko'rmasdi —
    # detal 10 → 6 ga kamaytirilayotganda 8 topshirilsa, ikkalasi saqlanib
    # detal 6, topshirilgan 8 bo'lib qolardi (ikkala tartibda ham).
    # Naqsh `create_delivery` / `delete_delivery` dagi bilan bir xil:
    # yozilmagan o'zgarish yo'qolmasin (`flush`), qulf, so'ng qulf ostida
    # bazadan QAYTA o'qiladi (`expire_all`).
    if db_item.order_id is not None:
        db.flush()
        _pul_qulfi(db, 101, db_item.order_id)
        db.expire_all()
        db_item = _q.first()
        if not db_item:
            return None

    order = db_item.order
    # MUHIM (2026-09 audit): o'chirilgan buyurtmaning detalini tahrirlab
    # bo'lmaydi — aks holda order_qty_normalized/delivery_percent o'chirish
    # va tiklash orasida o'zgarib, ombor hisobi (Loy/tayyor mahsulot
    # qaytarish-qayta yechish simmetriyasi) buzilib qolishi mumkin.
    if order and order.is_deleted:
        return None
    is_draft = order.status == OrderStatus.DRAFT if order else False

    # 13-sizish: tana HECH NARSA yozilmasdan OLDIN tekshiriladi.
    item_data = _clean_order_item_update(item_data)
    if item_data.get("penoplast_id"):
        _require_inventory_of_company(db, [item_data["penoplast_id"]],
                                      db_item.company_id)

    # Topshirilgandan kam qilib bo'lmaydi.
    # 2026-09-21: ilgari `None` qaytarardi → marshrut "Detal topilmadi"
    # (404) derdi — foydalanuvchi uchun noto'g'ri sabab. Endi aniq xabar.
    # kech60 (57-band): omborga ortiqcha qo'yilgan qism ham chiqqan — undan kam qilib bo'lmaydi
    # (aks holda kamaytirish uning xomashyosini IKKINCHI marta qaytarardi).
    delivered = db_item.delivered_qty
    _ortiqcha_u = db_item.ortiqcha_qty
    if delivered + _ortiqcha_u > 0.001:
        cat = (item_data.get('category') or db_item.category or '').lower()
        new_qty = float(item_data.get('length') or db_item.length or 0) if cat == 'profil' \
                  else float(item_data.get('quantity') or db_item.quantity or 0)
        if new_qty < delivered + _ortiqcha_u - 0.001:
            if _ortiqcha_u > 0.001:
                raise ValueError(
                    f"Topshirilgan ({round(delivered, 3)}) va omborga ortiqcha qaytarilgan "
                    f"({round(_ortiqcha_u, 3)}) miqdordan kam qilib bo'lmaydi "
                    f"(kamida {round(delivered + _ortiqcha_u, 3)})")
            raise ValueError(
                f"Topshirilgan miqdordan ({round(delivered, 3)}) kam qilib bo'lmaydi")

    # Eski holat snapshot
    # MUHIM (2026-09 audit): "finished_product_id" va "sub_details" ham
    # SHART qo'shilishi kerak — bo'lmasa, _FakeItem/_item_volume_m3 buni
    # oddiy xomashyo detali deb hisoblab, (a) "Tayyor mahsulotdan"
    # tanlangan detal uchun HECH QACHON ombordan chiqmagan hajmni omborga
    # xato qo'shib yuboradi, (b) ichki qo'shimcha detal borligini
    # butunlay unutib, uning hajmini diffdan tashlab ketadi.
    old_sub_details = [{
        "category": s.category, "width": s.width, "thickness": s.thickness,
        "length": s.length, "quantity": s.quantity,
    } for s in (db_item.sub_details or [])]
    old_snap = [{
        "category": db_item.category,
        "width": db_item.width,
        "thickness": db_item.thickness,
        "length": db_item.length,
        "quantity": float(db_item.quantity or 1),
        "unit_price": float(db_item.unit_price or 0),
        "penoplast_id": db_item.penoplast_id,
        "finished_product_id": db_item.finished_product_id,
        "sub_details": old_sub_details,
    }]

    for field, value in item_data.items():
        if hasattr(db_item, field):
            setattr(db_item, field, value)

    db_item.total_price = float(db_item.unit_price or 0) * float(db_item.quantity or 1)
    db.flush()

    # Yangi holat snapshot — "sub_details" bu funksiya orqali o'zgartirilmaydi
    # (item_data bunday maydonni yubormaydi), shuning uchun ESKISI bilan BIR
    # XIL qoladi (aks holda diff ularni "yo'qolgan" deb hisoblab, hajmini
    # noto'g'ri omborga qaytarib yuborardi).
    new_snap = [{
        "category": db_item.category,
        "width": db_item.width,
        "thickness": db_item.thickness,
        "length": db_item.length,
        "quantity": float(db_item.quantity or 1),
        "unit_price": float(db_item.unit_price or 0),
        "penoplast_id": db_item.penoplast_id,
        "finished_product_id": db_item.finished_product_id,
        "sub_details": old_sub_details,
    }]

    # Omborni farq bo'yicha to'g'rilaymiz
    if not is_draft:
        services.adjust_inventory_diff(db, old_snap, new_snap, order_id=db_item.order_id,
                                       company_id=db_item.company_id, commit=False)

    # Order summasi
    if order:
        order.total_amount = sum(float(it.total_price or 0) for it in order.items)
        db.flush()
        db.refresh(order)
        _update_order_payment_status(db, order)

    db.commit()
    db.refresh(db_item)
    return db_item


def record_cash_transaction(db: Session, category: str, amount: float, notes: str = None,
                           performed_by: str = None, company_id: int = None):
    """Kassaga qo'lda ta'sir qiladigan yozuv qo'shadi (boshlang'ich balans,
    Usta KPI to'landi, Ehson to'landi). amount — musbat (kirim) yoki
    manfiy (chiqim) bo'lishi mumkin."""
    from models import CashTransaction
    # M6 (2026-09-18) — TENANT: `CashTransaction`da ota-FK yo'q, shuning
    # uchun `_tenant_guard` uni to'ldira olmaydi — company_id ANIQ
    # berilmasa yozuv bazadagi vaqtinchalik DEFAULT 1 ga tushib qolardi.
    tx = CashTransaction(company_id=company_id, category=category, amount=amount,
                         notes=notes, performed_by=performed_by)
    db.add(tx)
    db.commit()
    return tx


def get_cash_transactions(db: Session, limit: int = 100, company_id: int = None) -> List:
    """Kassaga qo'lda qilingan yozuvlar tarixi (M6 — tenant-safe)."""
    from models import CashTransaction
    q = db.query(CashTransaction)
    if company_id is not None:
        q = q.filter(CashTransaction.company_id == company_id)
    return q.order_by(CashTransaction.created_at.desc()).limit(limit).all()


def delete_cash_transaction(db: Session, tx_id: int, company_id: int = None) -> bool:
    """Kassaga qo'lda qo'shilgan yozuvni o'chiradi (faqat Admin).

    2026-09-18 — bu funksiya M6 sinovidan qolgan yozuvlarni tozalash uchun
    qo'shildi: ilgari `CashTransaction` uchun o'chirish yo'li UMUMAN yo'q
    edi (faqat `factory_reset_all_data()` butun bazani tozalash orqali),
    shuning uchun noto'g'ri kiritilgan kassa yozuvini tuzatib bo'lmasdi.

    TENANT: yozuv FAQAT shu korxonadan topiladi (aks holda False → 404).
    Kassa balansi alohida saqlanmaydi — u har safar joriy yozuvlardan
    qayta hisoblanadi, shuning uchun bu yerda boshqa hech narsani
    yangilash shart emas."""
    from models import CashTransaction
    q = db.query(CashTransaction).filter(CashTransaction.id == tx_id)
    if company_id is not None:
        q = q.filter(CashTransaction.company_id == company_id)
    tx = q.first()
    if not tx:
        return False
    db.delete(tx)
    db.commit()
    return True


def get_setting(db: Session, key: str, default: str = None,
                company_id: int = None) -> str:
    """Korxona sozlamasini o'qiydi (masalan Ehson foizi).

    2026-09-18 — M8/F1a: qidiruv FAQAT `key` bo'yicha edi, ya'ni ikki
    korxonali bazada bir korxona boshqasining sozlamasini o'qib olardi.
    Endi `(company_id, key)` juftligi bo'yicha."""
    from models import CompanySetting
    q = db.query(CompanySetting).filter(CompanySetting.key == key)
    if company_id is not None:
        q = q.filter(CompanySetting.company_id == company_id)
    row = q.first()
    return row.value if row else default


def set_setting(db: Session, key: str, value: str, company_id: int = None):
    """Korxona sozlamasini saqlaydi/yangilaydi.

    2026-09-18 — M8/F1a: qidiruv ham, yangi yozuv ham korxona bilan
    bog'lanadi. Ilgari faqat `key` bo'yicha qidirilardi — bu o'qish
    sizishi emas, MA'LUMOT BUZILISHI edi: B korxona Ehson foizini
    o'zgartirsa, A korxonaning qatori qayta yozilardi."""
    from models import CompanySetting
    q = db.query(CompanySetting).filter(CompanySetting.key == key)
    if company_id is not None:
        q = q.filter(CompanySetting.company_id == company_id)
    row = q.first()
    if row:
        row.value = value
    else:
        row = CompanySetting(company_id=company_id, key=key, value=value)
        db.add(row)
    db.commit()


def log_activity(db: Session, action: str, entity_type: str, entity_id: int,
                  entity_label: str = None, performed_by: str = None,
                  old_value: str = None, new_value: str = None,
                  company_id: int = None):
    """Muhim amallarni audit uchun yozib boradi (o'chirish/tiklash/yaratish/
    tahrirlash). old_value/new_value — ixtiyoriy, qisqa tavsif (masalan
    "Jami: 850 000 so'm, 3 ta detal") — har bir maydonni emas, faqat
    tezda "nima o'zgargani"ni ko'rsatish uchun."""
    from models import ActivityLog
    # M7 (2026-09-18) — TENANT: `ActivityLog`da company_id ustuni bor, lekin
    # ota-FK yo'q va model `_TENANT_RULES` da emas — shuning uchun qiymat
    # ANIQ berilmasa yozuv bazadagi vaqtinchalik DEFAULT 1 ga tushardi.
    # Ya'ni B korxonaning audit izi A ning bazasiga yozilardi, B da esa
    # audit izi umuman bo'lmasdi (lokal ikki korxonali sinovda tasdiqlangan).
    entry = ActivityLog(
        company_id=company_id,
        action=action, entity_type=entity_type, entity_id=entity_id,
        entity_label=entity_label, performed_by=performed_by,
        old_value=old_value, new_value=new_value
    )
    db.add(entry)
    db.commit()


def get_activity_log(db: Session, limit: int = 100, company_id: int = None) -> List:
    """So'nggi audit yozuvlari (M7 — tenant-safe)."""
    from models import ActivityLog
    q = db.query(ActivityLog)
    if company_id is not None:
        q = q.filter(ActivityLog.company_id == company_id)
    return q.order_by(ActivityLog.created_at.desc()).limit(limit).all()


def _company_of_username(db: Session, username: str):
    """Login vaqtida korxonani SERVER tomonda aniqlaydi (M7).

    `User.username` butun tizim bo'yicha YAGONA (`unique=True`), shuning
    uchun foydalanuvchi nomidan korxona bir qiymatli aniqlanadi — mijoz
    yuborgan hech qanday `company_id` ga ishonilmaydi. Nom topilmasa
    (mavjud bo'lmagan hisobga urinish) None qaytadi."""
    from models import User, Employee
    if not username:
        return None
    u = db.query(User).filter(User.username == username).first()
    if u is not None:
        return getattr(u, "company_id", None)
    # 2026-09-20: xodimlar telefon raqami bilan kiradi (`/hodim/login`),
    # ya'ni bu yerga username emas, TELEFON keladi. Uni ham tekshiramiz —
    # aks holda xodimning kirish tarixi hech bir korxonaga bog'lanmay
    # qolardi. Telefon `(company_id, phone)` bo'yicha yagona.
    e = db.query(Employee).filter(Employee.phone == username).first()
    return getattr(e, "company_id", None) if e else None


def log_login_attempt(db: Session, username: str, success: bool, ip_address: str = None,
                      user_agent: str = None, company_id: int = None):
    """Tizimga kirish urinishini yozib boradi (muvaffaqiyatli yoki muvaffaqiyatsiz).

    M7 — TENANT: korxona foydalanuvchi NOMIDAN aniqlanadi (yuqoridagi
    `_company_of_username`). Nom noma'lum bo'lsa (mavjud bo'lmagan hisob)
    yozuv korxonasiz qoladi — u hech bir tenantning ro'yxatida
    ko'rinmaydi, faqat IP bo'yicha rate-limit uchun ishlatiladi."""
    from models import LoginHistory
    if company_id is None:
        company_id = _company_of_username(db, username)
    entry = LoginHistory(company_id=company_id, username=username, success=success,
                         ip_address=ip_address, user_agent=user_agent)
    db.add(entry)
    db.commit()


def check_login_rate_limit(db: Session, username: str, ip_address: str = None,
                            max_attempts: int = 5, window_minutes: int = 15) -> dict:
    """Rate limit — oxirgi `window_minutes` daqiqada, shu username YOKI shu
    IP manzildan `max_attempts` martadan ko'p MUVAFFAQIYATSIZ urinish
    bo'lgan bo'lsa, kirishni bloklaydi. Mavjud LoginHistory jadvalidan
    foydalanadi — yangi jadval kerak emas.

    Qaytaradi: {"blocked": bool, "retry_after_minutes": int}"""
    from models import LoginHistory
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)

    # M7 — TENANT: nom bo'yicha hisob (company_id, username) juftligi
    # bo'yicha olinadi. Ilgari u global edi: bir korxonada `admin` nomiga
    # 5 marta noto'g'ri urinilsa, BOSHQA korxonaning `admin`i ham bloklanardi
    # (lokal sinovda tasdiqlangan — korxonalararo DoS).
    # IP bo'yicha himoya ATAYLAB global qoladi: bitta IP dan turli
    # korxonalarga urinish ham xuddi shunday hujum.
    _uname_cid = _company_of_username(db, username)
    q = db.query(LoginHistory).filter(
        LoginHistory.success == False,
        LoginHistory.created_at >= cutoff
    )
    # Username BO'YICHA yoki IP BO'YICHA — ikkalasidan qay biri ko'proq
    # xavfli bo'lsa (masalan bitta IP'dan ko'p turli hisobga urinish, yoki
    # bitta hisobga turli joydan urinish) — shuni hisobga olamiz.
    _uq = q.filter(LoginHistory.username == username)
    if _uname_cid is not None:
        _uq = _uq.filter(LoginHistory.company_id == _uname_cid)
    by_username = _uq.count()
    by_ip = q.filter(LoginHistory.ip_address == ip_address).count() if ip_address else 0

    attempts = max(by_username, by_ip)
    if attempts >= max_attempts:
        return {"blocked": True, "retry_after_minutes": window_minutes}
    return {"blocked": False, "retry_after_minutes": 0}


def get_login_history(db: Session, limit: int = 100, company_id: int = None) -> List:
    """So'nggi kirish urinishlari (M7 — tenant-safe)."""
    from models import LoginHistory
    q = db.query(LoginHistory)
    if company_id is not None:
        q = q.filter(LoginHistory.company_id == company_id)
    return q.order_by(LoginHistory.created_at.desc()).limit(limit).all()


def log_error(db: Session, error_message: str, stack_trace: str = None,
              endpoint: str = None, method: str = None, performed_by: str = None,
              company_id: int = None):
    """Backend xatoligini yozib boradi.

    XAVFSIZLIK: bazaga ulanish/so'rov xatoliklarida, SQLAlchemy xato
    matniga (va odatda stack trace ichiga ham) SO'ROVNING BARCHA
    QIYMATLARINI (masalan session token, kelajakda boshqa maxfiy narsa)
    avtomatik qo'shib yuboradi — masalan "[parameters: ('...token...', 1)]".
    Shuning uchun bu funksiya HAR DOIM, qayerdan chaqirilishidan qat'iy
    nazar, bunday qiymatlarni yozishdan oldin yashiradi."""
    from models import ErrorLog
    import re
    _param_re = re.compile(r'\[parameters:.*?\]', re.DOTALL)
    safe_message = _param_re.sub('[parameters: YASHIRINGAN]', str(error_message))
    safe_trace = _param_re.sub('[parameters: YASHIRINGAN]', stack_trace or "")
    entry = ErrorLog(
        company_id=company_id,
        error_message=safe_message[:5000], stack_trace=safe_trace[:8000],
        endpoint=endpoint, method=method, performed_by=performed_by
    )
    db.add(entry)
    db.commit()


def get_error_logs(db: Session, limit: int = 100, company_id: int = None,
                   include_platform: bool = False) -> List:
    """So'nggi backend xatoliklari (Faza 3 — tenant-safe).

    `error_logs.company_id` ustuni qo'shilgach, filtr aniq bo'ldi:
      • korxonaga bog'langan xatolar — faqat o'sha korxonaga;
      • `company_id IS NULL` — PLATFORMA xatolari (fon vazifalari,
        ishga tushish, autentifikatsiyadan oldingi xatolar). Ularda
        tenant ma'lumoti yo'q, shuning uchun hammaga ko'rsatiladi —
        aks holda tizim egasi hech qanday xatoni ko'rmay qolardi
        (M7 dan keyin aynan shunday bo'lgan edi)."""
    from models import ErrorLog
    from sqlalchemy import or_ as _or
    q = db.query(ErrorLog)
    if company_id is not None:
        if include_platform:
            # PLATFORMA admini — o'z korxonasi + korxonaga bog'lanmagan
            # (tizim) xatolari. Faqat u tizimni tuzatadi.
            q = q.filter(_or(ErrorLog.company_id == company_id,
                             ErrorLog.company_id.is_(None)))
        else:
            # 2026-09-20 — TUZATISH: oddiy korxona admini FAQAT o'z
            # xatolarini ko'radi. Ilgari `company_id IS NULL` yozuvlari
            # ham ko'rsatilardi ("platforma xatosi" deb) — natijada yangi
            # mijoz birinchi kuni ERP ga kirib, bo'sh tizimda o'nlab
            # begona traceback ko'rdi. Traceback ichida boshqa
            # korxonaning jadval nomlari va ID lari bo'lishi ham mumkin.
            q = q.filter(ErrorLog.company_id == company_id)
    return q.order_by(ErrorLog.created_at.desc()).limit(limit).all()


def check_system_health(db: Session, company_id: int = None) -> dict:
    """Tizimdagi barcha ENUM ustunlarini tekshiradi — bazada noto'g'ri
    (masalan kichik/katta harf mos kelmaydigan) qiymat bor-yo'qligini
    aniqlaydi. MUHIM: bu tekshiruv XOM SQL orqali ishlaydi (ORM emas) —
    aks holda, agar chindan ham noto'g'ri qiymat bo'lsa, ORM so'rovining
    o'zi xato berib, tekshiruvni to'xtatib qo'yardi (aynan shu narsani
    aniqlashga harakat qilayotgan bo'lsak ham)."""
    from sqlalchemy import text
    from datetime import datetime as _dt
    from models import (UserRole, ProjectStatus, OrderType, OrderStatus, PaymentStatus,
                         ReturnReason, PayType, AdvanceRequestStatus, StockSource,
                         ProductionStatus, PaymentType, PaymentMethod)

    # M7 (2026-09-18) — TENANT: bu tekshiruv 12 ta jadvalni GLOBAL
    # skanerlab, nomuvofiqlik topilsa boshqa korxonaning `id` va nomini
    # (username, order_number, project_name, xodim/mahsulot nomi)
    # qaytarardi. Ro'yxatdagi 4-element — shu jadvalda korxona ustuni
    # bormi; hammasida `company_id` bor, shuning uchun so'rovga
    # PARAMETRLANGAN `WHERE company_id = :cid` qo'shiladi (jadval va
    # ustun nomlari — faqat quyidagi HARDCODED ro'yxatdan, foydalanuvchi
    # kiritmasi SQLga umuman tushmaydi).
    # (jadval, ustun, tekshiriladigan Enum sinfi, o'qiladigan "nom" ustuni — id yoki boshqa identifikator)
    # 5-element — korxona bo'yicha cheklash bo'lagi. Ustunning O'ZIDA
    # `company_id` bo'lmagan ikki jadval (payments, advance_requests) ota
    # jadval orqali cheklanadi. Barchasi HARDCODED; o'zgaruvchan yagona
    # qiymat — parametrlangan `:cid`.
    _DIRECT = " AND company_id = :cid"
    _VIA_ORDER = " AND order_id IN (SELECT id FROM orders WHERE company_id = :cid)"
    _VIA_EMP = " AND employee_id IN (SELECT id FROM employees WHERE company_id = :cid)"
    checks = [
        ("users", "role", UserRole, "username", _DIRECT),
        ("projects", "status", ProjectStatus, "project_name", _DIRECT),
        ("orders", "order_type", OrderType, "order_number", _DIRECT),
        ("orders", "status", OrderStatus, "order_number", _DIRECT),
        ("orders", "payment_status", PaymentStatus, "order_number", _DIRECT),
        ("return_items", "reason", ReturnReason, "item_name", _DIRECT),
        ("employees", "pay_type", PayType, "name", _DIRECT),
        ("advance_requests", "status", AdvanceRequestStatus, "id", _VIA_EMP),
        ("finished_products", "source", StockSource, "name", _DIRECT),
        ("finished_products", "production_status", ProductionStatus, "name", _DIRECT),
        ("payments", "payment_type", PaymentType, "id", _VIA_ORDER),
        ("payments", "payment_method", PaymentMethod, "id", _VIA_ORDER),
    ]

    issues = []
    check_errors = []
    for table, column, enum_cls, label_col, tenant_clause in checks:
        valid_names = [m.name for m in enum_cls]
        placeholders = ", ".join(f"'{n}'" for n in valid_names)
        try:
            _tenant_sql = tenant_clause if company_id is not None else ""
            _params = {"cid": company_id} if company_id is not None else {}
            rows = db.execute(text(
                f"SELECT id, {label_col}, {column} FROM {table} "
                f"WHERE {column} IS NOT NULL AND {column} NOT IN ({placeholders})"
                f"{_tenant_sql}"
            ), _params).fetchall()
            for r in rows:
                issues.append({
                    "table": table, "column": column, "id": r[0],
                    "label": str(r[1]), "bad_value": str(r[2]),
                    "valid_names": valid_names,
                })
        except Exception as e:
            # Jadval/ustun hali mavjud bo'lmasligi mumkin (eski deploy) —
            # tekshiruvni to'xtatmasdan davom etamiz.
            db.rollback()
            check_errors.append({"table": table, "column": column, "error": str(e)})

    return {
        "checked_at": _dt.utcnow().isoformat(),
        "total_checks": len(checks),
        "issues_found": len(issues),
        "issues": issues,
        "check_errors": check_errors,
    }


def check_financial_consistency(db: Session, company_id: int = None) -> dict:
    """Moliyaviy izchillik tekshiruvi — bazadagi hisob-kitoblar o'zaro
    to'g'ri qo'shilganmi, tekshiradi (masalan buyurtma summasi = detallar
    yig'indisimi, qarz = kelishilgan − to'langan). Bu, "Salomatlik"dagi
    ENUM tekshiruvidan FARQLI — bu yerda HISOB-KITOB (formula) natijalari
    solishtiriladi, ruxsat etilgan qiymatlar ro'yxati emas."""
    from datetime import datetime as _dt2
    from models import Order, OrderItem, Payment, Inventory, InventoryPurchase

    issues = []

    # 1) Buyurtma summasi = detallar (unit_price × quantity) yig'indisimi?
    # M7 (2026-09-18) — TENANT: bu tekshiruv butun bazani skanerlab,
    # boshqa korxonaning buyurtma raqami/detal nomi/summasini qaytarardi
    # (jonli sinovda A ning javobida "ZZZB_ORD-001" chiqqan). Endi barcha
    # so'rovlar joriy korxona bilan cheklanadi.
    def _oc(q):    # Order bo'yicha
        return q.filter(Order.company_id == company_id) if company_id is not None else q

    def _oic(q):   # OrderItem bo'yicha
        return q.filter(OrderItem.company_id == company_id) if company_id is not None else q

    orders = _oc(db.query(Order).filter(Order.is_deleted.is_(False))).all()
    for o in orders:
        items = db.query(OrderItem).filter(OrderItem.order_id == o.id).all()
        items_sum = sum(float(it.unit_price or 0) * float(it.quantity or 1) for it in items)
        total = float(o.total_amount or 0)
        diff = abs(items_sum - total)
        if diff > 1:
            issues.append({
                "type": "order_total_mismatch",
                "label": f"Buyurtma {o.order_number}",
                "detail": f"Jami summa: {total:,.0f} so'm, lekin detallar yig'indisi: {items_sum:,.0f} so'm",
                "diff": round(diff, 2),
            })

    # 2) Qarz = kelishilgan − to'langan?
    for o in orders:
        pays = db.query(Payment).filter(Payment.order_id == o.id).all()
        paid = sum(float(p.amount or 0) for p in pays)
        agreed = o.kelishilgan_summa
        debt = float(o.debt_amount or 0)
        expected_debt = agreed - paid
        diff = abs(debt - expected_debt)
        if diff > 1:
            issues.append({
                "type": "debt_mismatch",
                "label": f"Buyurtma {o.order_number}",
                "detail": f"Yozilgan qarz: {debt:,.0f} so'm, lekin kutilgan (kelishilgan−to'langan): {expected_debt:,.0f} so'm",
                "diff": round(diff, 2),
            })

    # 3) Manfiy ombor qoldig'i bormi?
    _invq = db.query(Inventory).filter(Inventory.stock_quantity < 0)
    if company_id is not None:
        _invq = _invq.filter(Inventory.company_id == company_id)
    for inv in _invq.all():
        issues.append({
            "type": "negative_stock",
            "label": inv.item_name,
            "detail": f"Ombor qoldig'i manfiy: {float(inv.stock_quantity):,.2f} {inv.unit}",
            "diff": abs(float(inv.stock_quantity)),
        })

    # 4) Xarid: miqdor × narx = jami summami?
    _ipq = db.query(InventoryPurchase)
    if company_id is not None:      # ota (material) orqali
        _ipq = _ipq.join(Inventory, Inventory.id == InventoryPurchase.inventory_id).filter(
            Inventory.company_id == company_id)
    for p in _ipq.all():
        expected = float(p.quantity or 0) * float(p.price_per_unit or 0)
        actual = float(p.total_amount or 0)
        diff = abs(expected - actual)
        if diff > 1:
            issues.append({
                "type": "purchase_total_mismatch",
                "label": p.item_name,
                "detail": f"Yozilgan summa: {actual:,.0f} so'm, lekin miqdor×narx: {expected:,.0f} so'm",
                "diff": round(diff, 2),
            })

    # 5) order_items notes'ida takroriy texnik belgi bormi? (masalan
    # 2026-08-17'da ORD-026-2'da topilgan [TERMO:...] ikki marta yozilish
    # holati kabi)
    for it in _oic(db.query(OrderItem)).all():
        notes = it.notes or ""
        for marker in ["[GISHT:"]:
            if notes.count(marker) > 1:
                issues.append({
                    "type": "duplicate_note_marker",
                    "label": f"{it.name} (buyurtma #{it.order_id})",
                    "detail": f"'{marker}' belgisi {notes.count(marker)} marta takrorlangan",
                    "diff": notes.count(marker),
                })

    # 6) Yetkazib berilgan miqdor, buyurtma qilingandan ko'pmi? (turkumga
    # qarab TO'G'RI maydonni solishtiramiz — "profil" uchun "length",
    # qolganlari uchun "quantity")
    from models import DeliveryItem
    for it in _oic(db.query(OrderItem)).all():
        cat = (it.category or '').lower()
        ordered = float(it.length or 0) if cat == 'profil' else float(it.quantity or 0)
        delivered = sum(float(di.quantity or 0) for di in
                         db.query(DeliveryItem).filter(DeliveryItem.order_item_id == it.id).all())
        if delivered > ordered + 0.01:
            issues.append({
                "type": "over_delivery",
                "label": f"{it.name} (buyurtma #{it.order_id})",
                "detail": f"Buyurtma qilingan: {ordered:.2f}, lekin topshirilgan: {delivered:.2f}",
                "diff": round(delivered - ordered, 2),
            })

    # 8) Qoralama bo'lmagan buyurtmada, narxi "0" bo'lgan detal bormi?
    # (bu, narx kiritishni unutib qo'yganini bildirishi mumkin)
    from models import OrderStatus
    for o in _oc(db.query(Order).filter(Order.is_deleted.is_(False), Order.status != OrderStatus.DRAFT)).all():
        for it in db.query(OrderItem).filter(OrderItem.order_id == o.id).all():
            if float(it.unit_price or 0) <= 0:
                issues.append({
                    "type": "zero_price_item",
                    "label": f"{it.name} (buyurtma {o.order_number})",
                    "detail": "Bu detalning narxi \"0\" — unutilib qolgan bo'lishi mumkin",
                    "diff": 0,
                })

    # 9) Egasiz to'lovlar (mavjud bo'lmagan buyurtmaga bog'langan)
    order_ids_set = {o.id for o in _oc(db.query(Order.id)).all()}
    _payq = db.query(Payment)
    if company_id is not None:      # ota (buyurtma) orqali
        _payq = _payq.join(Order, Order.id == Payment.order_id).filter(
            Order.company_id == company_id)
    for p in _payq.all():
        if p.order_id and p.order_id not in order_ids_set:
            issues.append({
                "type": "orphaned_payment",
                "label": f"To'lov #{p.id}",
                "detail": f"Mavjud bo'lmagan buyurtma (#{p.order_id})ga bog'langan — {float(p.amount or 0):,.0f} so'm",
                "diff": float(p.amount or 0),
            })

    # 10) Egasiz yetkazishlar (mavjud bo'lmagan buyurtmaga bog'langan)
    from models import Delivery
    _delq = db.query(Delivery)
    if company_id is not None:      # ota (buyurtma) orqali
        _delq = _delq.join(Order, Order.id == Delivery.order_id).filter(
            Order.company_id == company_id)
    for d in _delq.all():
        if d.order_id and d.order_id not in order_ids_set:
            issues.append({
                "type": "orphaned_delivery",
                "label": f"Yetkazish #{d.id}",
                "detail": f"Mavjud bo'lmagan buyurtma (#{d.order_id})ga bog'langan",
                "diff": 0,
            })

    return {
        "checked_at": _dt2.utcnow().isoformat(),
        "issues_found": len(issues),
        "issues": issues,
    }


def _auto_release_mrp_reservations(db: Session, order_item_ids, performed_by: str = None):
    """2026-09-17: buyurtma yoki uning biror detali o'chirilganda/bekor
    qilinganda ChaCHAQIRILADI — shu detal(lar)ga Production/MRP orqali
    band qilingan tayyor mahsulot bo'lsa, AVTOMATIK ozod qiladi (mahsulot
    o'zi YO'QOLMAYDI, faqat umumiy sotuvga qaytadi). Aks holda, band
    qilingan mahsulot ENDI HECH QACHON ozod bo'lmasdan, abadiy "yo'q"
    bo'lib qolar edi — chunki uni band qilgan buyurtma-detal endi
    mavjud emas.

    MUHIM: bu yerda commit QILINMAYDI — chaqiruvchi funksiya (delete_order/
    delete_order_item) o'zining umumiy tranzaksiyasi ichida keyinroq
    commit qiladi, shu bilan hammasi bitta atomik amal bo'lib qoladi.
    """
    from models import FinishedProduct
    if not order_item_ids:
        return
    fps = db.query(FinishedProduct).filter(
        FinishedProduct.reserved_for_order_item_id.in_(order_item_ids)
    ).all()
    for fp in fps:
        if fp.reserved_quantity:
            # kech41 (14-band): `log_activity` O'ZI `commit` qiladi — yuqoridagi
            # "commit QILINMAYDI" va'dasini buzar va `delete_order_item` /
            # `delete_order` dagi qulfni (101, buyurtma) muddatidan oldin
            # bo'shatardi (kech38 saboqi). Audit yozuvi bir xil maydonlar bilan
            # sessiyaga qo'shiladi, chaqiruvchining `commit` i bilan saqlanadi.
            from models import ActivityLog as _AL_rel
            db.add(_AL_rel(
                company_id=getattr(fp, 'company_id', None),
                action="auto_release_reservation", entity_type="finished_product",
                entity_id=fp.id, entity_label=fp.name, performed_by=performed_by,
                old_value=f"band: {fp.reserved_quantity}",
                new_value="band emas — bog'langan buyurtma/detal o'chirilgani uchun avtomatik ozod qilindi"))
        fp.reserved_quantity = 0.0
        fp.reserved_for_order_item_id = None


def delete_order(db: Session, order_id: int, soft: bool = False, performed_by: str = None) -> bool:
    """Buyurtmani o'chirish.
    soft=True bo'lsa — bazadan o'chirilmaydi, faqat 'is_deleted' belgisi qo'yiladi.
    Shu tufayli buyurtma "Buyurtmalar" ro'yxatidan yo'qoladi, lekin usta KPI'si
    va moliyaviy hisobotlarda (oylik/yillik) hisobga olinishda davom etadi —
    chunki bu joylar Order jadvalini to'g'ridan-to'g'ri, is_deleted'ga
    qaramasdan o'qiydi."""
    db_order = db.query(Order).filter(Order.id == order_id).first()
    if not db_order:
        return False
    order_num = db_order.order_number
    if soft:
        # 2026-09-17: MRP band qilingan detallar bo'lsa — avtomatik ozod
        # qilamiz (bir xil tranzaksiya ichida, pastdagi commit bilan).
        _auto_release_mrp_reservations(db, [i.id for i in db_order.items], performed_by)
        db_order.is_deleted = True
        db.commit()
        log_activity(db, "deleted", "order", order_id, order_num, performed_by,
                     company_id=getattr(db_order, 'company_id', None))
    else:
        # MUHIM: "Ombor harakatlari jurnali" (InventoryMovement) — bu buyurtmaga
        # FK orqali bog'langan, lekin bu yozuvlar TARIXIY LOG bo'lgani uchun
        # o'chirilmasligi kerak — faqat buyurtmaga bog'lanishi uziladi (order_id=NULL),
        # aks holda ma'lumotlar bazasi FK cheklovi tufayli o'chirishga yo'l qo'ymaydi.
        from models import InventoryMovement, FinishedProduct, Payment
        from production_models import ProductionOrder
        _auto_release_mrp_reservations(db, [i.id for i in db_order.items], performed_by)
        # 2026-09-18 (chuqur audit topilmasi — HAQIQIY, jonli sinovda aniqlangan
        # xato): Production/MRP orqali shu buyurtmaga bog'langan
        # ProductionOrder yozuvlari (source_order_id/source_order_item_id)
        # bo'lsa — ular ham, yuqoridagi InventoryMovement/FinishedProduct
        # kabi, TARIXIY YOZUV sifatida saqlanib qoladi (o'chirilmaydi), faqat
        # bog'lanishi uziladi. Bu qo'shilmagan bo'lsa, PostgreSQL FK cheklovi
        # ("production_orders_source_order_id_fkey") ushbu buyurtmani
        # o'chirishning O'ZINI ham butunlay bloklab, 500-xato berardi —
        # bu real sinovda dalili bilan aniqlandi.
        db.query(ProductionOrder).filter(ProductionOrder.source_order_id == order_id).update(
            {"source_order_id": None, "source_order_item_id": None}
        )
        db.query(InventoryMovement).filter(InventoryMovement.order_id == order_id).update(
            {"order_id": None}
        )
        db.query(FinishedProduct).filter(FinishedProduct.from_order_id == order_id).update(
            {"from_order_id": None}
        )
        # Bu yerga faqat HECH NARSA topshirilmagan buyurtmalar keladi (soft=False),
        # shuning uchun unga bog'liq to'lovlar ham — haqiqiy xizmat ko'rsatilmagani
        # sabab — buyurtma bilan BIRGA, avtomatik o'chiriladi.
        db.query(Payment).filter(Payment.order_id == order_id).delete()
        _prj_do = db_order.project
        db.delete(db_order)
        # 17c: o'chgan to'lovlar loyiha "To'langan" summasidan ham chiqadi.
        _loyiha_tolangan_yangila(db, _prj_do)
        db.commit()
        log_activity(db, "deleted", "order", order_id, order_num, performed_by,
                     company_id=getattr(db_order, 'company_id', None))
    return True


def permanent_delete_order(db: Session, order_id: int, performed_by: str = None) -> bool:
    """YUMSHOQ o'chirilgan buyurtmani BAZADAN BUTUNLAY o'chiradi.
    Faqat is_deleted=True bo'lgan (allaqachon 'chiqindi qutisi'da turgan)
    buyurtmalar uchun ishlaydi — himoya sifatida."""
    db_order = db.query(Order).filter(Order.id == order_id, Order.is_deleted.is_(True)).first()
    if not db_order:
        return False
    order_num = db_order.order_number
    from models import InventoryMovement, FinishedProduct
    from production_models import ProductionOrder
    db.query(ProductionOrder).filter(ProductionOrder.source_order_id == order_id).update(
        {"source_order_id": None, "source_order_item_id": None}
    )
    db.query(InventoryMovement).filter(InventoryMovement.order_id == order_id).update({"order_id": None})
    db.query(FinishedProduct).filter(FinishedProduct.from_order_id == order_id).update({"from_order_id": None})
    _prj_pd = db_order.project
    db.delete(db_order)
    # 17c: buyurtma bilan birga uning to'lovlari ham o'chadi (cascade) —
    # loyiha "To'langan" summasi qayta hisoblanadi.
    _loyiha_tolangan_yangila(db, _prj_pd)
    db.commit()
    log_activity(db, "permanently_deleted", "order", order_id, order_num, performed_by,
                 company_id=getattr(db_order, 'company_id', None))
    return True


def restore_order(db: Session, order_id: int, performed_by: str = None) -> bool:
    """O'chirilgan (yumshoq) buyurtmani tiklaydi.

    MUHIM: agar o'chirishda xomashyo/tayyor mahsulot omborga qaytarilgan
    bo'lsa (order.stock_returned=True), endi buyurtma qayta faol bo'lgani
    uchun O'SHA MIQDORNI QAYTA OMBORDAN YECHISH kerak — aks holda material
    ham "omborda bor", ham "buyurtmada ishlatilgan" bo'lib, ombor sun'iy
    ravishda ko'payib qoladi. Bu — o'chirishda ishlatilgan return_*
    funksiyalarning aynan aksi (sign=-1.0), shuning uchun sonlar mos keladi.
    """
    import services

    db_order = db.query(Order).filter(Order.id == order_id).first()
    if not db_order:
        return False

    if db_order.stock_returned:
        # kech60 (57-band): "qisman chiqqan" sharti — `services.buyurtmadan_qisman_chiqqan` (pastda)
        is_fully_delivered = db_order.status == OrderStatus.DELIVERED or db_order.is_fully_delivered

        if not is_fully_delivered:
            # kech60 (57-band): o'chirishdagi (`main.api_delete_order`) bilan AYNAN bir xil
            # shart — topshirilgan YOKI omborga ortiqcha qo'yilgan qism bo'lsa, faqat qolgan qism.
            if services.buyurtmadan_qisman_chiqqan(db_order):
                # Qisman topshirilgan / omborga qo'yilgan edi — faqat qolgan qism qayta yechiladi
                services.return_inventory_for_order_partial(db, db_order, sign=-1.0)
            else:
                # Hech narsa topshirilmagan edi — hammasi qayta yechiladi
                services.return_inventory_for_order(db, db_order, sign=-1.0)

            # Tayyor mahsulotlar qayta yechiladi — hech narsa topshirilmagan
            # bo'lsa TO'LIQ, QISMAN topshirilgan bo'lsa faqat QOLGAN qismi
            # (_return_finished_for_order item.remaining_qty orqali o'zi farqni
            # to'g'ri hisoblaydi — bu o'chirishdagi qaytarishning aynan aksi).
            _return_finished_for_order(db, db_order, sign=-1.0)

            # Loy uchun QOLGAN (topshirilmagan) qism ulushi — o'chirishda
            # QANCHA qaytarilgan bo'lsa, tiklashda AYNAN O'SHA qism qayta
            # yechiladi (bu ulush o'zgarmaydi, chunki buyurtma o'chirilgan
            # holatda yetkazishlar qo'shilmaydi va detallar tahrirlanmaydi —
            # create_delivery/update_order_item/delete_order_item endi
            # is_deleted buyurtmalarni rad etadi).
            # MUHIM (2026-09 chuqur audit — ikkinchi bosqich): order-wide
            # delivery_percent EMAS — Loy uchun ALOHIDA, faqat shu
            # xomashyoni haqiqatda sarflaydigan detallar bo'yicha hisoblangan
            # ulush (qarang: main.py'dagi bir xil tuzatish va services.py
            # dagi loy_relevant_remaining_fraction
            # fraction izohlari).
            loy_remaining_fraction = (services.loy_relevant_remaining_fraction(db_order)
                                      if services.buyurtmadan_qisman_chiqqan(db_order) else 1.0)

            # Loy (qoplama) — rejalashtirilgan miqdor (yoki QOLGAN ulushi) qayta yechiladi.
            # Eslatma: agar o'chirishda "haqiqatda qancha ishlatilgan edi"
            # deb alohida qiymat kiritilgan bo'lsa, o'sha aniq qiymat
            # saqlanmaganligi sabab, bu yerda REJADAGI (standart) miqdor
            # asos qilib olinadi — aksariyat holatlarda bu aynan to'g'ri keladi.
            planned_loy = services._get_planned_loy(db_order)
            redo_loy = planned_loy * loy_remaining_fraction
            if redo_loy > 0.01:
                services.deduct_loy_ingredients(db, db_order, redo_loy)

            # "Loy sotish" detallari — har biri o'z remaining_qty'i bo'yicha
            # ALOHIDA qayta yechiladi (o'chirishdagi bilan bir xil, item
            # darajasida — order-wide has_delivery emas; qarang: yuqoridagi
            # main.py'dagi bir xil tuzatish).
            for item in db_order.items:
                if (item.category or '').lower() == 'loy_sotish' and item.recipe_id:
                    remaining = item.remaining_qty
                    if remaining > 0.001:
                        services.deduct_loy_ingredients(db, db_order, float(remaining), recipe_id=item.recipe_id)

        db_order.stock_returned = False

    db_order.is_deleted = False
    db.commit()
    log_activity(db, "restored", "order", order_id, db_order.order_number, performed_by,
                 company_id=getattr(db_order, 'company_id', None))
    return True


def get_deleted_orders(db: Session, company_id: int = None) -> List[Order]:
    """O'chirilgan (lekin hali bazada saqlanayotgan) buyurtmalar."""
    _q = db.query(Order).filter(Order.is_deleted.is_(True))
    if company_id is not None:
        _q = _q.filter(Order.company_id == company_id)
    return _q.order_by(Order.created_at.desc()).all()


def delete_order_item(db: Session, item_id: int, company_id: int = None) -> bool:
    """Detal o'chirish — xomashyo omborga qaytariladi.
    Topshirilgan detalni o'chirib bo'lmaydi."""
    import services

    # M2: detal FAQAT o'z korxonasidan topiladi.
    _iq = db.query(OrderItem).filter(OrderItem.id == item_id)
    if company_id is not None:
        _iq = _iq.filter(OrderItem.company_id == company_id)
    db_item = _iq.first()
    if not db_item:
        return False
    # kech41 (5-bo'lim 14-band, K41-1) — QULF (101, buyurtma), yetkazish /
    # to'lov / qaytarish bilan BIR fazo. HAQIQIY PostgreSQL da O'LCHANGAN
    # (asl kod, `work/probe41.py`, 3 / 3 urinish): qulfsiz "topshirilgan"
    # tekshiruvi bir vaqtdagi yetkazishni ko'rmasdi —
    # detal o'chirilayotganda undan 3 topshirilsa, detal o'chib, yuk xati
    # qolardi (buyurtma summasi 0, penoplast TO'LIQ omborga "qaytardi");
    # teskari tartibda o'chirish FK xatosi bilan 500 berardi.
    # Naqsh `create_delivery` / `delete_delivery` dagi bilan bir xil:
    # yozilmagan o'zgarish yo'qolmasin (`flush`), qulf, so'ng qulf ostida
    # bazadan QAYTA o'qiladi (`expire_all`).
    if db_item.order_id is not None:
        db.flush()
        _pul_qulfi(db, 101, db_item.order_id)
        db.expire_all()
        db_item = _iq.first()
        if not db_item:
            return False

    # Topshirilgan bo'lsa — o'chirib bo'lmaydi
    if db_item.delivered_qty > 0.001:
        return False
    # kech60 (57-band, K59-3): detaldan ortiqcha mahsulot omborga qo'yilgan bo'lsa — rad
    # (ValueError -> marshrut 400, hech narsa o'zgarmaydi). O'LCHANGAN (asl kod): 10 m dan
    # 5 m omborga qo'yilgach detal o'chirilsa penoplast 10 m uchun to'liq qaytardi VA 5 m
    # tayyor mahsulot qolardi (ikki marta). Yo'l: qaytarishni o'chirish (22-band — tayyor
    # mahsulot AYNAN olinadi) yoki detal miqdorini kamaytirish (omborga qo'yilgandan kam emas).
    _ortiqcha_d = db_item.ortiqcha_qty
    if _ortiqcha_d > 0.001:
        raise ValueError(
            f"«{db_item.name}» detalidan {_miqdor_matn(_ortiqcha_d)} {db_item.delivery_unit} ortiqcha "
            f"mahsulot omborga qaytarilgan — detalni o'chirib bo'lmaydi. Avval o'sha qaytarishni "
            f"o'chiring yoki detal miqdorini kamaytiring (kamida {_miqdor_matn(_ortiqcha_d)})")

    order = db_item.order
    # MUHIM (2026-09 audit): o'chirilgan buyurtmaning detalini o'chirib
    # bo'lmaydi — sabab update_order_item'dagi bilan bir xil (ombor
    # hisobi simmetriyasini saqlash uchun).
    if order and order.is_deleted:
        return False
    is_draft = order.status == OrderStatus.DRAFT if order else False

    # O'chiriladigan detalning xomashyosini qaytaramiz
    if not is_draft:
        old_snap = [{
            "category": db_item.category,
            "width": db_item.width,
            "thickness": db_item.thickness,
            "length": db_item.length,
            "quantity": float(db_item.quantity or 1),
            "unit_price": float(db_item.unit_price or 0),
            "penoplast_id": db_item.penoplast_id,
            # MUHIM (2026-09 audit): "Tayyor mahsulotdan" tanlangan detal
            # bo'lsa — bu maydon bo'lmasa, _item_volume_m3() buni oddiy
            # xomashyo detali deb hisoblab, HECH QACHON ombordan chiqmagan
            # hajmni omborga "qaytarib" (aslida — YARATIB) qo'yar edi.
            # Butun buyurtma o'chirilganda bu xato yo'q (chunki o'sha yo'l
            # to'g'ridan-to'g'ri OrderItem obyektidan o'qiydi), lekin bu
            # yerda FAQAT bitta detal, dict shaklida uzatiladi — shuning
            # uchun bu maydonni ANIQ shu yerda qo'shish shart.
            "finished_product_id": db_item.finished_product_id,
            # MUHIM: ichki qo'shimcha detallar ham shu detal bilan BIRGA
            # o'chadi — ularning hajmi ham omborga qaytishi kerak, aks
            # holda shu qismi "yo'qolib" qolardi (buyurtma butunlay
            # o'chirilganda bunday muammo yo'q, chunki o'sha yo'l
            # order.items to'liq ro'yxatini o'qiydi — bu yerda esa FAQAT
            # shu bitta detal, shuning uchun aniq shu yerda qo'shishimiz kerak).
            "sub_details": [{
                "category": s.category, "width": s.width, "thickness": s.thickness,
                "length": s.length, "quantity": s.quantity,
            } for s in (db_item.sub_details or [])],
        }]
        services.adjust_inventory_diff(db, old_snap, [], order_id=db_item.order_id,
                                       company_id=db_item.company_id, commit=False)

    # 2026-09-17: shu detalga Production/MRP orqali band qilingan tayyor
    # mahsulot bo'lsa — avtomatik ozod qilamiz (aks holda, detal
    # o'chirilgach, u band qilingancha, ABADIY qaytarib bo'lmaydigan
    # holda qolib ketardi).
    _auto_release_mrp_reservations(db, [db_item.id])
    # 2026-09-18 (chuqur audit topilmasi — HAQIQIY, jonli sinovda
    # aniqlangan xato): agar shu detalga Production/MRP buyurtmasi
    # (source_order_item_id orqali) bog'langan bo'lsa, pastdagi
    # db.delete(db_item) PostgreSQL FK cheklovi tufayli 500-xato bilan
    # butunlay bloklanardi (delete_order()dagi bilan bir xil sabab —
    # o'sha yerda aynan shu xato jonli sinovda topildi). ProductionOrder
    # o'zi — TARIXIY YOZUV, o'chirilmaydi, faqat bog'lanishi uziladi.
    from production_models import ProductionOrder
    db.query(ProductionOrder).filter(ProductionOrder.source_order_item_id == db_item.id).update(
        {"source_order_item_id": None}
    )

    db.delete(db_item)
    db.flush()

    if order:
        order.total_amount = sum(float(it.total_price or 0) for it in order.items)
        db.flush()
        db.refresh(order)
        _update_order_payment_status(db, order)

    db.commit()
    return True


def update_project(db: Session, project_id: int, project_data) -> Optional[Project]:
    """Loyihani yangilash."""
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        return None
    # Pydantic v2 model_dump yoki dict
    if hasattr(project_data, 'model_dump'):
        update_data = project_data.model_dump(exclude_unset=True)
    else:
        update_data = {k: v for k, v in project_data.items() if v is not None}
    # 14-band: qat'iy tekshiruv — HECH NARSA yozilmasdan OLDIN (ValueError → 400).
    # `status` kanonik enum NOMIGA keltiriladi, noma'lum qiymat rad etiladi
    # (ilgari noma'lum matn to'g'ridan yozilib 500 berardi).
    update_data = _clean_update("Project", update_data)

    # HIMOYA: "status" satr (string) sifatida kelsa — katta/kichik harfdan
    # qat'i nazar, to'g'ri ProjectStatus a'zosiga moslashtiramiz. Bu, manba
    # (frontend yoki boshqa chaqiruvchi) noto'g'ri formatda yuborsa ham,
    # bazaga noto'g'ri qiymat yozilib qolishining oldini oladi (masalan
    # "active" o'rniga "ACTIVE" — enum NOMI kutiladi, QIYMATI emas).
    if 'status' in update_data and isinstance(update_data['status'], str):
        raw = update_data['status'].strip()
        matched = None
        for member in ProjectStatus:
            if raw.upper() == member.name or raw.lower() == member.value:
                matched = member
                break
        if matched:
            update_data['status'] = matched

    for field, value in update_data.items():
        if hasattr(db_project, field) and value is not None:
            setattr(db_project, field, value)

    db.commit()
    db.refresh(db_project)
    return db_project


def delete_project(db: Session, project_id: int, performed_by: str = None) -> bool:
    """Loyihani o'chirish — YUMSHOQ (is_deleted=True). Ma'lumot yo'qolmaydi,
    'O'chirilganlar' bo'limidan tiklash mumkin (inson xatosidan himoya)."""
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        return False
    label = f"{db_project.project_number} — {db_project.project_name}"
    db_project.is_deleted = True
    db.commit()
    log_activity(db, "deleted", "project", project_id, label, performed_by,
                 company_id=getattr(db_project, 'company_id', None))
    return True


def permanent_delete_project(db: Session, project_id: int, performed_by: str = None) -> tuple:
    """YUMSHOQ o'chirilgan loyihani BAZADAN BUTUNLAY o'chiradi.
    Xavfsizlik uchun — agar loyihada HALI HAM buyurtmalar bo'lsa (hatto
    ular ham o'chirilgan bo'lsa ham) — avval ularni hal qilish so'raladi,
    chunki loyiha o'chirilsa ular ham katta izsiz o'chib ketadi (cascade)."""
    db_project = db.query(Project).filter(Project.id == project_id, Project.is_deleted.is_(True)).first()
    if not db_project:
        return False, "Loyiha topilmadi (avval yumshoq o'chirilgan bo'lishi kerak)"
    order_count = db.query(Order).filter(Order.project_id == project_id).count()
    if order_count > 0:
        return False, f"Bu loyihada hali {order_count} ta buyurtma bor — avval ularni butunlay o'chiring"
    label = f"{db_project.project_number} — {db_project.project_name}"
    db.delete(db_project)
    db.commit()
    log_activity(db, "permanently_deleted", "project", project_id, label, performed_by,
                 company_id=getattr(db_project, 'company_id', None))
    return True, "ok"


def restore_project(db: Session, project_id: int, performed_by: str = None) -> bool:
    """O'chirilgan loyihani tiklaydi."""
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        return False
    db_project.is_deleted = False
    db.commit()
    label = f"{db_project.project_number} — {db_project.project_name}"
    log_activity(db, "restored", "project", project_id, label, performed_by,
                 company_id=getattr(db_project, 'company_id', None))
    return True


def get_deleted_projects(db: Session, company_id: int = None) -> List[Project]:
    """O'chirilgan (lekin hali bazada saqlanayotgan) loyihalar."""
    _q = db.query(Project).filter(Project.is_deleted.is_(True))
    if company_id is not None:
        _q = _q.filter(Project.company_id == company_id)
    return _q.order_by(Project.start_date.desc()).all()


# ============================================================
# RETURN ITEM CRUD
# ============================================================

from models import ReturnItem, ReturnReason
from schemas import ReturnItemCreate


def _miqdor_matn(x) -> str:
    """Miqdor xabar uchun: 3 xonagacha, ortiqcha nolsiz (6.0 -> '6',
    3.3333 -> '3.333'). `:g` katta sonni 1.2e+06 qilib yuborardi."""
    s = f"{float(x):.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _som_butun(v) -> float:
    """Butun so'mga, 0.5 YUQORIGA (musbat sonlarda JS `Math.round` bilan bir xil —
    UI summasi va server avto-summasi farq qilmasin). Python `round()` —
    "bankir" yaxlitlashi, 0.5 da farq berardi."""
    from decimal import Decimal, ROUND_HALF_UP
    return float(Decimal(repr(float(v))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def pul_qaytarish_kamaytirgan(db: Session, order) -> float:
    """28-band (kech43, K42-2): buyurtmaning kelishilgan summasini YANGI pul
    qaytarishlar (kech40 dan keyin belgilangan — `refunded_at` bor) AYNAN qanchaga
    kamaytirgani: `refund_agreed_delta` yig'indisi (so'm).

    Kelishilgan summani QAYTA HISOBLAYDIGAN har joy (buyurtmani tahrirlash,
    qisman yakunlash, qo'lda kelishilgan summa) shu miqdorni hisobga olishi SHART.
    O'LCHANGAN (asl kod, SQLite = PG, `work/probe43.py`): tahrirdan keyin pul
    qaytarish kamaytirishi yo'qolardi (qarz qayta paydo bo'lardi, 150 000 naqd
    qaytarilgan to'liq to'langan buyurtmada 150 000 "qarz"), yoki "chegirma" ga
    aylanib keyingi qaytarish narxini tushirardi (30 %), qaytarishni o'chirish esa
    summani JAMIDAN ham oshirardi (500 000 lik buyurtma 1 000 000).

    Yangilanishdan OLDINGI pul qaytarishlar (`refunded_at` bo'sh) — qancha
    kamaytirgani yozilmagan, taxmin qilinmaydi (0 deb olinadi)."""
    if order is None or getattr(order, "id", None) is None:
        return 0.0
    _qaytganlar = db.query(ReturnItem).filter(
        ReturnItem.order_id == order.id,
        ReturnItem.company_id == order.company_id,
        ReturnItem.is_refunded.is_(True),
        ReturnItem.refunded_at.isnot(None)).all()
    return float(sum(float(r.refund_agreed_delta or 0) for r in _qaytganlar))


def qaytarish_narx_koeffitsienti(db: Session, order) -> float:
    """4-band (kech42, FOYDALANUVCHI QARORI: "Chegirmali narxdan"): qaytarish
    summasi buyurtmaning KELISHILGAN (chegirmali) narxidan hisoblanadi —
    1 000 000 lik buyurtma 900 000 ga kelishilgan bo'lsa, butun qaytarish
    900 000. Koeffitsient = kelishilgan / jami (<= 1).

    Joriy `agreed_amount` pul qaytarishlardan keyin KAMAYADI (mark_refunded) —
    shuning uchun ASL kelishilgan = joriy + yangi belgilangan pul
    qaytarishlarning `refund_agreed_delta` yig'indisi. U saqlangan chegirma
    foiziga (`discount_percent`, 2 xonagacha yaxlitlangan) mos kelsa — aniq
    nisbat; mos kelmasa (qarz kechirilgan — bu narx chegirmasi emas,
    yangilanishdan oldingi pul qaytarish, qo'lda o'zgartirish) — saqlangan
    foiz. Chegirma yo'q yoki ustama (kelishilgan > jami) — 1 (qaror faqat
    chegirma haqida)."""
    if order is None:
        return 1.0
    total = float(order.total_amount or 0)
    dp = float(order.discount_percent or 0)
    if total <= 0 or dp <= 0:
        return 1.0
    asl = order.kelishilgan_summa + pul_qaytarish_kamaytirgan(db, order)
    k = asl / total
    if abs((1.0 - k) * 100.0 - dp) <= 0.0051:
        return min(1.0, max(0.0, k))
    return min(1.0, max(0.0, 1.0 - dp / 100.0))


def qaytarish_birlik_narxi(db: Session, order, order_item, koef: float = None) -> float:
    """Qaytarishning 1 birlik narxi (kelishilgan narx bo'yicha, tiyingacha).
    UI (`returns.html` `currentUnitPrice`) ham AYNAN shu qiymatni oladi
    (`/api/orders/{id}` → `refund_price_per_unit`)."""
    ordered = float(order_item.order_qty_normalized or 0)
    if ordered <= 0:
        return 0.0
    if koef is None:
        koef = qaytarish_narx_koeffitsienti(db, order)
    return _pul2(float(order_item.total_price or 0) / ordered * koef)


def _qaytarish_ortiqcha_qismi(db: Session, order_item, miqdor: float) -> float:
    """kech60 (57-band, K59-3): yangi (brakdan boshqa) qaytarishning mijozga HALI
    TOPSHIRILMAGAN qismi. Qoida: qaytarish avval topshirilgan (va hali qaytarilmagan)
    miqdordan olinadi, qolgani — ortiqcha (omborga qo'yilgan). Topshirilgan miqdor
    bazadan QAYTA o'qiladi (chaqiruvchi qulf (101, buyurtma) ostida). Eski yozuv
    (`ortiqcha_miqdor` NULL) — to'liq topshirilgandan deb olinadi.
    Migratsiya (`main._migrate_ortiqcha_qaytarish`) — AYNAN shu qoida, yozilish tartibida."""
    from sqlalchemy import func as _fn_o
    db.expire(order_item, ["deliveries"])
    _topsh = float(order_item.delivered_qty or 0)
    _oldin_topshdan = float(db.query(_fn_o.coalesce(_fn_o.sum(
        ReturnItem.quantity - _fn_o.coalesce(ReturnItem.ortiqcha_miqdor, 0)), 0)).filter(
        ReturnItem.company_id == order_item.company_id,
        ReturnItem.order_item_id == order_item.id,
        ReturnItem.reason != ReturnReason.DEFECT).scalar() or 0)
    _bor = max(0.0, _topsh - _oldin_topshdan)
    return max(0.0, float(miqdor) - _bor)


def create_return_item(db: Session, data: ReturnItemCreate,
                       company_id: int = None) -> ReturnItem:
    """Yangi qaytarishni bazaga qo'shadi.
    to_stock=True bo'lsa — tayyor mahsulotlar omboriga ham tushadi.
    refund_amount kelmasa (masalan hodim narx ko'rmasdan yozganda) —
    server o'zi tan narx/sotuv narxdan hisoblab qo'yadi."""
    import services

    # 17g (2026-09-22): ILDIZ — tana QAT'IY, bazaga tegishdan OLDIN (xato →
    # `ValueError`, marshrut → 400, hech narsa yozilmaydi). HAQIQIY PostgreSQL
    # da O'LCHANGAN (asl kod = 17f): miqdor manfiy / 0 / `1e20` — saqlanardi;
    # `Infinity` / `NaN` — SAQLANARDI va tayyor mahsulot qoldig'ini cheksiz /
    # "son emas" qilib qo'yardi (javob 500); summa `NaN` bazaga "NaN" bo'lib
    # yozilardi, `Infinity` / `1e20` — 500, `0.001` → 0.00; nom / birlik
    # sig'imdan uzun — 500; noma'lum sabab jimgina "Brak".
    _clean_val("Return", _val_dump(data, "Return"))

    # M2: qaytarish FAQAT o'z korxonasining buyurtmasiga yozilishi mumkin.
    _oq = db.query(Order).filter(Order.id == data.order_id)
    if company_id is not None:
        _oq = _oq.filter(Order.company_id == company_id)
    _o = _oq.first()
    if not _o:
        raise ValueError("Buyurtma topilmadi")

    # 17g: sabab — faqat `models.ReturnReason` qiymatlari (yuqorida tekshirilgan).
    # Ilgari noma'lum sabab JIMGINA "Brak" ga aylanardi (O'LCHANGAN): ombordan
    # xomashyo yechilar, mahsulot esa omborga qaytmasdi.
    reason_enum = ReturnReason(data.reason)
    # kech53 (13-band, 1-qadam): bosqich FAQAT brak uchun — boshqa sababga
    # berilsa jim tashlanmaydi, hech narsa yozilishidan OLDIN rad etiladi
    # (texnik qaror: noto'g'ri tana — xato, ma'lumot emas).
    _bosqich = getattr(data, 'brak_bosqich', None)
    if _bosqich is not None and reason_enum != ReturnReason.DEFECT:
        raise ValueError("Brak bosqichi faqat \"Brak\" sababi uchun tanlanadi")
    # kech56 (13-band, 7-qadam): sabab va javobgar hodim — bosqich kabi FAQAT brak
    # uchun; javobgar — shu korxonaning hodimi (hech narsa yozilishidan OLDIN).
    _sabab = getattr(data, 'brak_sabab', None)
    _javobgar = getattr(data, 'brak_javobgar_id', None)
    if (_sabab is not None or _javobgar is not None) and reason_enum != ReturnReason.DEFECT:
        raise ValueError("Brak sababi va javobgar hodim faqat \"Brak\" sababi uchun tanlanadi")
    _brak_javobgar_tekshir(db, _javobgar, _o.company_id)

    order_item = None
    oi_id = getattr(data, 'order_item_id', None)
    if oi_id:
        # 2026-09-21 (12-sizish) — O'LCHANGAN: detal faqat ID bo'yicha
        # olinardi, buyurtmaga tegishliligi tekshirilmasdi. B o'z buyurtmasi
        # + A ning `order_item_id` sini bersa, brak A ning penoplastini
        # yechardi va qaytarish summasi A tan narxidan hisoblanib B ga
        # qaytardi. Endi detal FAQAT shu buyurtma ichidan; topilmasa —
        # nom bo'yicha taxmin QILINMAYDI, rad etiladi.
        order_item = db.query(OrderItem).filter(
            OrderItem.id == oi_id,
            OrderItem.order_id == data.order_id).first()
        if not order_item:
            raise ValueError("Buyurtma detali topilmadi")
    if not order_item:
        # kech39 (5-bo'lim 3-band): detal raqamisiz (faqat nom) so'rov — nom
        # buyurtmada YAGONA bo'lsagina qabul qilinadi. O'LCHANGAN (asl kod
        # `8265a94`, SQLite va HAQIQIY PG 16): bitta buyurtmada bir xil nomli
        # ikki detal bo'lishi mumkin (`POST /api/orders` 200), `.first()` esa
        # ulardan birini TAXMIN qilardi — omborga qaytarish, summa va endi
        # yig'indi boshqa detalga yozilib ketardi. `returns.html` doim
        # `order_item_id` yuboradi.
        _nomdoshlar = db.query(OrderItem).filter(
            OrderItem.company_id == _o.company_id,
            OrderItem.order_id == data.order_id,
            OrderItem.name == data.item_name
        ).order_by(OrderItem.id).all()
        if len(_nomdoshlar) > 1:
            raise ValueError(f"Buyurtmada '{data.item_name}' nomli {len(_nomdoshlar)} ta detal bor — "
                             f"qaysi biri qaytayotganini tanlang (detal raqami kerak)")
        order_item = _nomdoshlar[0] if _nomdoshlar else None
    # 17g (kech25, 2026-09-22): qaytarish FAQAT buyurtmadagi detalga yoziladi.
    # O'LCHANGAN (asl kod = 17f va 17g WIP): detal ID siz, buyurtmada YO'Q nom
    # bilan (`"item_name": "boshqa"`) istalgan miqdor (999 999) 200 bilan
    # saqlanardi — miqdor chegarasi, summa hisobi va omborga qaytarish faqat
    # detal topilganda ishlaydi, ya'ni bunday yozuv hech narsaga tayanmasdi.
    # `returns.html` (qaytarish va brak oynalari) doim `order_item_id` yuboradi.
    if order_item is None:
        raise ValueError("Buyurtma detali topilmadi")

    # 17g (2026-09-22): bitta qaytarishda buyurtmadagidan KO'P miqdor bo'lmaydi.
    # `returns.html` buni faqat brauzerda tekshirardi (`order_qty_normalized`);
    # server tekshirmasdi — HAQIQIY PostgreSQL da O'LCHANGAN: 1000 metrlik
    # detaldan 1001 metr qaytarish 200 bilan saqlandi (omborga 1001 qo'shildi).
    # Xabar UI dagi bilan bir xil.
    _buyurtmada = float(order_item.order_qty_normalized or 0)
    if float(data.quantity) > _buyurtmada + 0.001:
        raise ValueError(f"Buyurtmada {_buyurtmada:g} {order_item.delivery_unit} bor, "
                         f"{float(data.quantity):g} qaytarib bo'lmaydi")

    # kech39 (5-bo'lim 3-band): omborga QAYTADIGAN sabablar (brakdan boshqa
    # hammasi; `to_stock=false` ham — mahsulot mijozdan baribir qaytgan) bo'yicha
    # shu DETALNING jami qaytarilgani buyurtmadagi miqdordan oshmaydi.
    # O'LCHANGAN (asl kod `8265a94`, SQLite va HAQIQIY PG 16, `work/probe39.py`):
    # 10 metrli detaldan "Ortiqcha" 6 + 6 + 6 metr — uchalasi 200, tayyor
    # mahsulotlar omboriga 18 metr qo'shildi. Brak uchun yig'indi cheklovi
    # QO'YILMAYDI (takroriy brak haqiqatda bo'ladi — kelishilgan) va brak
    # yig'indiga KIRMAYDI. Detal `order_item_id` ustuni bo'yicha (nom bo'yicha
    # EMAS); detal raqamisiz eski yozuvlar (migratsiya bog'lay olmaganlari —
    # nomi buyurtmada takrorlangan yoki topilmagan) yig'indiga kirmaydi: qaysi
    # detalniki ekani noma'lum, taxmin qilinmaydi.
    # Qulf (101, buyurtma) — yetkazish va to'lov bilan bir xil: ikki bir
    # vaqtli qaytarish ikkalasi ham "sig'adi" deb o'tib ketmasin (faqat PG;
    # yig'indi qulf OLINGANDAN KEYIN o'qiladi).
    # kech54 (13-band, 5-qadam): MRP detali braki xomashyosi shu detalni ishlab chiqargan
    # buyurtmaning retsept SURATIDAN olinadi (`services._mrp_birlik_sarfi`). Surat yo'q —
    # ishlab chiqarish hali boshlanmagan: brak faqat ishlab chiqarish ichida bo'ladi
    # (foydalanuvchi qoidasi, 2026-09-23), sarfni hisoblab bo'lmaydi — taxmin qilinmaydi,
    # hech narsa yozilishidan OLDIN rad etiladi (ilgari summa 0 bilan jim saqlanardi).
    if (reason_enum == ReturnReason.DEFECT
            and (order_item.category or '').lower() == 'mrp_product'
            and not getattr(order_item, 'finished_product_id', None)
            and services._mrp_birlik_sarfi(db, _o.company_id, order_item=order_item) is None):
        raise ValueError("Bu MRP mahsuloti uchun ishlab chiqarish hali boshlanmagan — brak faqat "
                         "ishlab chiqarish jarayonida yoziladi (xomashyo sarfini retsept suratidan "
                         "olib bo'lmaydi)")

    if reason_enum != ReturnReason.DEFECT:
        from sqlalchemy import func as _fn_q
        _pul_qulfi(db, 101, _o.id)
        _oldin = float(db.query(_fn_q.coalesce(_fn_q.sum(ReturnItem.quantity), 0)).filter(
            ReturnItem.company_id == _o.company_id,
            ReturnItem.order_item_id == order_item.id,
            ReturnItem.reason != ReturnReason.DEFECT).scalar() or 0)
        _qolgan = _buyurtmada - _oldin
        if float(data.quantity) > _qolgan + 0.001:
            _b = order_item.delivery_unit
            if _qolgan <= 0.001:
                raise ValueError(f"Bu detalning hammasi ({_miqdor_matn(_buyurtmada)} {_b}) allaqachon "
                                 f"qaytarilgan — yana qaytarib bo'lmaydi (brak bundan mustasno)")
            raise ValueError(f"Bu detaldan avval {_miqdor_matn(_oldin)} {_b} qaytarilgan (buyurtmada "
                             f"{_miqdor_matn(_buyurtmada)} {_b}) — yana ko'pi bilan "
                             f"{_miqdor_matn(_qolgan)} {_b} qaytarish mumkin")

    # kech60 (57-band, K59-3): brakdan boshqa qaytarishning mijozga HALI TOPSHIRILMAGAN qismi
    # (ortiqcha mahsulot omborga qo'yiladi — FOYDALANUVCHI QARORI, kech60). Qulf (101) yuqorida
    # olingan — topshirilgan miqdor bazadan qayta o'qiladi (bir vaqtdagi yuk xati hisobga olinsin).
    _ortiqcha_yangi = None
    if reason_enum != ReturnReason.DEFECT:
        _ortiqcha_yangi = _qaytarish_ortiqcha_qismi(db, order_item, float(data.quantity))
        # O'chirilgan buyurtmada omborga qo'yish — o'chirish / tiklash simmetriyasini buzadi
        # (o'chirishda qolgan qism xomashyosi allaqachon qaytgan).
        if _o.is_deleted and _ortiqcha_yangi > 0.001:
            raise ValueError("Buyurtma o'chirilgan — topshirilmagan mahsulotni omborga qaytarib bo'lmaydi "
                             "(uning xomashyosi o'chirishda qaytgan)")

    refund_amount = float(data.refund_amount or 0)
    # 17g: QO'LDA berilgan qaytarish summasi buyurtma qiymatidan oshmaydi —
    # `mark_refunded` shu summani kelishilgan summadan ayiradi (0 dan pastga
    # tushirmaydi) va AYNAN shu summada manfiy to'lov yozadi. O'LCHANGAN:
    # 1 000 000 so'mlik buyurtmaga 9 000 000 000 so'm qaytarish saqlandi,
    # "pul qaytarildi" belgisidan keyin kelishilgan summa 0, to'lovlar
    # −9 000 000 000 bo'ldi. Qiymat `mark_refunded` dagi bilan bir xil ta'rif
    # (kelishilgan, bo'lmasa jami summa). Server o'zi hisoblaydigan summa
    # (0 berilganda) bu tekshiruvga kirmaydi.
    # kech25 (2026-09-22) — chegara `returns.html` summasini rad etmasligi
    # SHART (hodimda summa maydoni yashirin — uni tuzatib bo'lmaydi). UI summasi
    # = Math.round(miqdor × 1 birlik narxi), narx esa detal jamisidan BUTUN
    # so'mga yaxlitlangan va CHEGIRMASIZ (`price_per_unit_final`). O'LCHANGAN
    # (17g WIP): chegirmali buyurtmada (kelishilgan 900 000, jami 1 000 000)
    # butun qaytarish 1 000 000 → 400; 6 × 166 666.67 (jami 1 000 000.02) → UI
    # 6 × 166 667 = 1 000 002 → 400. Shuning uchun chegara — kelishilgan va
    # jami summaning KATTASI, ustiga birlik narxini yaxlitlash farqi (har
    # birlikka 0.5 so'm + oxirgi yaxlitlash 0.5). Bema'ni summa (9e9) baribir
    # rad etiladi. Chegirmali buyurtmada qaytarish qiymatini qanday hisoblash
    # (chegirmasiz yoki chegirmali narx) — alohida BIZNES masalasi, bu yerda
    # o'zgartirilmaydi.
    # kech42 (4-band, FOYDALANUVCHI QARORI "Chegirmali narxdan"): brakdan boshqa
    # qaytarish summasi KELISHILGAN narxdan (`qaytarish_birlik_narxi`). O'LCHANGAN
    # (asl kod): 500 000 lik buyurtma 450 000 ga kelishilgan — butun qaytarish
    # 500 000 yozilardi. Qo'lda kiritilgan summa ham shu detal qismining
    # kelishilgan qiymatidan oshmaydi (+ yaxlitlash farqi: har birlikka 0.5
    # so'm + 0.5 — eski sahifadan chegirmasiz buyurtmaga butun so'mli narx
    # bilan yuborilgan summa rad etilmasin). Brak — avvalgidek (tan narx,
    # buyurtma darajasidagi chegara).
    _birlik = None
    if reason_enum != ReturnReason.DEFECT and order_item is not None:
        _birlik = qaytarish_birlik_narxi(db, _o, order_item)
    if refund_amount > 0:
        _mq = float(data.quantity)
        if _birlik is not None:
            _qiymat = _som_butun(_birlik * _mq)
            if refund_amount > _birlik * _mq + 0.5 * _mq + 0.5:
                raise ValueError(f"Qaytariladigan summa ({refund_amount:,.0f} so'm) bu detal qismining "
                                 f"kelishilgan qiymatidan ({_qiymat:,.0f} so'm = {_miqdor_matn(_mq)} × "
                                 f"{_birlik:,.2f} so'm) katta bo'lishi mumkin emas")
        else:
            _qiymat = max(_o.kelishilgan_summa, float(_o.total_amount or 0))
            if refund_amount > _qiymat + 0.5 * _mq + 0.5:
                raise ValueError(f"Qaytariladigan summa ({refund_amount:,.0f} so'm) buyurtma "
                                 f"qiymatidan ({_qiymat:,.0f} so'm) katta bo'lishi mumkin emas")
    if refund_amount <= 0 and order_item:
        if reason_enum == ReturnReason.DEFECT:
            # Brak — tan narx (xomashyo qiymati)
            # kech54 (42-band): loy FAQAT tortilgan bo'lsa ("✂️ Yo'q — loygacha" — loysiz).
            # O'LCHANGAN (asl kod `aecce02`, `work/probe54.py`): qoplamali profil 1 m loygacha
            # brak — ombordan faqat penoplast (5 000) yechilardi, summa esa loy bilan 10 200
            # yozilardi (Qaytarishlar sahifasi "Brak qiymati" Moliyadan katta). FOYDALANUVCHI
            # QARORI (kech54): eski yozuvlar O'ZGARMAYDI — faqat yangilari to'g'ri.
            unit_price = services.get_order_item_unit_cost(
                db, order_item.order, order_item,
                include_coating=bool(getattr(data, 'coating_applied', False)))
            refund_amount = round(unit_price * float(data.quantity or 0))
        else:
            # Butun — kelishilgan (chegirmali) sotuv narxi
            refund_amount = _som_butun((_birlik or 0) * float(data.quantity or 0))

    # M8/F1: `order_id` va `finished_product_id` ikkalasi ham NULL
    # bo'lishi mumkin — korxonani buyurtmadan olamiz.
    item = ReturnItem(
        company_id=company_id,
        order_id=data.order_id,
        # kech39 (3-band): detal raqami — yig'indi shu bo'yicha hisoblanadi
        order_item_id=order_item.id,
        item_name=data.item_name,
        quantity=data.quantity,
        unit=data.unit,
        reason=reason_enum,
        refund_amount=refund_amount,
        is_refunded=False,
        notes=data.notes,
        coating_applied=(getattr(data, 'coating_applied', False) if reason_enum == ReturnReason.DEFECT else False),
        # kech53 (13-band, 1-qadam): ixtiyoriy bosqich (yuqorida faqat brakka ruxsat)
        brak_bosqich=(_bosqich if reason_enum == ReturnReason.DEFECT else None),
        # kech56 (13-band, 7-qadam): ixtiyoriy sabab va javobgar (yuqorida faqat brakka ruxsat)
        brak_sabab=(_sabab if reason_enum == ReturnReason.DEFECT else None),
        brak_javobgar_id=(_javobgar if reason_enum == ReturnReason.DEFECT else None),
        # kech60 (57-band): mijozga topshirilmagan (ortiqcha, omborga qo'yilgan) qism; brak — NULL
        ortiqcha_miqdor=_ortiqcha_yangi
    )
    db.add(item)
    db.flush()

    # BRAK bo'lsa — sarflangan xomashyoni (Penoplast + shart bo'lsa Loy)
    # ombordan haqiqatda yechamiz (moliyaviy hisobdan MUSTAQIL, alohida)
    if reason_enum == ReturnReason.DEFECT and order_item and order_item.order:
        # kech45 (13-band, 6-qadam): yechilgan har harakat shu brak yozuviga
        # bog'lanadi (`log_movement` sessiyadagi belgini o'qiydi) — o'chirishda
        # AYNAN o'sha miqdor omborga qaytadi. Belgi `finally` da olinadi.
        db.info["_brak_qaytarish_id"] = item.id
        try:
            brak_log = services.deduct_raw_material_for_brak(
                db, order_item, order_item.order, float(data.quantity or 0),
                getattr(data, 'coating_applied', False)
            )
        finally:
            db.info.pop("_brak_qaytarish_id", None)
        if brak_log:
            print(f"✓ Brak uchun xomashyo yechildi: {brak_log}")

    # Tayyor mahsulotlar omboriga qo'shamiz (brak bo'lmasa)
    to_stock = getattr(data, 'to_stock', True)
    if to_stock and reason_enum != ReturnReason.DEFECT:
        oi = order_item
        if oi:
            # kech40 (22-band, K39-1): omborga NIMA qo'shilgani yozuvga saqlanadi —
            # o'chirishda AYNAN shu ayiriladi (`delete_return_item`). `commit=False`:
            # yozuv, bog'lam va ombor BITTA tranzaksiyada (ilgari
            # `add_returned_to_stock` o'zi commit qilardi — yozuv bog'lamsiz saqlanib,
            # (101, buyurtma) qulfi yig'indi tekshiruvidan keyin muddatidan oldin
            # bo'shardi).
            _ombor = {}
            fp = add_returned_to_stock(
                db, oi, float(data.quantity), reason_enum.value,
                order_id=data.order_id,
                notes=f"{data.notes or ''}".strip() or None,
                commit=False, natija=_ombor
            )
            if fp:
                item.finished_product_id = fp.id
                item.stock_qty = _ombor.get("qty")
                item.stock_cost = _ombor.get("cost")
                item.stock_volume_m3 = _ombor.get("volume")
                print(f"✓ Tayyor mahsulotlar omboriga: {fp.name} +{data.quantity} {fp.unit}")

    db.commit()
    db.refresh(item)
    return item


# MUHIM (2026-09 — Fasa 3, brak-yozish konsolidatsiyasi): bu yerda avval
# create_finished_product_brak() funksiyasi bo'lgan — Qaytarishlar sahifasi
# ("Ishlab chiqarishdan brak") uchun. U record_finished_product_production_brak()
# (Tayyor mahsulotlar sahifasi) bilan AYNAN bir xil ishni — mahsulot soniga
# tegmasdan, faqat qo'shimcha sarflangan xomashyoni ombordan ayirishni —
# qilardi (ikkalasi ham bir xil "unit_volume_m3/unit_loy_kg" nisbatidan
# foydalanardi). Ikki parallel yo'l chalkashlik va ombor hisobida
# nomuvofiqlik xavfini tug'dirgani uchun, foydalanuvchi tasdig'i bilan,
# BU funksiya OLIB TASHLANDI va endi faqat Tayyor mahsulotlar sahifasidagi
# yagona yo'l (record_finished_product_production_brak, "/api/finished/
# production-brak") ishlatiladi. Eski ReturnItem yozuvlari (bu funksiya
# orqali avval yaratilgan) tarixiy ma'lumot sifatida bazada saqlanib qoladi.


def get_return_items(db: Session, order_id: Optional[int] = None,
                     company_id: int = None) -> List:
    """Barcha qaytarishlar yoki bitta buyurtma bo'yicha."""
    query = db.query(ReturnItem)
    if company_id is not None:
        query = query.filter(ReturnItem.company_id == company_id)
    if order_id:
        query = query.filter(ReturnItem.order_id == order_id)
    return query.order_by(ReturnItem.returned_at.desc()).all()


def get_return_items_for_main_page(db: Session, days: int = 90, show_all: bool = False,
                                   company_id: int = None) -> List:
    """Qaytarishlar sahifasining ASOSIY ro'yxati uchun — tezlik uchun,
    faqat so'nggi `days` kunlikni ko'rsatadi (show_all=True — hammasi)."""
    from datetime import timedelta
    query = db.query(ReturnItem)
    if company_id is not None:
        query = query.filter(ReturnItem.company_id == company_id)
    if not show_all:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(ReturnItem.returned_at >= cutoff)
    return query.order_by(ReturnItem.returned_at.desc()).all()


def get_return_item(db: Session, return_id: int) -> Optional[ReturnItem]:
    return db.query(ReturnItem).filter(ReturnItem.id == return_id).first()


def mark_refunded(db: Session, return_id: int, refunded_by: str = None,
                  company_id: int = None) -> Optional[ReturnItem]:
    """Qaytarishni 'pul qaytarildi' deb belgilaydi VA buni moliyaga to'g'ri
    ta'sir qiladigan qilib yozadi:

    1) Buyurtmaning 'agreed_amount' (kelishilgan summa) — refund_amount ga
       kamaytiriladi. Shu orqali bu pul endi Moliyadagi daromad/foyda
       hisob-kitoblarida (calculate_order_profit agreed_amount'dan
       foydalanadi) AVTOMATIK kamayadi — alohida "kirim" bo'lib qolmaydi.
    2) MANFIY to'lov yozuvi qo'shiladi (mijozga naqd qaytarilgan pul),
       shunda "To'langan" va "Qarz qoldi" ham to'g'ri, izchil qoladi.

    kech40 (5-bo'lim 22-band, FOYDALANUVCHI QARORI B — qaytarish o'chirilsa
    hammasi orqaga qaytadi): manfiy to'lov qaytarishga BOG'LANADI
    (`Payment.return_item_id`), kelishilgan summa AYNAN qanchaga kamaygani
    (`refund_agreed_delta` — `max(0, …)` tufayli summadan kam bo'lishi mumkin)
    va vaqti (`refunded_at` — yangi belgilash belgisi) saqlanadi.
    QULF (101, buyurtma) — to'lovlar va `delete_return_item` bilan bir fazo:
    qulfsiz ikki parallel so'rov ikkalasi ham "hali qaytarilmagan" deb ko'rib
    pulni IKKI marta qaytarardi (UI dagi `inFlightRefundToggle` faqat bitta
    tabni to'sadi); o'chirish bilan poygada esa bog'lamsiz manfiy to'lov
    qolishi mumkin edi. Korxona: `company_id` berilsa yozuv FAQAT shu
    korxonadan (marshrut ham tekshiradi — ikki to'siq)."""
    _rq = db.query(ReturnItem).filter(ReturnItem.id == return_id)
    if company_id is not None:
        _rq = _rq.filter(ReturnItem.company_id == company_id)
    item = _rq.first()
    if not item:
        return None
    if item.is_refunded:
        return item  # Allaqachon qaytarilgan — qayta ishlamaymiz
    # kech42 (FOYDALANUVCHI, so'zma-so'z mazmuni): brak — ishlab chiqarish
    # zarari; mijozga yaroqsiz mahsulot HECH QACHON berilmaydi, buyurtma baribir
    # to'liq tayyorlanadi — demak brak uchun mijozga pul qaytarilmaydi. UI
    # tugmani brakda ko'rsatmaydi, lekin server tekshirmasdi (O'LCHANGAN:
    # `POST /api/returns/{id}/refund` brak yozuviga 200, −25 000 to'lov).
    if item.reason == ReturnReason.DEFECT:
        raise ValueError("Brak — ishlab chiqarish zarari, mijozga pul qaytarilmaydi")
    _cid = item.company_id
    # QULF — `create_delivery` naqshi: yozilmagan o'zgarish yo'qolmasin
    # (`flush`), qulf, so'ng qulf ostida bazadan QAYTA o'qiladi.
    db.flush()
    if item.order_id is not None:
        _pul_qulfi(db, 101, item.order_id)
    db.expire_all()
    item = db.query(ReturnItem).filter(ReturnItem.id == return_id,
                                       ReturnItem.company_id == _cid).first()
    if not item:
        return None             # parallel so'rov o'chirib yuborgan
    if item.is_refunded:
        return item             # parallel so'rov allaqachon belgilagan

    from models import Payment, PaymentType
    refund_amount = float(item.refund_amount or 0)
    order = None
    if item.order_id is not None:
        order = db.query(Order).filter(Order.id == item.order_id,
                                       Order.company_id == _cid).first()
    _kamaydi = 0.0

    _naqd = 0.0
    if refund_amount > 0 and order is not None:
        _eski = order.kelishilgan_summa
        _yangi = max(0.0, _eski - refund_amount)
        order.agreed_amount = _pul2(_yangi)
        _kamaydi = _eski - _yangi

        # kech42 (24-band, qaror: "real hayotdagidek"): to'lanmagan pulni
        # qaytarib bo'lmaydi — qaytgan mahsulot QARZDAN chegiriladi, naqd faqat
        # mijoz ORTIQCHA to'lagan qism uchun: min(summa, max(0, to'langan −
        # yangi kelishilgan)). O'LCHANGAN (asl kod): to'lanmagan buyurtmada 30 m
        # qaytishi −150 000 to'lov yozib, qarzni kelishilgandan katta
        # ko'rsatardi; 200 000 to'langan + 300 000 qaytgan → −300 000 to'lov va
        # qarz 300 000 (asli 0, naqd yo'q). To'liq to'langanda — avvalgidek.
        _tolangan = sum(float(p.amount or 0) for p in (order.payments or []))
        _naqd = _pul2(min(refund_amount, max(0.0, _tolangan - _yangi)))
        if _naqd >= 0.01:
            payment = Payment(
                order_id=order.id,
                return_item_id=item.id,
                amount=-_naqd,
                payment_type=PaymentType.PARTIAL,
                received_by=refunded_by,
                notes=f"Qaytarilgan mahsulot uchun pul qaytarildi: {item.item_name} ({item.quantity} {item.unit})"
            )
            db.add(payment)
            db.flush()
            # 17c: manfiy to'lov loyiha "To'langan" summasiga ham tushadi —
            # ilgari tushmasdi (`total_paid` faqat create/delete_payment da
            # yangilanardi).
            _loyiha_tolangan_yangila(db, order.project)
        # kech42: to'lov holati ham yangilanadi (ilgari yangilanmasdi —
        # O'LCHANGAN: to'liq qaytgan to'langan buyurtma "paid" + qarz 500 000).
        db.flush()
        db.expire(order, ["payments"])
        _update_order_payment_status(db, order)

    item.is_refunded = True
    item.refunded_at = datetime.utcnow()
    item.refund_agreed_delta = _pul2(_kamaydi)
    db.commit()
    db.refresh(item)
    item.naqd_qaytarildi = float(_naqd or 0)   # marshrut xabari uchun (bazaga yozilmaydi)
    return item


def delete_return_item(db: Session, return_id: int, company_id: int = None,
                       performed_by: str = None):
    """Qaytarish yozuvini o'chirish — qaytarish umuman bo'lmagandek.

    Qaytaradi: muvaffaqiyatda dict (doim rost qiymat), topilmasa `False`;
    o'chirib bo'lmasa `ValueError` (marshrut → 400, HECH NARSA o'zgarmaydi).

    kech40 (5-bo'lim 22-band, K39-1) — O'LCHANGAN (asl kod, SQLite va HAQIQIY
    PostgreSQL, `work/probe40.py`): funksiya faqat yozuvni o'chirardi.
      * Omborga qaytgan detal: tayyor mahsulot QOLARDI — qayta kiritilsa ikki
        baravar (10 → 20); qisman sotilgan / band qilingan bo'lsa ham jim 200.
      * "Pul qaytdi" bosilgan: kamaytirilgan kelishilgan summa va manfiy
        to'lov QOLARDI — qayta kiritib yana bosilsa pul IKKI marta qaytarilgan
        bo'lib ko'rinardi (700 000 → 400 000, −300 000 × 2).
    Endi (FOYDALANUVCHI QARORI B, kech40 — "hammasi orqaga qaytsin"):
      1) Ombor: yozuv bilan qo'shilgan AYNAN miqdor / tan narxi / hajm
         (`stock_*`) tayyor mahsulotdan ayiriladi. Bo'sh qoldiq (qoldiq −
         band) yetmasa — rad (mahsulot sotilgan / band / kamaytirilgan).
         Mahsulot faqat shu qaytarishlardan paydo bo'lgan va boshqa hech narsa
         unga ishora qilmasa — butunlay o'chadi (bo'sh "arvoh" karta qolmaydi).
         Mahsulot o'zi o'chirilgan bo'lsa (bog'lam uzilgan) — ayiradigan narsa yo'q.
      2) Pul: `refunded_at` bor (yangi belgilash) — bog'langan manfiy to'lov(lar)
         o'chadi (audit izi bilan), kelishilgan summa `refund_agreed_delta` ga
         tiklanadi, to'lov holati va loyiha "To'langan" summasi qayta
         hisoblanadi. `refunded_at` YO'Q (yangilanishdan oldingi belgilash) va
         pul haqiqatan qaytarilgan — to'lov bog'lami noma'lum → RAD (taxmin
         qilinmaydi).
      3) Brak (kech45, 13-band 6-qadam): shu yozuvga bog'langan ombor
         harakatlari (`InventoryMovement.return_item_id` — brak uchun yechilgan
         penoplast / tayyor loy / loy ingredientlari) miqdori omborga
         QAYTARILADI va harakatlar o'chiriladi — brak xarajati (hisobot va sof
         foyda harakatlardan hisoblanadi) ham yo'qoladi. Bog'lamsiz ESKI brak
         yozuvi — xomashyo avvalgidek qaytmaydi (qaysi harakat ekani noma'lum,
         taxmin qilinmaydi).
         Yangilanishdan OLDINGI omborga qaytgan yozuv (`stock_qty` NULL) —
         ombor bog'lami noma'lum, avvalgidek faqat yozuv o'chadi.
    Hamma tekshiruv O'ZGARTIRISHDAN OLDIN; hammasi BITTA tranzaksiyada
    (`log_activity` o'zi commit qiladi — ishlatilmaydi, audit to'g'ridan).
    QULF (101, buyurtma) — `create_return_item` (yig'indi), `mark_refunded`
    va to'lovlar bilan bir fazo; tayyor mahsulot qatori `FOR UPDATE` (sotuv
    bilan navbat)."""
    from models import ActivityLog, Payment
    _rq = db.query(ReturnItem).filter(ReturnItem.id == return_id)
    if company_id is not None:
        _rq = _rq.filter(ReturnItem.company_id == company_id)
    item = _rq.first()
    if not item:
        return False
    _cid = item.company_id
    db.flush()
    if item.order_id is not None:
        _pul_qulfi(db, 101, item.order_id)
    db.expire_all()
    item = db.query(ReturnItem).filter(ReturnItem.id == return_id,
                                       ReturnItem.company_id == _cid).first()
    if not item:
        return False            # parallel so'rov allaqachon o'chirgan
    order = None
    if item.order_id is not None:
        order = db.query(Order).filter(Order.id == item.order_id,
                                       Order.company_id == _cid).first()

    # ── 1) TEKSHIRUVLAR — hech narsa o'zgartirilmaydi ────────────────
    # kech60 (57-band): o'chirilgan buyurtmaning ORTIQCHA (topshirilmagan, omborga qo'yilgan)
    # qaytarishi o'chirilmaydi — o'chirishda qolgan qism xomashyosi qaytgan, tiklash esa
    # AYNAN o'shani qayta yechadi; qaytarish o'chsa ortiqcha qism buyurtmaga qaytib,
    # tiklashda xomashyo ko'proq yechilardi (simmetriya buziladi).
    if (order is not None and order.is_deleted and item.reason != ReturnReason.DEFECT
            and float(item.ortiqcha_miqdor or 0) > 0.001):
        raise ValueError("Buyurtma o'chirilgan — uning topshirilmagan (ortiqcha) mahsuloti qaytarishini "
                         "o'chirib bo'lmaydi. Avval buyurtmani tiklang")
    _summa = float(item.refund_amount or 0)
    pul_orqaga = bool(item.is_refunded) and _summa > 0 and order is not None
    if pul_orqaga and item.refunded_at is None:
        raise ValueError(
            f"Bu qaytarish uchun mijozga {_summa:,.0f} so'm qaytarilgani tizim yangilanishidan "
            f"OLDIN belgilangan — qaysi to'lov yozuvi ekani saqlanmagan, shuning uchun pulni "
            f"avtomatik bekor qilib bo'lmaydi va qaytarish o'chirilmadi")

    fp = None
    _sq = float(item.stock_qty or 0)
    if _sq > 0 and item.finished_product_id is not None:
        fp = get_finished_product(db, item.finished_product_id, _cid, lock=True)
        if fp is not None:
            _bor = float(fp.quantity or 0)
            _band = float(fp.reserved_quantity or 0)
            _bosh = _bor - _band
            if _bosh + 0.001 < _sq:
                _izoh = f" (qoldiq {_miqdor_matn(max(_bor, 0))}, shundan band {_miqdor_matn(_band)})" if _band > 0 else ""
                raise ValueError(
                    f"Bu qaytarish bilan \"{fp.name}\" omboriga {_miqdor_matn(_sq)} {fp.unit} qo'shilgan, "
                    f"hozir bo'sh qoldig'i {_miqdor_matn(max(_bosh, 0))} {fp.unit}{_izoh} — mahsulot "
                    f"sotilgan, band qilingan yoki kamaytirilgan, shuning uchun qaytarishni o'chirib bo'lmaydi")

    # ── 2) PUL orqaga ────────────────────────────────────────────────
    _tolov_soni = 0
    if pul_orqaga:
        # TENANT: `Payment` da korxona ustuni yo'q — OTA (buyurtma) orqali.
        tolovlar = db.query(Payment).join(Order, Order.id == Payment.order_id).filter(
            Payment.return_item_id == item.id,
            Payment.order_id == order.id,
            Order.company_id == _cid,
        ).order_by(Payment.id).all()
        for p in tolovlar:
            db.add(ActivityLog(
                company_id=_cid, action="deleted", entity_type="payment",
                entity_id=p.id, entity_label=f"Buyurtma {order.order_number}",
                performed_by=performed_by,
                new_value=_tolov_audit_matni(p) + f" · qaytarish #{item.id} o'chirilgani uchun "
                                                  f"(pul qaytarish bekor qilindi)"))
            db.delete(p)
            _tolov_soni += 1
        _asos = float(order.agreed_amount) if order.agreed_amount is not None else float(order.total_amount or 0)
        order.agreed_amount = _pul2(_asos + float(item.refund_agreed_delta or 0))

    # ── 3) OMBOR orqaga ──────────────────────────────────────────────
    def _ayir(eski, qancha):
        _q = float(eski or 0) - float(qancha or 0)
        return 0.0 if _q < 1e-9 else _q
    _fp_ochiriladi = False
    if fp is not None:
        # kech59 (47-band): qo'shilgandagi og'irlikli o'rtachaning TESKARISI (muzlagan birlik tannarx)
        _qb59 = float(fp.quantity or 0)
        _sb59 = float(fp.unit_cost_stable) if fp.unit_cost_stable is not None else 0.0
        fp.quantity = _ayir(fp.quantity, _sq)
        fp.produced_quantity = _ayir(fp.produced_quantity, _sq)
        _qa59 = float(fp.quantity or 0)
        if _sb59 > 0 and _qa59 > 1e-9:
            _yangi_b59 = (_sb59 * _qb59 - float(item.stock_cost or 0)) / _qa59
            if _yangi_b59 > 0:
                fp.unit_cost_stable = _yangi_b59
        fp.cost_price = _pul2(_ayir(fp.cost_price, item.stock_cost))
        fp.volume_m3 = round(_ayir(fp.volume_m3, item.stock_volume_m3), 9)
        _fp_ochiriladi = (fp.source == StockSource.RETURNED
                          and float(fp.quantity or 0) <= 1e-9
                          and float(fp.produced_quantity or 0) <= 1e-9
                          and float(fp.reserved_quantity or 0) <= 1e-9)

    # ── 3b) BRAK xomashyosi orqaga (kech45, 13-band 6-qadam) ─────────
    from models import InventoryMovement as _IM4
    _xom = []
    if item.reason == ReturnReason.DEFECT:
        _harakatlar = db.query(_IM4).filter(
            _IM4.return_item_id == item.id,
            _IM4.company_id == _cid,
            _IM4.movement_type == "out",
        ).order_by(_IM4.id).all()
        for _h in _harakatlar:
            _inv = None
            if _h.inventory_id is not None:
                _inv = db.query(Inventory).filter(
                    Inventory.id == _h.inventory_id,
                    Inventory.company_id == _cid,
                ).with_for_update().first()
            if _inv is not None:
                _inv.stock_quantity = float(_inv.stock_quantity or 0) + float(_h.quantity or 0)
                _xom.append(f"{_inv.item_name} +{_miqdor_matn(float(_h.quantity or 0))} {_inv.unit or ''}".rstrip())
            db.delete(_h)

    _qator = (f"{item.item_name} · {_miqdor_matn(item.quantity or 0)} {item.unit or ''} · "
              f"{item.reason.value if item.reason else '-'}")
    if _xom:
        _qator += " · brak xomashyosi omborga qaytdi: " + "; ".join(_xom)
    if fp is not None:
        _qator += f" · ombordan olindi: {_miqdor_matn(_sq)} {fp.unit} ({fp.name})"
    if pul_orqaga:
        _qator += f" · pul qaytarish bekor qilindi: {_summa:,.0f} so'm (to'lov yozuvi: {_tolov_soni})"
    db.add(ActivityLog(
        company_id=_cid, action="deleted", entity_type="return", entity_id=item.id,
        entity_label=(f"Buyurtma {order.order_number}" if order is not None else "Qaytarish"),
        performed_by=performed_by, new_value=_qator))
    _fp_id = fp.id if fp is not None else None
    db.delete(item)
    db.flush()                  # tashqi kalitlar: to'lov va yozuv mahsulotdan OLDIN

    if _fp_ochiriladi:
        from models import FinishedProductSale as _FPS3, FinishedProductLoss as _FPL3
        _havola = (
            db.query(ReturnItem.id).filter(ReturnItem.finished_product_id == _fp_id,
                                           ReturnItem.company_id == _cid).first()
            or db.query(_FPS3.id).filter(_FPS3.finished_product_id == _fp_id).first()
            or db.query(_FPL3.id).filter(_FPL3.finished_product_id == _fp_id).first()
            or db.query(OrderItem.id).filter(OrderItem.finished_product_id == _fp_id,
                                             OrderItem.company_id == _cid).first()
        )
        if _havola is None:
            try:
                from production_models import ProductionOrder as _PO3
                _havola = db.query(_PO3.id).filter(_PO3.finished_product_id == _fp_id).first()
            except ImportError:
                _havola = None
        if _havola is None:
            db.delete(fp)
            db.flush()
        else:
            _fp_ochiriladi = False

    if pul_orqaga:
        db.expire(order, ["payments"])
        _update_order_payment_status(db, order)
        _loyiha_tolangan_yangila(db, order.project)

    db.commit()
    return {
        "ombordan_olindi": _sq if fp is not None else 0,
        "mahsulot_ochirildi": bool(_fp_ochiriladi),
        "pul_bekor_qilindi": _summa if pul_orqaga else 0,
        "tolov_ochirildi": _tolov_soni,
        "xomashyo_qaytdi": len(_xom),
    }


def get_return_stats(db: Session, company_id: int = None) -> dict:
    """Qaytarishlar statistikasi — jami va shu oy bo'yicha."""
    from datetime import datetime
    from models import ReturnReason, FinishedProductLoss

    _rq = db.query(ReturnItem)
    if company_id is not None:
        _rq = _rq.filter(ReturnItem.company_id == company_id)
    all_returns = _rq.all()
    total_count = len(all_returns)
    total_refund = sum(float(r.refund_amount) for r in all_returns)
    pending_refund = sum(float(r.refund_amount) for r in all_returns if not r.is_refunded)

    by_reason = {}
    for r in ReturnReason:
        by_reason[r.value] = sum(1 for i in all_returns if i.reason == r)

    # Brak qiymati — jami va shu oy
    brak_items = [r for r in all_returns if r.reason == ReturnReason.DEFECT]
    brak_total_value = sum(float(r.refund_amount or 0) for r in brak_items)
    brak_total_count = len(brak_items)

    now = datetime.utcnow()
    month_brak = [r for r in brak_items if r.returned_at and r.returned_at.year == now.year and r.returned_at.month == now.month]
    brak_month_value = sum(float(r.refund_amount or 0) for r in month_brak)
    brak_month_count = len(month_brak)

    # MUHIM (2026-09 chuqur audit — ikkinchi bosqich): "Ishlab chiqarish
    # jarayonidagi brak" (Tayyor mahsulotlar sahifasi) endi ReturnItem EMAS,
    # FinishedProductLoss yaratadi (Fasa 3 konsolidatsiyasidan keyin) —
    # shuning uchun yuqoridagi hisobga UMUMAN kirmaydi va bu stat-kartalar
    # brak faoliyatini kam ko'rsatib qo'yardi. Bu yerda ULARNI HAM qo'shib
    # hisoblaymiz (faqat "ishlab chiqarish braki" belgisi bilan — oddiy
    # "zaxiradan kamaytirish" bu yerga kirmaydi, u haqiqiy brak emas,
    # balki alohida yo'qotish turi).
    _PROD_BRAK_MARKER = _ISH_BRAK_BELGI
    # M4 (2026-09-18) — TENANT: bu so'rov korxona filtrisiz edi — B
    # korxonaning ishlab chiqarish braki A ning brak statistikasiga
    # qo'shilib ketardi.
    _pbq = db.query(FinishedProductLoss).filter(
        FinishedProductLoss.reason.like(f"{_PROD_BRAK_MARKER}%")
    )
    if company_id is not None:
        _pbq = _pbq.filter(FinishedProductLoss.company_id == company_id)
    prod_brak_losses = _pbq.all()
    brak_total_count += len(prod_brak_losses)
    brak_total_value += sum(float(l.cost_amount or 0) for l in prod_brak_losses)
    month_prod_brak = [l for l in prod_brak_losses if l.lost_at and l.lost_at.year == now.year and l.lost_at.month == now.month]
    brak_month_count += len(month_prod_brak)
    brak_month_value += sum(float(l.cost_amount or 0) for l in month_prod_brak)

    whole_items = [r for r in all_returns if r.reason != ReturnReason.DEFECT]
    month_whole = [r for r in whole_items if r.returned_at and r.returned_at.year == now.year and r.returned_at.month == now.month]

    return {
        "total_count": total_count,
        "total_refund": total_refund,
        "pending_refund": pending_refund,
        "by_reason": by_reason,
        "brak_total_value": round(brak_total_value),
        "brak_total_count": brak_total_count,
        "brak_month_value": round(brak_month_value),
        "brak_month_count": brak_month_count,
        "whole_month_count": len(month_whole),
    }


# ============================================================
# PAYMENT — To'lovlar CRUD
# ============================================================

from models import Payment, PaymentType, PaymentMethod, PaymentStatus
from schemas import PaymentCreate


def _update_order_payment_status(db: Session, order: Order) -> None:
    """Buyurtmaning to'lov holatini yangilaydi.
    Qarz to'liq to'lansa — avtomatik arxivga o'tkazadi."""
    agreed = order.kelishilgan_summa
    paid = sum(float(p.amount or 0) for p in (order.payments or []))
    total = float(order.total_amount or 0)

    # kech42 (K42-1): kelishilgan summa 0 (hammasi qaytarilgan / qarz to'liq
    # kechirilgan) va mijozdan qarz yo'q — hisob yopiq. Ilgari bu holda 0
    # "kiritilmagan" deb olinib, jami summa bo'yicha "to'lanmagan" chiqardi.
    # `total > 0` — bo'sh (0 so'mlik) yangi buyurtma arxivga tushib qolmasin.
    if agreed <= 0.005 and total > 0 and paid >= -0.005:
        order.payment_status = PaymentStatus.PAID
        order.is_archived = True
        if not order.closed_at:
            order.closed_at = datetime.utcnow()
    elif paid <= 0:
        order.payment_status = PaymentStatus.UNPAID
        order.is_archived = False
        order.closed_at = None
    elif paid < agreed:
        order.payment_status = PaymentStatus.PARTIAL
        order.is_archived = False
        order.closed_at = None
    else:
        # To'liq to'landi — avtomatik yopish
        order.payment_status = PaymentStatus.PAID
        order.is_archived = True
        if not order.closed_at:
            order.closed_at = datetime.utcnow()


# ============================================================
# PUL AMALLARIDA TAKROR YUBORISH HIMOYASI  (2026-09-20)
# ============================================================
# Buyurtma yaratishda bu himoya allaqachon bor edi (pg_advisory_xact_lock
# + "yaqinda bir xil tarkibli yozuv bormi" tekshiruvi). To'lovlarda esa
# yo'q edi: tugmani ikki marta bosish yoki tarmoq so'rovni qayta yuborishi
# IKKITA to'lov yozuvini yaratardi — ya'ni pul ikki marta hisoblanardi.
#
# Ikki qatlam:
#   1) Qulf — bir vaqtning o'zida kelgan bir xil so'rovlarni NAVBATGA
#      qo'yadi (aks holda ikkalasi ham "takror emas" deb o'tib ketardi)
#   2) Imzo tekshiruvi — qulf ichida, yaqinda AYNAN shunday to'lov
#      bormi deb qaraydi; bo'lsa, yangisini yaratmay, mavjudini qaytaradi

PUL_TAKROR_SONIYA = 8      # buyurtma himoyasidagi oyna bilan bir xil


def _pay_enum(enum_class, qiymat, sukut):
    """Matnni enum ga aylantiradi; noto'g'ri bo'lsa sukutdagini qaytaradi.
    Imzo tekshiruvi va yozish AYNAN bir xil qiymatni ishlatishi uchun
    alohida funksiyaga chiqarilgan."""
    try:
        return enum_class(qiymat)
    except ValueError:
        return sukut


def _pul_qulfi(db: Session, ns: int, kalit) -> None:
    """Tranzaksiya davomida ushlanadigan qulf (faqat PostgreSQL).

    Ikki argumentli shakl ishlatilgan — u `create_order` dagi bir
    argumentli `pg_advisory_xact_lock(project_id)` bilan HECH QACHON
    to'qnashmaydi, chunki Postgres ularni alohida fazoda saqlaydi.
    SQLite'da bunday funksiya yo'q va u yerda bir vaqtlilik muammosi
    ham yo'q — xavfsiz o'tkazib yuboriladi.
    """
    try:
        if db.bind.dialect.name == "postgresql":
            from sqlalchemy import text as _t
            db.execute(_t("SELECT pg_advisory_xact_lock(:ns, :k)"),
                       {"ns": ns, "k": int(kalit)})
    except Exception:
        pass


def _tolov_chegarasi(order, summa: float, confirm_overpay: bool) -> None:
    """Mijoz to'lovining buyurtmaga nisbatan chegaralari — YAGONA manba (17g).

    1) "3 baravar" qoidasi: summa buyurtmaning UMUMIY qiymatidan 3 baravardan
       ko'p bo'lsa — deyarli aniq tasodifiy xato (ortiqcha nol) → `ValueError`.
    2) Qarzdan ko'p summa — `OverpaymentWarning` (marshrut → 409, UI aniq
       tasdiq so'raydi va `confirm_overpay: true` bilan qayta yuboradi).

    17g gacha bu ikki qoida faqat `create_payment` ichida edi; yetkazishdagi
    to'lov (`create_delivery`) `Payment` ni TO'G'RIDAN yozardi va ularni
    chetlab o'tardi — HAQIQIY PostgreSQL da O'LCHANGAN: 1 000 000 so'mlik
    buyurtmaga yetkazish bilan 5 000 000 so'm to'lov jimgina yozildi (qo'lda
    to'lov yo'li xuddi shunday summani 400 bilan rad etadi), ortiqcha to'lov
    tasdig'i ham so'ralmadi. Endi ikkala yo'l AYNAN shu funksiyani chaqiradi."""
    order_total = float(order.total_amount or 0)
    if order_total > 0 and float(summa) > order_total * 3:
        raise ValueError(
            f"Kiritilgan summa ({summa:,.0f}) buyurtma qiymatidan "
            f"({order_total:,.0f}) juda katta — xato bo'lishi mumkin. "
            f"Iltimos, summani tekshirib qayta kiriting."
        )
    current_debt = order.debt_amount
    if float(summa) > current_debt and not confirm_overpay:
        raise OverpaymentWarning(
            amount=float(summa), debt=current_debt,
            excess=float(summa) - current_debt
        )


def create_payment(db: Session, payment_data: PaymentCreate,
                   company_id: int = None) -> Payment:
    """Yangi to'lov qo'shish."""
    # 17f (2026-09-22): ILDIZ — tana QAT'IY, bazaga tegishdan OLDIN (xato →
    # `ValueError`, hech narsa yozilmaydi). HAQIQIY PostgreSQL da O'LCHANGAN:
    # `Infinity` / `1e20` summa pastdagi takror-tekshiruv so'rovida
    # (`Payment.amount == _summa`) 500 berardi; `0.001` → 0 so'mlik to'lov.
    # Marshrut ham tekshiradi; bu qatlam boshqa chaqiruvchilar uchun.
    _clean_val("Payment", _val_dump(payment_data, "Payment"))
    # M2: to'lov FAQAT o'z korxonasining buyurtmasiga yozilishi mumkin.
    _oq = db.query(Order).filter(Order.id == payment_data.order_id)
    if company_id is not None:
        _oq = _oq.filter(Order.company_id == company_id)
    order = _oq.first()
    if not order:
        raise ValueError("Buyurtma topilmadi")

    # ── TAKROR YUBORISH HIMOYASI ───────────────────────────────────────
    # Ortiqcha to'lov ogohlantirishidan OLDIN turishi SHART: birinchi
    # so'rov o'tib bo'lgach qarz kamayadi, shuning uchun takroriy so'rov
    # bu yerga yetib kelsa foydalanuvchiga "ortiqcha to'lov" degan
    # chalg'ituvchi oyna chiqib qolardi.
    _pul_qulfi(db, 101, payment_data.order_id)

    # TENANT: bu so'rovda company_id filtri ATAYLAB yo'q. Payment'da
    # bunday ustun umuman yo'q, filtrlash OTA orqali bo'ladi — va ota
    # (buyurtma) YUQORIDA allaqachon tekshirilgan: boshqa korxonaniki
    # bo'lsa, "Buyurtma topilmadi" xatosi bilan shu yergacha yetib
    # kelinmaydi. Ya'ni bu order_id faqat shu korxonaniki bo'lishi mumkin.
    from datetime import timedelta as _td_pay
    _summa = round(float(payment_data.amount or 0), 2)
    # kech38 (5-bo'lim 13-band): himoya FAQAT qo'lda kiritilgan to'lovlar
    # orasida (`delivery_id IS NULL`). O'LCHANGAN (SQLite va HAQIQIY
    # PostgreSQL 16, asl kod `c7a11f3`): yuk bilan 50 000 naqd to'lov
    # yozilgach 8 s ichida qo'lda kiritilgan 50 000 naqd to'lov JIM yutilardi
    # (javob `duplicate: true`, yangi yozuv yo'q; `orders.html` bu belgini
    # o'qimaydi — foydalanuvchi "saqlandi" ko'rardi). Teskari tartibda (avval
    # qo'lda, keyin yuk bilan) esa ikkalasi yozilardi — ya'ni bu "bir pulni
    # ikki joyda yozish"ga qarshi himoya EMAS, tasodif edi. Himoyaning
    # maqsadi — AYNAN bir so'rovning qayta yuborilishi (ikki bosish, tarmoq
    # takrori); yuk to'lovi qo'lda to'lov so'rovining takrori bo'la olmaydi,
    # uning o'z himoyasi bor (`create_delivery` imzosi).
    _oldingi = db.query(Payment).filter(
        Payment.order_id == payment_data.order_id,
        Payment.delivery_id.is_(None),
        Payment.amount == _summa,
        Payment.payment_type == _pay_enum(PaymentType, payment_data.payment_type,
                                          PaymentType.PARTIAL),
        Payment.payment_method == _pay_enum(PaymentMethod, payment_data.payment_method,
                                            PaymentMethod.CASH),
        Payment.paid_at >= datetime.utcnow() - _td_pay(seconds=PUL_TAKROR_SONIYA),
    ).order_by(Payment.paid_at.desc()).first()
    if _oldingi is not None:
        # main.py shu belgini o'qib, javobda "takroriy" deb ko'rsatadi
        _oldingi._is_duplicate_submit = True
        return _oldingi

    # Xavfsizlik: agar kiritilgan summa buyurtmaning UMUMIY qiymatidan
    # 3 baravardan ko'proq bo'lsa — bu, deyarli aniq, tasodifiy xato
    # (masalan ortiqcha nol qo'shilib ketgan). Kichik-o'rtacha ortiqcha
    # to'lovlar (mijoz qasddan ko'proq to'lasa) — bunga tegilmaydi.
    # Ortiqcha to'lov — qarzdan ko'p summa kiritilsa, aniq tasdiqlash talab qilinadi
    # (ehtiyotkorlik uchun — lekin AVANS sifatida qasddan ko'p to'lash ham mumkin,
    # shuning uchun BUTUNLAY to'smaymiz, faqat tasdiqlashni so'raymiz).
    # 17g: ikkala qoida — `_tolov_chegarasi` (yetkazishdagi to'lov bilan umumiy).
    _tolov_chegarasi(order, payment_data.amount, payment_data.confirm_overpay)

    # Enum ga aylantirish (yuqoridagi imzo tekshiruvi bilan bir xil mantiq)
    p_type = _pay_enum(PaymentType, payment_data.payment_type, PaymentType.PARTIAL)
    p_method = _pay_enum(PaymentMethod, payment_data.payment_method, PaymentMethod.CASH)

    db_payment = Payment(
        order_id=payment_data.order_id,
        amount=payment_data.amount,
        payment_type=p_type,
        payment_method=p_method,
        received_by=payment_data.received_by,
        notes=payment_data.notes
    )
    db.add(db_payment)
    db.flush()

    # Buyurtmani yangilash
    db.refresh(order)
    _update_order_payment_status(db, order)

    # Loyihaning to'langan summasini yangilash (17c: yagona yordamchi)
    _loyiha_tolangan_yangila(db, order.project)

    db.commit()
    db.refresh(db_payment)
    return db_payment


def get_payments(db: Session, order_id: Optional[int] = None,
                 company_id: int = None) -> List[Payment]:
    """To'lovlar ro'yxati.

    2026-09-18 — M2: Payment'da company_id ustuni YO'Q, shuning uchun
    filtrlash OTA (buyurtma) orqali — JOIN bilan."""
    query = db.query(Payment)
    if company_id is not None:
        query = query.join(Order, Order.id == Payment.order_id).filter(
            Order.company_id == company_id)
    if order_id:
        query = query.filter(Payment.order_id == order_id)
    return query.order_by(Payment.paid_at.desc()).all()


def _tolov_audit_matni(payment) -> str:
    """To'lovning audit uchun to'liq tafsiloti (summa, tur, usul, kim qabul
    qilgan, qachon, izoh). kech38: `delete_payment` va `delete_delivery`
    (yuk bilan birga to'lovni o'chirish — 12-band) uchun YAGONA manba."""
    return (
        f"{payment.amount:,.0f} so'm · {payment.payment_type.value if payment.payment_type else '-'} · "
        f"{payment.payment_method.value if payment.payment_method else '-'} · "
        f"qabul qilgan: {payment.received_by or '-'} · "
        f"sana: {payment.paid_at.strftime('%Y-%m-%d %H:%M') if payment.paid_at else '-'}"
        + (f" · izoh: {payment.notes}" if payment.notes else "")
    )


def delete_payment(db: Session, payment_id: int, performed_by: str = None,
                   company_id: int = None) -> bool:
    """To'lovni o'chirish.
    XAVFSIZLIK/AUDIT: o'chirishdan OLDIN to'lovning to'liq tafsiloti
    (summa, usul, buyurtma, kim qabul qilgan, qachon) ActivityLog'ga
    yozib qo'yiladi — shunda to'lov o'chirilgandan keyin ham, KIM,
    QACHON va QANDAY to'lovni o'chirgani abadiy saqlanadi (kelishmovchilik
    yoki xatolikni keyinchalik tekshirish uchun)."""
    # M2: to'lovda company_id yo'q — ota (buyurtma) orqali tekshiriladi.
    _pq = db.query(Payment).filter(Payment.id == payment_id)
    if company_id is not None:
        _pq = _pq.join(Order, Order.id == Payment.order_id).filter(
            Order.company_id == company_id)
    payment = _pq.first()
    if not payment:
        return False

    order = payment.order
    order_label = order.order_number if order else f"#{payment.order_id}"
    detail = _tolov_audit_matni(payment)
    log_activity(
        db, "deleted", "payment", payment.id,
        company_id=getattr(order, 'company_id', None),   # M7
        entity_label=f"Buyurtma {order_label}",
        performed_by=performed_by,
        new_value=detail
    )

    db.delete(payment)
    db.flush()

    if order:
        db.refresh(order)
        _update_order_payment_status(db, order)
        # 17c: yagona yordamchi
        _loyiha_tolangan_yangila(db, order.project)

    db.commit()
    return True


def update_order_agreed_amount(db: Session, order_id: int, agreed_amount: float) -> Optional[Order]:
    """Kelishilgan summani (chegirmadan keyingi narx) yangilash."""
    # 17e (2026-09-22): ILDIZ — summa MUSBAT, chekli, Numeric(12,2) sig'imi
    # ichida (`true`, matn, `Infinity`, 0 — `ValueError`), bazaga tegishdan OLDIN.
    agreed_amount = _clean_val("OrderAgreed", {"agreed_amount": agreed_amount})["agreed_amount"]
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return None

    total = float(order.total_amount or 0)
    order.agreed_amount = agreed_amount

    # Chegirma foizini hisoblash.
    # 28-band (kech43): to'lov panelida xodim JORIY (pul qaytarishdan keyingi)
    # summani ko'rib yangisini yozadi — summa yozilgandek saqlanadi, lekin
    # chegirma foizi (narx chegirmasi) pul qaytarish kamaytirishisiz ASL summadan:
    # aks holda qaytarilgan tovar "chegirma" bo'lib, keyingi qaytarish narxi
    # tushib ketardi (4-band koeffitsienti).
    _asl_qolda = float(agreed_amount) + pul_qaytarish_kamaytirgan(db, order)
    if total > 0 and _asl_qolda < total:
        order.discount_percent = round((total - _asl_qolda) / total * 100, 2)
    else:
        order.discount_percent = 0.0

    _update_order_payment_status(db, order)
    db.commit()
    db.refresh(order)
    return order


def get_delivery_stats(db: Session, company_id: int = None) -> dict:
    """Yetkazish statistikasi — dashboard uchun."""
    _oq = db.query(Order).filter(
        Order.status.notin_([OrderStatus.DRAFT, OrderStatus.CANCELLED]),
        Order.is_deleted.isnot(True)
    )
    if company_id is not None:
        _oq = _oq.filter(Order.company_id == company_id)
    orders = _oq.all()

    partial = []
    not_started = 0
    fully = 0

    for o in orders:
        pct = o.delivery_percent
        if pct >= 100:
            fully += 1
        elif pct > 0:
            partial.append({
                "order_id": o.id,
                "order_number": o.order_number,
                "client_name": o.project.client_name if o.project else "—",
                "percent": pct,
                "items_pending": sum(1 for i in o.items if i.remaining_qty > 0.001),
                "debt_amount": o.debt_amount
            })
        else:
            not_started += 1

    partial.sort(key=lambda x: x["percent"], reverse=True)

    return {
        "fully_delivered": fully,
        "partial_count": len(partial),
        "not_started": not_started,
        "partial_orders": partial[:15]
    }


def get_debt_stats(db: Session, company_id: int = None) -> dict:
    """Qarzdorlik statistikasi — dashboard uchun."""
    _dq = db.query(Order)
    if company_id is not None:
        _dq = _dq.filter(Order.company_id == company_id)
    orders = _dq.filter(
        Order.is_archived == False,
        Order.is_deleted.isnot(True)
    ).all()

    total_agreed = 0.0
    total_paid = 0.0
    debt_orders = []

    for o in orders:
        agreed = o.kelishilgan_summa
        paid = sum(float(p.amount or 0) for p in (o.payments or []))
        debt = max(agreed - paid, 0)

        total_agreed += agreed
        total_paid += paid

        if debt > 0:
            days_passed = (datetime.utcnow() - o.created_at).days if o.created_at else 0
            debt_orders.append({
                "order_id": o.id,
                "order_number": o.order_number,
                "client_name": o.project.client_name if o.project else "—",
                "project_name": o.project.project_name if o.project else "—",
                "agreed_amount": agreed,
                "paid_amount": paid,
                "debt_amount": debt,
                "payment_status": o.payment_status.value if o.payment_status else "unpaid",
                "days_passed": days_passed,
                "is_overdue": days_passed > 30,
                "created_at": o.created_at.isoformat() if o.created_at else None
            })

    debt_orders.sort(key=lambda x: x["debt_amount"], reverse=True)

    # Bugungi to'lovlar
    from database import tashkent_date
    today = tashkent_date()
    # M6 — TENANT: bugungi to'lovlar ham joriy korxona bo'yicha.
    _tpq = db.query(Payment)
    if company_id is not None:
        _tpq = _tpq.join(Order, Order.id == Payment.order_id).filter(
            Order.company_id == company_id)
    today_payments = _tpq.all()
    today_sum = sum(
        float(p.amount or 0) for p in today_payments
        if p.paid_at and tashkent_date(p.paid_at) == today
    )

    return {
        "total_agreed": total_agreed,
        "total_paid": total_paid,
        # MUHIM: bu — har bir buyurtmaning (hech qachon manfiy bo'lmaydigan)
        # qarzlari YIG'INDISI, "jami kelishilgan - jami to'langan" emas.
        # Aks holda, agar ba'zi mijozlar ORTIQCHA to'lagan bo'lsa (masalan
        # oldindan to'lov), umumiy natija noto'g'ri, MANFIY chiqib qolar edi.
        "total_debt": sum(d["debt_amount"] for d in debt_orders),
        "debt_orders_count": len(debt_orders),
        "overdue_count": sum(1 for d in debt_orders if d["is_overdue"]),
        "today_payments": today_sum,
        "debt_orders": debt_orders[:20]
    }


# ============================================================
# DRAFT — Qoralama buyurtmalar
# ============================================================

def activate_draft_order(db: Session, order_id: int, performed_by: str = None) -> dict:
    """Qoralama buyurtmani jarayonga oladi — ombordan xomashyo yechiladi."""
    import services

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    if order.status != OrderStatus.DRAFT:
        return {"success": False, "message": "Bu buyurtma qoralama emas"}

    # Xomashyo yetarliligini tekshiramiz
    check = services.check_inventory_for_order(db, order)
    all_shortages = list(check.get("shortages", []))
    if all_shortages:
        return {
            "success": False,
            "message": "Xomashyo yetishmayapti!",
            "shortages": all_shortages
        }

    # Ombordan penoplast yechamiz
    log = services.deduct_inventory_for_order(db, order)

    # "Loy sotish" detallari — har biri o'z retseptiga ko'ra
    for oi in order.items:
        if (oi.category or '').lower() == 'loy_sotish' and oi.recipe_id and oi.quantity:
            log.extend(services.deduct_loy_ingredients(db, order, float(oi.quantity), recipe_id=oi.recipe_id))

    # Rejalashtirilgan loy (qoplama) bo'lsa — uni ham yechamiz
    planned_loy = services._get_planned_loy(order)
    if planned_loy > 0:
        loy_log = services.deduct_loy_ingredients(db, order, planned_loy)
        log.extend(loy_log)

    # Tayyor mahsulotlarni yechamiz
    log.extend(_take_finished_for_order(db, order))

    order.status = OrderStatus.IN_PROGRESS
    db.commit()
    db.refresh(order)

    # AUDIT: ombordan xomashyo yechiladigan lahza — eng muhim voqealardan
    # biri, shuning uchun kim va qachon bosgani alohida qayd etiladi.
    try:
        log_activity(db, "activated", "order", order.id, order.order_number, performed_by,
                     company_id=getattr(order, 'company_id', None))
    except Exception:
        pass

    return {
        "success": True,
        "message": "Buyurtma jarayonga olindi!",
        "inventory_log": log
    }


# ============================================================
# BUYURTMANI TAHRIRLASH (ombor farq bo'yicha to'g'rilanadi)
# ============================================================
def finalize_partial_order_quantities(db: Session, order) -> dict:
    """Buyurtma QISMAN topshirilgan holatda yakunlanganda —
    har bir detalning miqdorini (va narxini) HAQIQATDA berilgan
    miqdorga moslab qisqartiradi. Boshida yozilgan (lekin berilmagan)
    ortiqcha miqdor — buyurtma yozuvidan ham olib tashlanadi.

    Keyin: jami summa qayta hisoblanadi, to'langan pul bilan solishtiriladi —
    ortiqcha to'lov bo'lsa 'qaytarilishi kerak' deb belgilanadi,
    yetmasa — oddiy qarz sifatida qoladi (avtomatik, debt_amount orqali)."""
    import re as _re

    for item in order.items:
        ordered = item.order_qty_normalized
        if ordered <= 0:
            continue
        # kech60 (57-band): omborga ORTIQCHA qo'yilgan qism ham buyurtmada qoladi — u mijoz
        # uchun ishlab chiqarilgan (pul masalasi — alohida "Pul qaytdi" orqali, 24 / 28-band).
        # Aks holda miqdor topshirilganga tushib, qaytarilgan yig'indi buyurtmadan oshardi.
        delivered = min(item.delivered_qty + item.ortiqcha_qty, ordered)
        fraction = min(delivered / ordered, 1.0)

        old_total = float(item.total_price or 0)
        new_total = round(old_total * fraction, 2)

        cat = (item.category or '').lower()
        if cat == 'profil':
            item.length = delivered
        else:
            item.quantity = delivered
        item.total_price = new_total

    new_total_amount = round(sum(float(i.total_price or 0) for i in order.items), 2)
    old_total_amount = float(order.total_amount or 0)
    order.total_amount = new_total_amount

    discount_pct = float(order.discount_percent or 0)
    # 28-band (kech43, O'LCHANGAN S5): 50 m berilgan, 20 m qaytib pul qaytarilgan
    # buyurtma "Tayyor" bosilganda summa 250 000 bo'lardi (to'g'risi 150 000) —
    # pul qaytarish kamaytirishi QAYTA ayiriladi (manfiy bo'lmaydi).
    _qaytgan_kam = pul_qaytarish_kamaytirgan(db, order)
    new_agreed = round(max(0.0, new_total_amount * (1 - discount_pct / 100) - _qaytgan_kam), 2)
    order.agreed_amount = new_agreed

    paid = order.paid_amount
    overpaid = None
    if paid > new_agreed + 1:
        overpaid = round(paid - new_agreed, 2)
        base_notes = _re.sub(r'\s*\[OVERPAID:[\d.]+\]', '', order.notes or '').strip()
        order.notes = (base_notes + f" [OVERPAID:{overpaid}]").strip()

    # MUHIM (2026-09 audit): summa (agreed_amount) shu yerda kamaytirildi —
    # bu, avvalgi to'lovlarni ENDI "to'liq to'langan"ga aylantirishi mumkin
    # (masalan mijoz 4.5 mln to'lagan, buyurtma 10 mlndan 4.5 mlnga
    # tushirilgan). Bu chaqiruv bo'lmasa, buyurtma "Qisman to'langan" deb
    # ABADIY qolib ketardi va hech qachon avtomatik arxivlanmasdi — garchi
    # qarzi aslida 0 bo'lsa ham.
    _update_order_payment_status(db, order)

    db.commit()
    db.refresh(order)

    return {
        "old_total": old_total_amount,
        "new_total": new_total_amount,
        "new_agreed": new_agreed,
        "paid": paid,
        "overpaid": overpaid,
        "debt": order.debt_amount
    }


# ============================================================
# M7 (2026-09-18) — TENANT-SCOPED BACKUP / RESET uchun umumiy xarita
# ============================================================
# Qaysi jadval qanday cheklanadi:
#   • modelda `company_id` ustuni bor       → to'g'ridan-to'g'ri filtr
#   • yo'q                                   → ota-zanjir orqali (quyida)
#   • ota ham yo'q (global/tizim jadvali)     → tenant amaliga KIRMAYDI
# Faqat repozitoriyadagi HAQIQIY model/ustun nomlari ishlatiladi.
_TENANT_PARENTS = {
    # bola model nomi        : (FK ustuni, ota model nomi)
    "Payment":               ("order_id", "Order"),
    "Delivery":              ("order_id", "Order"),
    "OrderAttachment":       ("order_id", "Order"),
    "OrderGipsAdditive":     ("order_id", "Order"),
    "OrderItemSubDetail":    ("order_item_id", "OrderItem"),
    "DeliveryItem":          ("delivery_id", "Delivery"),
    "InventoryPurchase":     ("inventory_id", "Inventory"),
    "RecipeIngredient":      ("recipe_id", "Recipe"),
    "SupplierPayment":       ("supplier_id", "Supplier"),
    "EmployeeAdvance":       ("employee_id", "Employee"),
    "AdvanceRequest":        ("employee_id", "Employee"),
    "EmployeeCompensationHistory": ("employee_id", "Employee"),
    "EmployeeMonthlyAdjustment":   ("employee_id", "Employee"),
    "GiftPeriodTier":        ("period_id", "GiftPeriod"),
    "GiftPeriodParticipant": ("period_id", "GiftPeriod"),
    "MasterGiftPeriodRedemption": ("period_id", "GiftPeriod"),
    "MasterGiftRedemption":  ("master_id", "Master"),
}

# Tenant amallariga UMUMAN kirmaydigan jadvallar.
#   user_sessions / employee_sessions — xom sessiya TOKENlari (2026-09-15)
#   error_logs                        — modelda `company_id` ustuni YO'Q;
#       to'g'ri ajratish ALTER TABLE talab qiladi → M8 ga qoldirilgan.
_NON_TENANT_TABLES = {"user_sessions", "employee_sessions", "error_logs"}

# Zahira nusxaga HECH QACHON kiritilmaydigan ustunlar.
_SECRET_COLUMNS = {"password_hash", "pin_hash"}


def _tenant_filter(db: Session, model, query, company_id: int):
    """So'rovni berilgan korxona bilan cheklaydi.
    Qaytaradi: (cheklangan_query, True) yoki (None, False) — agar model
    tenantga umuman bog'lanmasa."""
    import models as _m
    if company_id is None:
        return query, True
    if hasattr(model, "company_id"):
        return query.filter(model.company_id == company_id), True
    rule = _TENANT_PARENTS.get(model.__name__)
    if not rule:
        return None, False
    fk, parent_name = rule
    parent = getattr(_m, parent_name, None)
    if parent is None:
        return None, False
    q = query.join(parent, parent.id == getattr(model, fk))
    if hasattr(parent, "company_id"):
        return q.filter(parent.company_id == company_id), True
    # ota ham bevosita tenantga ega emas (masalan DeliveryItem → Delivery)
    sub, ok = _tenant_filter(db, parent, db.query(parent.id), company_id)
    if not ok:
        return None, False
    return query.filter(getattr(model, fk).in_(sub)), True


def export_full_backup(db: Session, company_id: int = None) -> dict:
    """Butun bazaning TO'LIQ zaxira nusxasini (barcha jadvallar, sessiya
    jadvallaridan tashqari) JSON formatida qaytaradi.

    MUHIM (2026-09-15, xavfsizlik tekshiruvi): UserSession va
    EmployeeSession jadvallari ATAYLAB chiqarib tashlangan — ular xom
    sessiya TOKENlarini o'z ichiga oladi, va bu tokenlar hali muddati
    tugamagan bo'lsa, ularni bilgan har qanday kishi parolsiz, o'sha
    foydalanuvchi/xodim nomidan tizimga kira olardi. Zahira nusxa
    ma'lumotni TIKLASH uchun kerak — tiklashdan keyin baribir hamma
    qayta login qilishi kerak bo'ladi, shuning uchun bu ikki jadvalning
    yo'qligi hech narsani buzmaydi, faqat xavfni yo'qotadi."""
    import decimal
    from datetime import datetime as _dt, date as _date
    from enum import Enum as _Enum
    from sqlalchemy import inspect as sa_inspect
    import models as _models

    # Backupga umuman kiritilmaydigan jadvallar — sabab yuqorida yozilgan.
    EXCLUDED_TABLES = set(_NON_TENANT_TABLES)

    def serialize_value(v):
        if v is None:
            return None
        if isinstance(v, decimal.Decimal):
            return float(v)
        if isinstance(v, (_dt, _date)):
            return v.isoformat()
        if isinstance(v, _Enum):
            return v.value
        return v

    # Barcha model klasslarini avtomatik topamiz (User dan tashqari — u ham
    # kiritiladi, chunki to'liq zaxira nusxa deganda HAMMASI saqlanishi kerak)
    # 2026-09-19 — Faza 2: ishlab chiqarish (MRP) jadvallari ALOHIDA
    # modulda e'lon qilingan va shu sababli zaxira nusxaga UMUMAN
    # kirmasdi (`product_types`, `boms`, `bom_items`, `production_orders`).
    # Ya'ni zahiradan tiklaganda butun MRP moduli yo'qolardi. Endi ikkala
    # modul ham ko'rib chiqiladi.
    import production_models as _pmodels
    all_models = []
    _seen_tables = set()
    for _mod in (_models, _pmodels):
        for name in dir(_mod):
            obj = getattr(_mod, name)
            if not (isinstance(obj, type) and issubclass(obj, _models.Base)
                    and obj is not _models.Base):
                continue
            tname = getattr(obj, "__tablename__", None)
            if not tname or tname in EXCLUDED_TABLES or tname in _seen_tables:
                continue
            # `companies` — platforma jadvali, tenant zaxirasiga kirmaydi
            if tname == "companies":
                continue
            _seen_tables.add(tname)
            all_models.append(obj)

    backup = {}
    skipped = []
    for model in all_models:
        table_name = model.__tablename__
        mapper = sa_inspect(model)
        # M7 — XAVFSIZLIK: parol/PIN hashlari zahira nusxaga HECH QACHON
        # kirmaydi (ular tiklash uchun kerak emas; tiklashdan keyin
        # baribir parol qayta belgilanadi).
        columns = [c.key for c in mapper.columns if c.key not in _SECRET_COLUMNS]
        q, ok = _tenant_filter(db, model, db.query(model), company_id)
        if not ok:
            # Tenantga bog'lanmagan jadval — korxona zahirasiga kiritilmaydi.
            skipped.append(table_name)
            continue
        rows = q.all()
        backup[table_name] = [
            {col: serialize_value(getattr(row, col)) for col in columns}
            for row in rows
        ]

    return {
        "backup_created_at": datetime.utcnow().isoformat(),
        "company_id": company_id,
        "skipped_tables": skipped,
        "tables": backup
    }


def _reset_table_order():
    """O'chirish tartibi: har bir "bola" o'z "ota"sidan OLDIN turadi.

    2026-09-19 — Faza 2: bu ro'yxat endi IKKI joyda ishlatiladi —
    `factory_reset_all_data()` (shu tartibda o'chiradi) va
    `import_full_backup()` (TESKARI tartibda qo'shadi). Yagona manba
    bo'lgani uchun ular hech qachon bir-biridan ajralib qolmaydi.
    """
    from production_models import ProductionOrder, BOM, BOMItem, ProductType
    from models import (
        DeliveryItem, Payment, OrderAttachment, ReturnItem, InventoryMovement,
        Delivery, OrderGipsAdditive, OrderItemSubDetail, OrderItem,
        FinishedProductSale, FinishedProductLoss, FinishedProduct, Order,
        InventoryPurchase, InventoryReceipt, SupplierPayment,
        TransportExpense, ExpenseTransaction, MonthlyExpense,
        EmployeeSession, EmployeeAdvance, AdvanceRequest,
        EmployeeMonthlyAdjustment, EmployeeCompensationHistory, Employee,
        RecipeIngredient, Recipe, MasterGiftRedemption, MasterGift,
        MasterGiftPeriodRedemption, GiftPeriodParticipant, GiftPeriodTier,
        GiftPeriod, Master, Project, Supplier, CashTransaction, ActivityLog,
        ErrorLog, LoginHistory, CompanySetting, RecurringObligation, Inventory,
    )
    return [
        ProductionOrder,
        DeliveryItem, Payment, OrderAttachment, ReturnItem, InventoryMovement,
        Delivery, OrderGipsAdditive,
        OrderItemSubDetail, OrderItem,
        FinishedProductSale, FinishedProductLoss, FinishedProduct, Order,
        InventoryPurchase, InventoryReceipt, SupplierPayment,
        TransportExpense, ExpenseTransaction, MonthlyExpense,
        EmployeeSession, EmployeeAdvance, AdvanceRequest,
        EmployeeMonthlyAdjustment, EmployeeCompensationHistory, Employee,
        RecipeIngredient, Recipe,
        BOMItem, BOM, ProductType, Inventory,
        MasterGiftRedemption, MasterGift,
        MasterGiftPeriodRedemption, GiftPeriodParticipant, GiftPeriodTier, GiftPeriod,
        Master, Project, Supplier,
        CashTransaction, ActivityLog, ErrorLog, LoginHistory,
        CompanySetting, RecurringObligation,
    ]


def import_full_backup(db: Session, data: dict, company_id: int,
                       replace: bool = False) -> dict:
    """Zaxira nusxadan korxona ma'lumotini TIKLAYDI (Faza 2).

    NIMA UCHUN KERAK
    ----------------
    Shu paytgacha `export_full_backup()` bor edi, TIKLASH esa YO'Q edi.
    Ya'ni zaxira nusxa olinardi, lekin undan qaytarib bo'lmasdi — baza
    yo'qolsa biznes to'xtardi. Bu funksiya o'sha bo'shliqni yopadi.

    XAVFSIZLIK QOIDALARI
    --------------------
      • Faqat JORIY korxonaga tiklanadi. Fayldagi `company_id` boshqa
        korxonaniki bo'lsa — rad etiladi.
      • Har bir qatorning `company_id` si majburan joriy korxonaga
        o'rnatiladi (fayl ichidagi qiymatga ISHONILMAYDI).
      • Korxona bo'sh bo'lmasa, `replace=True` berilmaguncha rad etiladi.
        `replace=True` bo'lsa avval `factory_reset_all_data()` bilan
        SHU korxona tozalanadi (boshqa korxonalarga tegilmaydi).
      • Hammasi BITTA tranzaksiyada: xato bo'lsa to'liq qaytariladi.
      • `id` qiymatlari SAQLANADI — aks holda jadvallararo bog'lanishlar
        (FK) buziladi. Oxirida PostgreSQL ketma-ketliklari yangilanadi.
      • Sessiya jadvallari va `error_logs` zaxirada yo'q — tiklanmaydi.
      • FOYDALANUVCHI HISOBLARI (`users`) ATAYLAB tiklanmaydi: zaxirada
        parol hashlari yo'q (xavfsizlik uchun chiqarilgan), shuning uchun
        ularni tiklash hech kim kira olmaydigan hisoblar yaratardi.
        Tiklashdan keyin hisoblar qo'lda qayta yaratiladi.
    """
    import decimal
    from datetime import datetime as _dt, date as _date
    from sqlalchemy import inspect as sa_inspect, text as _sa_text

    tables = (data or {}).get("tables")
    if not isinstance(tables, dict):
        return {"success": False, "message": "Fayl formati noto'g'ri: 'tables' topilmadi"}

    file_cid = (data or {}).get("company_id")
    if file_cid is not None and company_id is not None and int(file_cid) != int(company_id):
        return {"success": False,
                "message": f"Bu zaxira boshqa korxonaniki (fayl: {file_cid}). "
                           f"Tiklash rad etildi."}

    # --- Model xaritasi (models + production_models) ---
    import models as _models
    import production_models as _pmodels
    model_by_table = {}
    for _mod in (_models, _pmodels):
        for name in dir(_mod):
            obj = getattr(_mod, name)
            if (isinstance(obj, type) and issubclass(obj, _models.Base)
                    and obj is not _models.Base and hasattr(obj, "__tablename__")):
                model_by_table.setdefault(obj.__tablename__, obj)

    # --- Korxona bo'shmi? ---
    from models import Order as _O, Master as _M, Inventory as _I
    mavjud = (db.query(_O).filter(_O.company_id == company_id).count()
              + db.query(_M).filter(_M.company_id == company_id).count()
              + db.query(_I).filter(_I.company_id == company_id).count())
    if mavjud and not replace:
        return {"success": False,
                "message": f"Korxonada allaqachon ma'lumot bor ({mavjud} ta asosiy yozuv). "
                           f"Ustiga yozish uchun replace=true bering."}

    def coerce(col, v):
        """Matn ko'rinishidagi qiymatni ustun turiga moslaydi.

        MUHIM (jonli mashqda aniqlangan): zaxiraga Enum qiymati sifatida
        `.value` yoziladi (masalan "product"), SQLAlchemy esa bazada
        Enum NOMINI saqlaydi ("PRODUCT"). Shuning uchun tiklashda qiymat
        qayta Enum a'zosiga aylantiriladi — aks holda buyurtma turi
        o'qilmay, `LookupError` beradi."""
        if v is None:
            return None
        # Enum ustuni — qiymatdan a'zoga qaytaramiz
        enum_cls = getattr(col.type, "enum_class", None)
        if enum_cls is not None and not isinstance(v, enum_cls):
            try:
                return enum_cls(v)              # qiymat bo'yicha ("product")
            except (ValueError, KeyError):
                try:
                    return enum_cls[str(v)]     # nom bo'yicha ("PRODUCT")
                except (ValueError, KeyError):
                    return None
        t = str(col.type).upper()
        if isinstance(v, str) and ("DATETIME" in t or "TIMESTAMP" in t):
            try:
                return _dt.fromisoformat(v)
            except ValueError:
                return None
        if isinstance(v, str) and t.startswith("DATE"):
            try:
                return _date.fromisoformat(v)
            except ValueError:
                return None
        if isinstance(v, float) and "NUMERIC" in t:
            return decimal.Decimal(str(v))
        return v

    try:
        if replace and mavjud:
            factory_reset_all_data(db, company_id=company_id)

        # Tartib: o'chirish tartibining TESKARISI — ota avval, bola keyin.
        order = list(reversed(_reset_table_order()))
        inserted, skipped_tables = {}, []

        for model in order:
            tname = model.__tablename__
            rows = tables.get(tname)
            if not rows:
                continue
            mapper = sa_inspect(model)
            cols = {c.key: c for c in mapper.columns}
            payload = []
            for r in rows:
                rec = {}
                for k, v in (r or {}).items():
                    if k not in cols:
                        continue          # sxema o'zgargan — noma'lum ustun tashlanadi
                    rec[k] = coerce(cols[k], v)
                if "company_id" in cols:
                    rec["company_id"] = company_id   # faylga ISHONMAYMIZ
                if rec:
                    payload.append(rec)
            if payload:
                db.execute(model.__table__.insert(), payload)
                inserted[tname] = len(payload)

        for tname in tables:
            if tname not in {m.__tablename__ for m in order}:
                skipped_tables.append(tname)

        # --- PostgreSQL ketma-ketliklarini yangilaymiz ---
        # `id` lar aniq berilgani uchun avtomatik hisoblagich orqada qoladi;
        # tuzatilmasa keyingi yangi yozuv "duplicate key" xatosi beradi.
        seq_fixed = 0
        if db.bind.dialect.name == "postgresql":
            for model in order:
                tname = model.__tablename__
                if tname not in inserted or not hasattr(model, "id"):
                    continue
                try:
                    db.execute(_sa_text(
                        f"SELECT setval(pg_get_serial_sequence('{tname}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM {tname}), 1), true)"))
                    seq_fixed += 1
                except Exception:
                    pass

        db.commit()
        return {"success": True, "company_id": company_id,
                "restored_tables": len(inserted),
                "restored_rows": sum(inserted.values()),
                "per_table": inserted,
                "skipped_tables": skipped_tables,
                "sequences_fixed": seq_fixed}
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Tiklashda xato: {e}"}


def factory_reset_all_data(db: Session, keep_only_user_id: int = None,
                          company_id: int = None) -> dict:
    """DIQQAT: BU QAYTARIB BO'LMAYDIGAN AMAL!
    Foydalanuvchilar (User) dan TASHQARI — barcha ma'lumotni butunlay o'chiradi:
    buyurtmalar, ombor, retseptlar, ustalar, yetkazib beruvchilar, loyihalar,
    tayyor mahsulotlar, qaytarishlar, xarajatlar, xodimlar — HAMMASI.

    keep_only_user_id — agar berilsa, shu ID'dan BOSHQA barcha User (login)
    hisoblari HAM o'chiriladi (masalan, admin "faqat men qolayin, sinov uchun
    yaratgan boshqa hisoblarni ham tozalang" desa).

    Chet el kaliti (ForeignKey) xatosi bermasligi uchun, jadvallar to'g'ri
    (avval "bola", keyin "ota") tartibda tozalanadi."""
    from models import (
        DeliveryItem, Payment, OrderAttachment, ReturnItem, Delivery,
        OrderItem, Order, InventoryMovement, InventoryPurchase, InventoryReceipt,
        SupplierPayment, FinishedProduct, TransportExpense,
        ExpenseTransaction, MonthlyExpense, EmployeeSession, EmployeeAdvance,
        AdvanceRequest, Employee, RecipeIngredient, Recipe, Inventory, Master, Project, Supplier,
        CashTransaction, ActivityLog, ErrorLog, LoginHistory, UserSession, User,
        OrderGipsAdditive, FinishedProductSale, FinishedProductLoss, EmployeeMonthlyAdjustment,
        CompanySetting, RecurringObligation, MasterGift, MasterGiftRedemption,
        # 2026-09-18 — FK TARTIBI TUZATISHI: quyidagi "bola" jadvallar
        # ro'yxatda YO'Q edi, shuning uchun ota yozuv o'chirilganda
        # PostgreSQL chet el kaliti amalni to'xtatardi (staging'da
        # `employee_compensation_history_employee_id_fkey` bilan 500 chiqdi).
        # SQLite'da bu ko'rinmagan — u FK ni standart holatda tekshirmaydi.
        OrderItemSubDetail, EmployeeCompensationHistory,
        GiftPeriodParticipant, GiftPeriodTier, GiftPeriod,
        MasterGiftPeriodRedemption
    )
    # Ishlab chiqarish (MRP) jadvallari alohida modulda — ular ham
    # `orders`, `order_items`, `finished_products`, `inventory` ga ishora
    # qiladi, shuning uchun reset zanjiriga kiritilishi SHART.
    from production_models import ProductionOrder, BOM, BOMItem, ProductType

    # Tartib MUHIM va TO'LIQ tekshirilgan (har bir ForeignKey hisobga olingan):
    # 1) DeliveryItem — deliveries, order_items ga bog'langan
    # 2) Payment — orders, deliveries ga bog'langan
    # 3) OrderAttachment — orders ga bog'langan
    # 4) ReturnItem — orders ga bog'langan
    # 5) InventoryMovement — inventory, orders, suppliers ga bog'langan
    # 6) Delivery — orders ga bog'langan (DeliveryItem, Payment dan keyin xavfsiz)
    # 6b) OrderGipsAdditive — orders, inventory ga bog'langan, Order'dan OLDIN tozalanishi SHART
    # 7) OrderItem — orders, recipes, inventory, finished_products ga bog'langan
    # 7b) FinishedProductSale, FinishedProductLoss — finished_products ga bog'langan,
    #     FinishedProduct'dan OLDIN tozalanishi SHART
    # 8) FinishedProduct — orders, inventory, recipes ga bog'langan (OrderItem dan keyin)
    # 9) Order — endi barcha "bolalari" tozalangan, xavfsiz
    # 10) InventoryPurchase — inventory, suppliers, inventory_receipts ga bog'langan
    # 11) InventoryReceipt — suppliers ga bog'langan, InventoryPurchase'dan OLDIN emas, KEYIN tozalanadi
    #     (chunki InventoryPurchase.receipt_id shu jadvalga ishora qiladi — bola avval, ota keyin)
    # 12) SupplierPayment — suppliers ga bog'langan
    # 13-16) Mustaqil jadvallar
    # 17-19) EmployeeSession/EmployeeAdvance/AdvanceRequest — employees ga bog'langan,
    #        Employee'dan OLDIN tozalanishi SHART (bulk delete cascade ishlatmaydi)
    # 19b) EmployeeMonthlyAdjustment — employees ga bog'langan, Employee'dan OLDIN
    # 20) Employee — endi xavfsiz
    # 21) RecipeIngredient — recipes VA inventory ga bog'langan, Recipe/Inventory'dan OLDIN tozalanishi SHART
    # 22) Recipe — endi xavfsiz (OrderItem, FinishedProduct, RecipeIngredient tozalangan)
    # 23) Inventory — endi xavfsiz
    # 24) Master, 25) Project — endi xavfsiz (Order tozalangan)
    # 26) Supplier — endi xavfsiz (InventoryReceipt, InventoryPurchase, SupplierPayment, InventoryMovement tozalangan)
    # 27) CashTransaction, 28) ActivityLog — mustaqil, sinov izlarini tozalash uchun
    # ── AYLANMA BOG'LANISHNI UZISH ──────────────────────────────
    # `order_items.finished_product_id` → finished_products VA
    # `finished_products.reserved_for_order_item_id` → order_items —
    # ikkisi BIR-BIRIGA ishora qiladi, shuning uchun qay biri birinchi
    # o'chirilsa ham FK buziladi. Loyihada allaqachon ishlatiladigan
    # naqsh (`delete_order`, `delete_finished_product`): AVVAL bog'lanishni
    # uzish, KEYIN o'chirish. Faqat JORIY korxona qatorlari uziladi.
    _unlink_oi = db.query(OrderItem)
    _unlink_fp = db.query(FinishedProduct)
    if company_id is not None:
        _unlink_oi = _unlink_oi.filter(OrderItem.company_id == company_id)
        _unlink_fp = _unlink_fp.filter(FinishedProduct.company_id == company_id)
    _oi_ids = [r[0] for r in _unlink_oi.with_entities(OrderItem.id).all()]
    _fp_ids = [r[0] for r in _unlink_fp.with_entities(FinishedProduct.id).all()]
    if _oi_ids:
        db.query(OrderItem).filter(OrderItem.id.in_(_oi_ids)).update(
            {"finished_product_id": None}, synchronize_session=False)
    if _fp_ids:
        db.query(FinishedProduct).filter(FinishedProduct.id.in_(_fp_ids)).update(
            {"reserved_for_order_item_id": None}, synchronize_session=False)
    db.flush()

    tables_in_order = _reset_table_order()


    # M7 (2026-09-18) — TENANT: bu amal butun bazani (BARCHA korxonani)
    # o'chirardi. Endi `company_id` berilsa FAQAT shu korxonaning
    # ma'lumoti tozalanadi; boshqa korxonalarga umuman tegilmaydi.
    # Cheklash `_tenant_filter()` orqali — backup bilan AYNAN bir xil
    # xarita, shuning uchun "backupda bor, resetda yo'q" nomuvofiqligi
    # bo'lishi mumkin emas.
    counts = {}
    skipped = []
    for model in tables_in_order:
        q, ok = _tenant_filter(db, model, db.query(model), company_id)
        if not ok:
            # Tenantga bog'lanmagan jadval (masalan error_logs) — korxona
            # reseti unga TEGMAYDI.
            skipped.append(model.__tablename__)
            continue
        if company_id is None:
            n = db.query(model).delete(synchronize_session=False)
        elif hasattr(model, "company_id"):
            # Ustunning O'ZIDA korxona bor — to'g'ridan-to'g'ri (bu yo'l
            # `id` ustuni bo'lmagan jadvallarni ham qamraydi, masalan
            # CompanySetting: uning kaliti (company_id, key)).
            n = db.query(model).filter(model.company_id == company_id).delete(
                synchronize_session=False)
        else:
            # Ota orqali: avval ID lar yig'iladi, keyin o'chiriladi.
            ids = [r[0] for r in q.with_entities(model.id).all()]
            n = db.query(model).filter(model.id.in_(ids)).delete(
                synchronize_session=False) if ids else 0
        counts[model.__tablename__] = n
    if skipped:
        counts["_skipped_tables"] = skipped

    if keep_only_user_id is not None:
        # Boshqa foydalanuvchilarning sessiyalarini avval tozalaymiz (FK xatosi bo'lmasligi uchun)
        _uq = db.query(User.id).filter(User.id != keep_only_user_id)
        if company_id is not None:      # M7: faqat SHU korxona hisoblari
            _uq = _uq.filter(User.company_id == company_id)
        other_user_ids = [u.id for u in _uq.all()]
        if other_user_ids:
            db.query(UserSession).filter(UserSession.user_id.in_(other_user_ids)).delete(synchronize_session=False)
            n_users = db.query(User).filter(User.id.in_(other_user_ids)).delete(synchronize_session=False)
        else:
            n_users = 0
        counts["users"] = n_users

    db.commit()
    return counts
def _retsept_nomi53(r) -> str:
    """kech63 (53-band): retsept nomi xabar / jurnal uchun (nom enum yoki matn bo'lishi mumkin)."""
    n = getattr(r, 'name', None)
    return str(getattr(n, 'value', n) or '')


def update_order_full(db: Session, order_id: int, order_data, confirm_shortage: bool = False, performed_by: str = None) -> dict:
    """Buyurtmani to'liq yangilaydi:
    - Detallarni almashtiradi
    - Omborni faqat FARQ miqdorida to'g'rilaydi
    - Buyurtma raqami, to'lovlar, sana saqlanadi
    """
    import services
    import re

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}
    # kech41 (5-bo'lim 14-band, K41-1) — QULF (101, buyurtma), yetkazish /
    # to'lov / qaytarish bilan BIR fazo. HAQIQIY PostgreSQL da O'LCHANGAN
    # (asl kod, `work/probe41.py`, 3 / 3 urinish): qulfsiz "topshirilgan"
    # tekshiruvi bir vaqtdagi yetkazishni ko'rmasdi —
    # butun buyurtma tahriri (`PUT /api/orders/{id}` — UI dagi "Tahrirlash")
    # ham xuddi `update_order_item` / `delete_order_item` kabi "topshirilgan"
    # miqdorni qulfsiz o'qirdi.
    # Naqsh `create_delivery` / `delete_delivery` dagi bilan bir xil:
    # yozilmagan o'zgarish yo'qolmasin (`flush`), qulf, so'ng qulf ostida
    # bazadan QAYTA o'qiladi (`expire_all`).
    _cid_q = order.company_id
    db.flush()
    _pul_qulfi(db, 101, order.id)
    db.expire_all()
    order = db.query(Order).filter(Order.id == order_id, Order.company_id == _cid_q).first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    if order.status == OrderStatus.READY:
        return {"success": False, "message": "Tayyor buyurtmani tahrirlab bo'lmaydi"}

    # AUDIT uchun — tahrirlashdan OLDINGI qisqa holatni saqlab qo'yamiz
    _audit_before = f"Jami: {float(order.total_amount or 0):,.0f} so'm, {len(order.items)} ta detal".replace(',', ' ')

    # 1) Eski detallarni snapshot qilamiz (ombor hisobi uchun)
    old_snapshot = [{
        "category": i.category,
        "width": i.width,
        "thickness": i.thickness,
        "length": i.length,
        "quantity": float(i.quantity or 1),
        "unit_price": float(i.unit_price or 0),
        # MUHIM: "Donalik" hajmi shu (qulflangan) narxdan hisoblanadi
        # (_item_volume_m3 ga qarang). Bu yerda BO'LMASA, hajm noto'g'ri
        # (joriy — o'zgargan bo'lishi mumkin bo'lgan — unit_price'dan)
        # qayta hisoblanib, HAR BIR tahrirlashda xomashyo sabab-siz
        # "qaytib"/"ayirilib" ketardi (garchi hech narsa o'zgarmagan bo'lsa ham).
        "unit_price_for_volume": float(i.unit_price_for_volume) if i.unit_price_for_volume is not None else None,
        "penoplast_id": i.penoplast_id,
        "price_per_m3": float(i.price_per_m3) if i.price_per_m3 else None,
        "finished_product_id": i.finished_product_id,
        # Ichki qo'shimcha detallar — omborni FARQ bo'yicha to'g'ri
        # hisoblash uchun (bo'lmasa, tahrirlashda ularning hajmi "yo'q
        # bo'lib qolgandek" hisoblanib, xomashyo noto'g'ri qaytarilardi).
        "sub_details": [{
            "category": s.category, "width": s.width, "thickness": s.thickness,
            "length": s.length, "quantity": s.quantity,
        } for s in (i.sub_details or [])],
    } for i in order.items]

    # "Loy sotish" — eski holatni recipe_id bo'yicha jamlab olamiz (keyinroq
    # farq hisoblanadi, chunki old_snapshot'da recipe_id saqlanmaydi)
    old_loysale_by_recipe = {}
    for i in order.items:
        if (i.category or '').lower() == 'loy_sotish' and i.recipe_id:
            old_loysale_by_recipe[i.recipe_id] = old_loysale_by_recipe.get(i.recipe_id, 0) + float(i.quantity or 0)

    new_snapshot = [{
        "category": it.category,
        "width": it.width,
        "thickness": it.thickness,
        "length": it.length,
        "quantity": float(it.quantity or 1),
        "unit_price": float(it.unit_price or 0),
        "unit_price_for_volume": getattr(it, 'unit_price_for_volume', None),
        "penoplast_id": getattr(it, 'penoplast_id', None),
        "price_per_m3": getattr(it, 'price_per_m3', None),
        "finished_product_id": getattr(it, 'finished_product_id', None),
        "sub_details": [{
            "category": sd.category, "width": sd.width, "thickness": sd.thickness,
            "length": sd.length, "quantity": sd.quantity,
        } for sd in (getattr(it, 'sub_details', None) or [])],
    } for it in order_data.items]

    is_draft = order.status == OrderStatus.DRAFT
    # kech58 (K58-3): tahrirdan OLDINGI qoplama retsepti — umumiy loy SHUNDAN yechilgan.
    _qr58_oldin = services.resolve_recipe(db, company_id=order.company_id, order=order)
    # kech63 (53-band): tahrirdan OLDINGI foydalanuvchi TANLOVI (YANGI qoida — detallardan; UI shu
    # tanlovni ko'rsatadi) va umumiy loy REJASI (shu `_qr58_oldin` retseptidan yechilgan miqdor).
    _qr53_tanlov_oldin = None if is_draft else services.buyurtma_qoplama_retseptini_tanla(db, order)
    _loy53 = 0.0 if is_draft else float(services._get_planned_loy(order) or 0)

    # 2) Qoralama bo'lmasa — xomashyo yetishini tekshiramiz
    if not is_draft:
        check = services.check_inventory_diff(db, old_snapshot, new_snapshot,
                                              company_id=order.company_id)
        _all_short = []
        if not check["enough"]:
            _all_short += list(check["shortages"])
        # Yetishmovchilik bor-u, lekin foydalanuvchi hali tasdiqlamagan bo'lsa —
        # "davom etasizmi?" ogohlantirishini qaytaramiz (create bilan bir xil).
        # confirm_shortage=True bo'lsa — o'tkazib yuboramiz (ombor manfiy bo'ladi).
        if _all_short and not confirm_shortage:
            return {
                "success": False,
                "type": "stock_shortage_warning",
                "message": "Omborda yetishmayotgan xomashyo bor. Shunday ham davom etasizmi?",
                "shortages": _all_short
            }

    # 3) TOPSHIRISH TEKSHIRUVI — topshirilgandan kam qilib bo'lmaydi
    old_items = list(order.items)
    delivery_errors = []

    def _qty_of(it_data):
        """Yangi detal miqdori (profil — metr, qolganlar — dona)."""
        cat = (it_data.category or '').lower()
        if cat == 'profil':
            return float(it_data.length or 0)
        return float(it_data.quantity or 0)

    # Eski detallarni yangilar bilan moslashtiramiz (nom + tur bo'yicha)
    matched = {}       # old_item.id -> new_item_data
    used_new = set()

    for oi in old_items:
        key = ((oi.name or '').strip().lower(), (oi.category or '').lower())
        for idx, nd in enumerate(order_data.items):
            if idx in used_new:
                continue
            nkey = ((nd.name or '').strip().lower(), (nd.category or '').lower())
            if key == nkey:
                matched[oi.id] = nd
                used_new.add(idx)
                break

    # Tekshiramiz
    for oi in old_items:
        delivered = oi.delivered_qty
        # kech60 (57-band, K59-3): omborga ortiqcha qo'yilgan qism ham chiqqan — undan kam
        # qilib / o'chirib bo'lmaydi. O'LCHANGAN (asl kod): 10 m dan 5 m omborga qo'yilib
        # 10 -> 3 m qilinsa penoplast 7 m uchun qaytardi VA 5 m tayyor mahsulot qolardi.
        _ortiqcha_f = oi.ortiqcha_qty
        if _ortiqcha_f > 0.001:
            _nd_f = matched.get(oi.id)
            _kamida_f = delivered + _ortiqcha_f
            if _nd_f is None:
                delivery_errors.append(
                    f"«{oi.name}» — {_miqdor_matn(_ortiqcha_f)} {oi.delivery_unit} ortiqcha mahsulot "
                    f"omborga qaytarilgan, o'chirib bo'lmaydi (avval qaytarishni o'chiring)")
                continue
            _new_f = _qty_of(_nd_f)
            if _new_f < _kamida_f - 0.001:
                delivery_errors.append(
                    f"«{oi.name}» — {_miqdor_matn(_ortiqcha_f)} {oi.delivery_unit} omborga ortiqcha "
                    f"qaytarilgan" + (f", {delivered:g} {oi.delivery_unit} topshirilgan" if delivered > 0.001 else "")
                    + f" — {_new_f:g} qilib bo'lmaydi (kamida {_miqdor_matn(_kamida_f)})")
                continue
        if delivered <= 0.001:
            continue          # topshirilmagan — hech qanday cheklov yo'q

        nd = matched.get(oi.id)
        if nd is None:
            delivery_errors.append(
                f"«{oi.name}» — {delivered:g} {oi.delivery_unit} topshirilgan, o'chirib bo'lmaydi"
            )
            continue

        new_qty = _qty_of(nd)
        if new_qty < delivered - 0.001:
            delivery_errors.append(
                f"«{oi.name}» — {delivered:g} {oi.delivery_unit} topshirilgan, "
                f"{new_qty:g} qilib bo'lmaydi (kamida {delivered:g})"
            )

    if delivery_errors:
        return {
            "success": False,
            "message": "Topshirilgan miqdordan kam qilib bo'lmaydi!",
            "shortages": delivery_errors
        }

    # 4) Detallarni yangilaymiz — topshirilganlarini SAQLAB
    total_amount = 0
    keep_ids = set()

    for oi in old_items:
        nd = matched.get(oi.id)
        if nd is None:
            # Yangi ro'yxatda yo'q — o'chiramiz (topshirilmagani tekshirildi)
            db.delete(oi)
            continue

        # MUHIM TUZATISH (2026-09 audit): "dona" uchun qo'shimcha ×2
        # qilinmaydi endi — sabab yuqoridagi create_order()dagi izohda
        # (frontend allaqachon yakuniy, qoplamali narx yuboradi).
        _stored_up1 = float(nd.unit_price or 0)
        item_total = _stored_up1 * float(nd.quantity or 1)
        total_amount += item_total

        oi.width = nd.width
        oi.thickness = nd.thickness
        oi.length = nd.length
        oi.quantity = nd.quantity
        oi.is_coated = nd.is_coated
        # MUHIM TUZATISH: avval BARCHA detallarning recipe_id'si, ularning
        # O'Z tanlovidan qat'i nazar, buyurtma darajasidagi (order_data.
        # recipe_id) BITTA umumiy qiymat bilan ALMASHTIRILAR edi. Bu, "loy
        # sotish" detallari (masalan "Qoplama kvars") o'zining to'g'ri
        # retseptini yuborgan bo'lsa ham, uni buyurtmaning umumiy (masalan
        # qoplama uchun tanlangan) retsepti bilan bosib qo'yardi — natijada
        # noto'g'ri xomashyo hisoblanardi. Endi — har bir detal, AGAR O'Z
        # retseptini yuborgan bo'lsa, O'SHANI saqlaydi; faqat yubormagan
        # (masalan qoplamali profil/panel) detallar uchun buyurtmaning
        # umumiy retseptiga tushadi.
        oi.recipe_id = getattr(nd, 'recipe_id', None) or order_data.recipe_id
        oi.penoplast_id = getattr(nd, 'penoplast_id', None)
        oi.price_per_m3 = getattr(nd, 'price_per_m3', None)
        oi.finished_product_id = getattr(nd, 'finished_product_id', None)
        oi.unit_price = _stored_up1
        oi.unit_price_for_volume = getattr(nd, 'unit_price_for_volume', None)
        oi.product_type_id = getattr(nd, 'product_type_id', None)
        oi.total_price = item_total
        oi.notes = nd.notes

        # Ichki qo'shimcha detallarni ALMASHTIRAMIZ — eskisini o'chirib
        # (cascade="all, delete-orphan"), yangisini yozamiz. Ombordagi
        # FARQ — old_snapshot/new_snapshot orqali, pastda, o'zi to'g'ri
        # hisoblanadi (sub_details ham shu snapshotlarga kiritilgan).
        import services as _svc_sub
        oi.sub_details.clear()
        _sub_bp = float(getattr(nd, 'price_per_m3', None) or getattr(order_data, 'base_price', None) or 0)
        for sd in (getattr(nd, 'sub_details', None) or []):
            sub_vol, sub_price = _svc_sub._calc_dim_volume_price(
                sd.category, sd.width, sd.thickness, sd.length, sd.quantity, _sub_bp, sd.is_coated
            )
            oi.sub_details.append(OrderItemSubDetail(
                name=sd.name, category=sd.category, width=sd.width, thickness=sd.thickness,
                length=sd.length, quantity=sd.quantity, is_coated=sd.is_coated,
                volume_m3=sub_vol, total_price=sub_price
            ))

        keep_ids.add(oi.id)

    # Yangi qo'shilgan detallar
    for idx, nd in enumerate(order_data.items):
        if idx in used_new:
            continue
        # MUHIM TUZATISH (2026-09 audit): "dona" uchun qo'shimcha ×2
        # qilinmaydi endi — sabab yuqoridagi create_order()dagi izohda.
        _stored_up2 = float(nd.unit_price or 0)
        item_total = _stored_up2 * float(nd.quantity or 1)
        total_amount += item_total
        _new_item_notes = nd.notes
        _new_oi = OrderItem(
            order_id=order.id,
            name=nd.name,
            category=nd.category,
            width=nd.width,
            thickness=nd.thickness,
            length=nd.length,
            quantity=nd.quantity,
            is_coated=nd.is_coated,
            recipe_id=(getattr(nd, 'recipe_id', None) or order_data.recipe_id),
            penoplast_id=getattr(nd, 'penoplast_id', None),
            price_per_m3=getattr(nd, 'price_per_m3', None),
            finished_product_id=getattr(nd, 'finished_product_id', None),
            unit_price=_stored_up2,
            unit_price_for_volume=getattr(nd, 'unit_price_for_volume', None),
            product_type_id=getattr(nd, 'product_type_id', None),
            total_price=item_total,
            notes=_new_item_notes
        )
        import services as _svc_sub2
        _sub_bp2 = float(getattr(nd, 'price_per_m3', None) or getattr(order_data, 'base_price', None) or 0)
        for sd in (getattr(nd, 'sub_details', None) or []):
            sub_vol, sub_price = _svc_sub2._calc_dim_volume_price(
                sd.category, sd.width, sd.thickness, sd.length, sd.quantity, _sub_bp2, sd.is_coated
            )
            _new_oi.sub_details.append(OrderItemSubDetail(
                name=sd.name, category=sd.category, width=sd.width, thickness=sd.thickness,
                length=sd.length, quantity=sd.quantity, is_coated=sd.is_coated,
                volume_m3=sub_vol, total_price=sub_price
            ))
        db.add(_new_oi)

    # 5) Buyurtma ma'lumotlarini yangilaymiz
    order.master_id = order_data.master_id
    if getattr(order_data, 'deadline', None):
        order.deadline = order_data.deadline

    old_total = float(order.total_amount or 0)
    old_discount_pct = float(order.discount_percent or 0)
    # 28-band (kech43, K42-2 — O'LCHANGAN, `work/probe43.py`): kelishilgan summa
    # ikki qismdan iborat — ASL kelishilgan narx (chegirma / ustama bilan) va pul
    # qaytarishlar kamaytirishi (`pul_qaytarish_kamaytirgan`). Tahrir ASL summani
    # oladi (UI formasi ham ASL summani ko'rsatadi — `/api/orders/{id}`
    # `kelishilgan_asl`), saqlanganda pul qaytarish kamaytirishi QAYTA ayiriladi.
    # Chegirma foizi — faqat narx chegirmasi (ASL summadan).
    _qaytgan_kam = pul_qaytarish_kamaytirgan(db, order)
    _eski_asl = order.kelishilgan_summa + _qaytgan_kam
    order.total_amount = total_amount
    order.base_price = getattr(order_data, 'base_price', None)

    agreed = getattr(order_data, 'agreed_amount', None)

    if agreed:
        # Xodim qo'lda (ASL) summa kiritdi — shuni olamiz
        _asl = float(agreed)
    elif abs(total_amount - old_total) <= 0.01:
        # Jami o'zgarmadi — ASL kelishilgan summa O'ZGARMAYDI (chegirma, ustama,
        # kechirilgan qarz saqlanadi; ilgari chegirma jim yo'qolardi)
        _asl = _eski_asl
    elif old_discount_pct > 0:
        # Jami o'zgardi, chegirma foizi saqlanadi
        _asl = round(total_amount * (1 - old_discount_pct / 100))
    else:
        _asl = total_amount
    order.agreed_amount = _pul2(max(0.0, _asl - _qaytgan_kam))

    # Chegirma foizini qayta hisoblaymiz (ASL summadan)
    if total_amount > 0 and _asl < total_amount:
        order.discount_percent = round(
            (total_amount - _asl) / total_amount * 100, 2)
    else:
        order.discount_percent = 0.0

    db.flush()

    # kech58 (K58-3): qoplama retsepti tahrirda. O'LCHANGAN (asl kod, `work/probe58.py` S6):
    # retsept R1 -> R2 tahririda ombor tegilmasdi, o'chirishda esa loy R2 ga qaytardi.
    #  - Qoralama (hech narsa yechilmagan) — yangi tanlovga ergashadi.
    #  - Qoralama emas: umumiy loy qaysi retseptdan YECHILGAN bo'lsa — shu saqlanadi
    #    (yangi buyurtmada ustun allaqachon bor; eski NULL buyurtmada — faqat retsept
    #    o'zgaradigan bo'lsa, oldingisi yoziladi, aks holda avvalgi qoida AYNAN qoladi).
    #
    # kech63 (53-band) — FOYDALANUVCHI QARORI (kech62, tugma): "Oq loy omborga qaytsin, Kulrang
    # yechilsin" — jarayondagi buyurtmada qoplama retsepti o'zgartirilsa eski retsept loyi omborga
    # QAYTADI, yangisidan YECHILADI. O'LCHANGAN (asl kod `25bcd8d`, `work/probe53.py`): PUT R1 -> R2
    # 200 "Buyurtma yangilandi!" berardi, ombor tegilmasdi, `qoplama_retsept_id` R1 da qolardi, detallar
    # va tahrir oynasi esa R2 ni ko'rsatardi — foydalanuvchi almashtirdim deb o'ylardi (JIM).
    # Qoida (texnik — Claude):
    #  - ALMASHTIRISH = foydalanuvchi TANLOVI o'zgargan (`buyurtma_qoplama_retseptini_tanla` tahrirdan
    #    OLDIN va KEYIN farqli) VA yangi tanlov loy yechilgan retseptdan (`_qr58_oldin`) farqli.
    #    Tanlov o'zgarmagan tahrir (masalan eski NULL buyurtma, K58-1 shakli) — kech58 qoidasi AYNAN.
    #  - Loy rejasi > 0 va buyurtmadan biror qism CHIQQAN (topshirilgan / omborga ortiqcha) yoki
    #    "Tayyor" (haqiqiy loy yozilgan) — 400, HECH NARSA yozilmaydi (loyning bir qismi mahsulotda —
    #    qaytarib bo'lmaydi; aralash retsept foydani buzadi).
    #  - Aks holda eski retseptga BUTUN reja qaytadi (o'chirishdagi yo'l — `return_loy_ingredients`),
    #    yangisidan yechiladi (yaratishdagi yo'l — `deduct_loy_ingredients`, avval tayyor loy zaxirasi).
    #    Yangi retsept xomashyosi yetmasa — yaratishdagidek 409 "davom etasizmi?" (`confirm_shortage`).
    #  - Qulf (101) ostida, `commit=False` — tahrir bilan BITTA tranzaksiya (keyingi `commit` —
    #    `adjust_inventory_diff`). Loy miqdori ham o'zgarsa — `PUT` keyin `update_order_loy` farqni
    #    YANGI retseptda qo'llaydi (`resolve_recipe` -> `qoplama_retsept_id`).
    #  - Loy rejasi 0 — ombor tegilmaydi, faqat yangi tanlov yoziladi (keyingi loy shundan yechiladi).
    db.expire(order, ['items'])
    _qr53_log = []
    _qr53_matn = None
    if is_draft:
        _qr58_yangi = services.buyurtma_qoplama_retseptini_tanla(db, order)
        order.qoplama_retsept_id = _qr58_yangi.id if _qr58_yangi else None
    else:
        _qr53_keyin = services.buyurtma_qoplama_retseptini_tanla(db, order)
        _qr53_ozgardi = getattr(_qr53_tanlov_oldin, 'id', None) != getattr(_qr53_keyin, 'id', None)
        if (_qr53_ozgardi and _qr58_oldin is not None and _qr53_keyin is not None
                and _qr53_keyin.id != _qr58_oldin.id):
            _eski53 = _retsept_nomi53(_qr58_oldin)
            _yangi53 = _retsept_nomi53(_qr53_keyin)
            if _loy53 > 0.001:
                _sabab53 = None
                if order.actual_loy_kg is not None:
                    _sabab53 = "buyurtma «Tayyor» qilingan (haqiqiy loy yozilgan)"
                elif services.buyurtmadan_qisman_chiqqan(order):
                    _sabab53 = "buyurtmadan mahsulot allaqachon topshirilgan yoki omborga qaytarilgan"
                if _sabab53:
                    db.rollback()
                    return {
                        "success": False,
                        "message": "Qoplama retseptini o'zgartirib bo'lmaydi!",
                        "shortages": [
                            f"Loy ({_miqdor_matn(_loy53)} kg) «{_eski53}» retseptidan yechilgan va {_sabab53} — "
                            f"loyning bir qismi ishlatilgan, uni «{_yangi53}» ga almashtirib bo'lmaydi. "
                            f"Retseptni «{_eski53}» holicha qoldiring."
                        ]
                    }
                if not confirm_shortage:
                    _lchk53 = services.check_loy_ingredients_for_order(
                        db, _qr53_keyin.id, _loy53, company_id=order.company_id, commit=False)
                    if not _lchk53.get("enough", True):
                        db.rollback()
                        return {
                            "success": False,
                            "type": "stock_shortage_warning",
                            "message": "Omborda yetishmayotgan xomashyo bor. Shunday ham davom etasizmi?",
                            "shortages": list(_lchk53.get("shortages") or [])
                        }
                _nomer53 = order.order_number or order.id
                _qr53_log.append(
                    f"🔄 Qoplama retsepti almashtirildi: «{_eski53}» → «{_yangi53}» — {_miqdor_matn(_loy53)} kg loy: "
                    f"eskisi omborga qaytdi, yangisidan yechildi")
                _qr53_log.extend(services.return_loy_ingredients(
                    db, order, _loy53, recipe_id=_qr58_oldin.id, company_id=order.company_id,
                    reason_override=f"Buyurtma {_nomer53} — qoplama retsepti almashtirildi (eski retsept loyi qaytarildi)",
                    commit=False))
                _qr53_log.extend(services.deduct_loy_ingredients(
                    db, order, _loy53, recipe_id=_qr53_keyin.id, company_id=order.company_id,
                    reason_override=f"Buyurtma {_nomer53} (loy — yangi qoplama retsepti)",
                    commit=False))
            order.qoplama_retsept_id = _qr53_keyin.id
            _qr53_matn = f"qoplama retsepti «{_eski53}» → «{_yangi53}»"
        elif order.qoplama_retsept_id is None and _qr58_oldin is not None:
            _qr58_keyin = services.resolve_recipe(db, company_id=order.company_id, order=order)
            if _qr58_keyin is None or _qr58_keyin.id != _qr58_oldin.id:
                order.qoplama_retsept_id = _qr58_oldin.id
    db.flush()

    # 6) Omborni farq bo'yicha to'g'rilaymiz (qoralama emas bo'lsa)
    inventory_log = []
    if not is_draft:
        inventory_log = services.adjust_inventory_diff(db, old_snapshot, new_snapshot, order_id=order_id,
                                                       company_id=order.company_id)
        # kech63 (53-band): qoplama retsepti almashtirilgan bo'lsa — uning qatorlari jurnal boshida.
        inventory_log[:0] = _qr53_log
        # Tayyor mahsulot farqi
        # M4: farq faqat SHU buyurtmaning korxonasidagi mahsulotlarga qo'llanadi.
        inventory_log.extend(_adjust_finished_diff(db, old_snapshot, new_snapshot,
                                                   company_id=getattr(order, 'company_id', None)))

        # "Loy sotish" — farq bo'yicha to'g'irlaymiz (recipe_id bo'yicha
        # jamlab, eski va yangi holatni solishtiramiz). Bu — avval BUTUNLAY
        # yo'q edi, tahrirlashda hech narsa to'g'irlanmasdi.
        new_loysale_by_recipe = {}
        for oi in order.items:
            if (oi.category or '').lower() == 'loy_sotish' and oi.recipe_id:
                new_loysale_by_recipe[oi.recipe_id] = new_loysale_by_recipe.get(oi.recipe_id, 0) + float(oi.quantity or 0)
        all_recipe_ids = set(old_loysale_by_recipe.keys()) | set(new_loysale_by_recipe.keys())
        for rid in all_recipe_ids:
            diff = new_loysale_by_recipe.get(rid, 0) - old_loysale_by_recipe.get(rid, 0)
            if abs(diff) > 0.001:
                if diff > 0:
                    inventory_log.extend(services.deduct_loy_ingredients(db, order, diff, recipe_id=rid))
                else:
                    inventory_log.extend(services.return_loy_ingredients(db, order, abs(diff), recipe_id=rid))

        db.commit()

    # 7) To'lov holatini qayta hisoblaymiz
    db.refresh(order)
    _update_order_payment_status(db, order)

    # 8) Yetkazish holatini qayta hisoblaymiz
    #    (miqdor oshsa "Yetkazildi" dan qaytadi, kamaysa aksincha)
    if order.deliveries:
        if order.is_fully_delivered:
            if order.status not in (OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.DRAFT):
                order.status = OrderStatus.DELIVERED
        elif order.status == OrderStatus.DELIVERED:
            order.status = OrderStatus.IN_PROGRESS

    db.commit()
    db.refresh(order)

    # AUDIT: tahrirlashdan OLDINGI va KEYINGI qisqa holatni solishtirib
    # yozamiz — bugun aynan shunday tafsilot yo'qligi sabab, muammoni
    # topish uchun butun zaxira faylini qo'lda tahlil qilishga to'g'ri
    # kelgan edi (Termopanel belgisi yo'qolishi, va h.k.).
    try:
        _audit_after = f"Jami: {float(order.total_amount or 0):,.0f} so'm, {len(order.items)} ta detal".replace(',', ' ')
        if _qr53_matn:
            _audit_after += f"; {_qr53_matn}"
        log_activity(db, "updated", "order", order.id, order.order_number, performed_by,
                      old_value=_audit_before, new_value=_audit_after,
                      company_id=getattr(order, 'company_id', None))
    except Exception:
        pass

    return {
        "success": True,
        "message": "Buyurtma yangilandi!",
        "inventory_log": inventory_log,
        "delivery_percent": order.delivery_percent,
        "total_amount": float(order.total_amount or 0),
        "agreed_amount": float(order.agreed_amount or 0),
        "discount_percent": float(order.discount_percent or 0),
        "paid_amount": order.paid_amount,
        "debt_amount": order.debt_amount,
        "price_changed": {
            "old_total": old_total,
            "new_total": total_amount,
            "old_discount_pct": old_discount_pct,
            "new_discount_pct": float(order.discount_percent or 0),
            "auto_applied": (not agreed and old_discount_pct > 0 and abs(total_amount - old_total) > 0.01)
        }
    }


def update_order_loy(db: Session, order_id: int, new_loy: float) -> dict:
    """Loy rejasini o'zgartiradi — ombor farq bo'yicha to'g'rilanadi."""
    import services

    # 17d (2026-09-21): yangi reja OMBORGA TEGILISHIDAN oldin tekshiriladi
    # (`adjust_loy_diff` xomashyoni darhol o'zgartiradi va commit qiladi).
    # O'LCHANGAN: `inf` → qoldiq −∞ va buyurtma kartasi 500; manfiy reja →
    # omborga olinganidan KO'P qaytardi (5 kg olingan, −5 bilan 7.5 qaytdi).
    try:
        new_loy = _query_loy("loy_kg", new_loy, bosh_mumkin=False)
    except ValueError as e:
        return {"success": False, "message": str(e)}

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    old_loy = services._get_planned_loy(order)

    log = []
    if order.status != OrderStatus.DRAFT:
        log = services.adjust_loy_diff(db, order, old_loy, new_loy)

    services._set_planned_loy(order, new_loy)
    db.commit()

    return {
        "success": True,
        "old_loy": old_loy,
        "new_loy": new_loy,
        "inventory_log": log
    }


# ============================================================
# DELIVERY — Yetkazishlar
# ============================================================

from models import Delivery, DeliveryItem
from schemas import DeliveryCreate


def _mrp_deliver_stock(db: Session, order_item, qty: float,
                       company_id: int = None, sign: float = 1.0) -> list:
    """MRP orqali SHU DETALGA band qilingan tayyor mahsulotni yuk xati
    bo'yicha ombordan chiqaradi (sign=1) yoki qaytaradi (sign=-1).

    NIMA UCHUN KERAK (2026-09-20):
    Oddiy "tayyor mahsulotdan" detallarda ombor buyurtma YARATILGANDA
    olinadi (`_take_finished_for_order`). MRP esa mahsulotni buyurtmadan
    KEYIN ishlab chiqaradi — o'sha payt allaqachon o'tib ketgan bo'ladi.
    Natijada mahsulot mijozga ketgandan keyin ham omborda "band" holatda
    abadiy turib qolardi.

    Endi u YUK XATI yozilganda chiqadi — foydalanuvchi tanlagan tartib:
    ishlab chiqarilgach omborda ko'rinib turadi, topshirilganda chiqadi.

    Tan narx BARQAROR `unit_cost_stable` dan kamaytiriladi, shuning uchun
    chiqarish va qaytarish aynan teng bo'ladi.
    """
    if not order_item or qty <= 0:
        return []
    cid = company_id if company_id is not None else getattr(order_item, 'company_id', None)
    q = db.query(FinishedProduct).filter(
        FinishedProduct.reserved_for_order_item_id == order_item.id)
    if cid is not None:
        q = q.filter(FinishedProduct.company_id == cid)
    log = []
    qoldi = float(qty)
    for fp in q.with_for_update().all():
        if qoldi <= 1e-9:
            break
        unit_cost = _fp_stable_unit_cost(db, fp)
        if sign > 0:
            olinadi = min(qoldi, float(fp.quantity or 0))
            if olinadi <= 1e-9:
                continue
            fp.quantity = float(fp.quantity or 0) - olinadi
            fp.reserved_quantity = max(0.0, float(fp.reserved_quantity or 0) - olinadi)
            if unit_cost > 0:
                fp.cost_price = max(0.0, float(fp.cost_price or 0) - unit_cost * olinadi)
            log.append(f"🏭 {fp.name}: -{olinadi:g} {fp.unit} (yuk xati bo'yicha)")
            qoldi -= olinadi
            # MUHIM: `reserved_for_order_item_id` TOZALANMAYDI, garchi
            # `reserved_quantity` 0 ga tushsa ham. Bu — mahsulot qaysi
            # detal uchun qilinganini ko'rsatuvchi TARIXIY bog'lam.
            # Tozalansa, yuk xati keyin o'chirilganda mahsulotni topib
            # bo'lmay qolardi va qaytarish ishlamasdi (sinovda aynan
            # shunday chiqdi). Bandlik miqdori 0 — bu yetarli belgi.
        else:
            fp.quantity = float(fp.quantity or 0) + qoldi
            fp.reserved_quantity = float(fp.reserved_quantity or 0) + qoldi
            if unit_cost > 0:
                fp.cost_price = float(fp.cost_price or 0) + unit_cost * qoldi
            log.append(f"🏭 {fp.name}: +{qoldi:g} {fp.unit} (yuk xati bekor qilindi)")
            qoldi = 0.0
            break
    if log:
        db.flush()
    return log


# ============================================================
# YETKAZISH — TAKROR YUBORISH HIMOYASI VA QULF (kech27, 2026-09-22)
# ============================================================
# HAQIQIY PostgreSQL 16 da O'LCHANGAN (asl kod = 17g, `3319f4a`; har holat
# 12 urinishdan 12 tasida):
#   A) bir xil qisman yetkazish (+ to'lov 50 000) ketma-ket ikki marta
#      yuborildi → ikkalasi 200: 2 yetkazish, 2 to'lov (pul ikki marta).
#   B) xuddi shu so'rov ikki oqimda BIR VAQTDA → yana 2 yetkazish, 2 to'lov.
#   C) ikki foydalanuvchi bir vaqtda 20 + 20 (qoldiq 30, to'lovsiz) →
#      IKKALASI saqlandi: 40 topshirildi (buyurtma 30), ikkala yetkazish
#      raqami ham bir xil "/Y-1". Qoldiq tekshiruvi qulfsiz edi — ikkala
#      so'rov bir-birining yozuvini ko'rmasdan "sig'adi" deb o'tardi.
#   D) C bilan bir xil, to'lov bilan → yana 40: qulf (101, buyurtma) faqat
#      to'lov bo'lganda va qoldiq tekshiruvidan KEYIN olinardi.
# Yechim (ikki qatlam, qo'lda to'lov / buyurtma himoyasi bilan bir naqsh):
#   1) Qulf — HAR yetkazishda, har qanday tekshiruvdan OLDIN (to'lovdagi
#      bilan bir fazo: 101, buyurtma). Keyin sessiya holati bazadan qayta
#      o'qiladi — qoldiq, holat, qarz va yetkazish raqami navbatdagi so'rov
#      uchun oldingisi yozib bo'lgandan keyingi haqiqiy qiymat bo'ladi.
#   2) Imzo — qulf ichida: shu buyurtmada so'nggi `PUL_TAKROR_SONIYA`
#      soniya ichida AYNAN shunday yetkazish (bazaga yoziladigan hamma
#      narsa bir xil) bo'lsa, yangisi yozilmaydi, mavjudining o'zi
#      `duplicate: true` bilan qaytariladi (qo'lda to'lov va buyurtmadagi
#      kabi). Rad etish (400) EMAS — chunki birinchi so'rov haqiqatan
#      saqlangan; xato ko'rgan foydalanuvchi oynadan keyin qayta kiritib,
#      haqiqiy ikki marta yozib qo'yishi mumkin edi. Haqiqiy takroriy
#      yetkazish oynadan keyin (yoki biror maydoni boshqacha bo'lsa) —
#      odatdagidek yoziladi.

# Yozish va imzo AYNAN bir xil usulni ishlatishi uchun yagona jadval
_YETKAZISH_USULI = {
    "naqd": PaymentMethod.CASH,
    "plastik": PaymentMethod.CARD,
    "o'tkazma": PaymentMethod.TRANSFER,
}


def _yetkazish_usuli(qiymat) -> "PaymentMethod":
    return _YETKAZISH_USULI.get(qiymat or "naqd", PaymentMethod.CASH)


def _yetkazish_imzo_sorov(data, detal_idlari) -> tuple:
    """So'rovning imzosi — bazaga AYNAN nima yozilishi.

    Qatorlar pastdagi yozuv bilan bir xil saralanadi: miqdori musbat va
    shu buyurtmaning detali bo'lganlari (boshqalari yozilmaydi)."""
    qatorlar = tuple(sorted(
        (int(di.order_item_id), round(float(di.quantity), 6))
        for di in (data.items or [])
        if float(di.quantity or 0) > 0 and di.order_item_id in detal_idlari
    ))
    summa = getattr(data, 'payment_amount', None)
    tolov = None
    if summa and summa > 0:
        tolov = (_pul2(summa), _yetkazish_usuli(getattr(data, 'payment_method', None)))
    return (
        qatorlar,
        tolov,
        _pul2(getattr(data, 'transport_cost', 0) or 0),
        getattr(data, 'transport_payer', 'none') or 'none',
        getattr(data, 'transport_carrier', None) or None,
        getattr(data, 'received_by', None) or None,
        getattr(data, 'notes', None) or None,
    )


def _yetkazish_imzo_bazadan(db: Session, d, korxona_id) -> tuple:
    """Bazadagi yetkazishning imzosi (`_yetkazish_imzo_sorov` bilan bir shakl).

    TENANT: `Payment` da korxona ustuni yo'q — filtr OTA (buyurtma) orqali;
    `korxona_id` — chaqiruvchi allaqachon tekshirgan buyurtmaning korxonasi
    (ortiqcha, lekin ataylab aniq: so'rov o'zi ham korxona bilan cheklangan)."""
    qatorlar = tuple(sorted(
        (int(x.order_item_id), round(float(x.quantity), 6)) for x in d.items
    ))
    tolovlar = db.query(Payment).join(Order, Order.id == Payment.order_id).filter(
        Payment.delivery_id == d.id, Order.company_id == korxona_id).all()
    tolov = None
    if len(tolovlar) == 1:
        tolov = (_pul2(tolovlar[0].amount or 0), tolovlar[0].payment_method)
    elif tolovlar:
        tolov = ("bir nechta", len(tolovlar))      # so'rov bilan hech qachon teng emas
    return (
        qatorlar,
        tolov,
        _pul2(d.transport_cost or 0),
        d.transport_payer or 'none',
        d.transport_carrier or None,
        d.received_by or None,
        d.notes or None,
    )


def create_delivery(db: Session, data: DeliveryCreate, delivered_by: str = None,
                    company_id: int = None) -> dict:
    """Yangi yetkazish qo'shadi.
    Ombor tegilmaydi — bu faqat mijozga topshirish hisobi."""
    # 17g (2026-09-22): ILDIZ — tana QAT'IY, bazaga tegishdan OLDIN (xato →
    # `ValueError`, hech narsa yozilmaydi). HAQIQIY PostgreSQL da O'LCHANGAN
    # (asl kod = 17f): to'lov / transport `Infinity` / `1e20` — 500; to'lov
    # `0.001` → 0.00 so'mlik to'lov yozuvi; noma'lum to'lovchi saqlanib
    # transport Moliyadan tushib qolardi; noma'lum usul jimgina "naqd";
    # uzun matnlar — 500. Marshrut ham tekshiradi; bu qatlam ichki
    # chaqiruvchilar (`services` — "Tayyor" belgisidagi avtomatik yetkazish)
    # uchun ham amal qiladi.
    _clean_val("Delivery", _val_dump(data, "Delivery"))
    # M2: yetkazish FAQAT o'z korxonasining buyurtmasiga.
    _oq = db.query(Order).filter(Order.id == data.order_id)
    if company_id is not None:
        _oq = _oq.filter(Order.company_id == company_id)
    order = _oq.first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    # kech27: QULF — har qanday tekshiruvdan OLDIN, to'lov bo'lmasa ham
    # (yuqoridagi "YETKAZISH — TAKROR YUBORISH HIMOYASI VA QULF" izohi, C/D).
    # Korxona tekshiruvidan KEYIN — begona buyurtma raqami bilan qulf olinmaydi.
    # `flush` — chaqiruvchining (masalan `services` "Tayyor" oqimi) hali
    # yozilmagan o'zgarishlari `expire_all` da yo'qolmasin (sessiya
    # `autoflush=False`). `expire_all` — qulfdan OLDIN o'qilgan buyurtma /
    # detal / yetkazishlar holati eskirgan bo'lishi mumkin; endi hammasi
    # qulf ostida bazadan qayta o'qiladi (oldingi so'rov yozib bo'lgach).
    db.flush()
    _pul_qulfi(db, 101, order.id)
    db.expire_all()

    # MUHIM (2026-09 audit): o'chirilgan (is_deleted) buyurtmaga yetkazish
    # qo'shishga YO'L QO'YILMAYDI. Bunga yo'l qo'yilsa, buyurtma o'chirilgan
    # paytda hisoblangan delivery_percent (Loy proporsional qaytarish
    # va keyinchalik tiklashda qayta yechish shu foizga tayanadi) o'chirish
    # va tiklash orasida o'zgarib qolib, ombor hisobini buzib qo'yishi mumkin
    # edi (masalan eski ochiq varaq yoki to'g'ridan-to'g'ri API chaqiruvi orqali).
    if order.is_deleted:
        return {"success": False, "message": "Bu buyurtma o'chirilgan — avval uni tiklang"}

    if order.status == OrderStatus.DRAFT:
        return {"success": False, "message": "Qoralama buyurtmani yetkazib bo'lmaydi"}

    if not data.items:
        return {"success": False, "message": "Kamida bitta detal kiriting"}

    # kech38 (5-bo'lim 6-band): shu buyurtmaga TEGISHLI BO'LMAGAN yoki umuman
    # mavjud bo'lmagan detal qatori — butun so'rov RAD etiladi. Ilgari bunday
    # qator pastdagi siklda jimgina tashlab yuborilar, qolganlari 200 bilan
    # saqlanardi — O'LCHANGAN (SQLite va HAQIQIY PostgreSQL 16, asl kod
    # `c7a11f3`): [o'z detali 2, boshqa buyurtma detali 3] → 200, faqat o'z
    # detali yozildi; [yo'q id, o'z detali] → 200. Haqiqiy holat: yetkazish
    # oynasi ochiq turganda boshqa xodim detalni o'chirsa, foydalanuvchi
    # "saqlandi" ko'rardi, lekin bir qator izsiz yo'qolardi. Tekshiruv IMZO
    # va qoldiq tekshiruvidan OLDIN: noto'g'ri so'rov "takroriy" deb ham
    # qabul qilinmaydi (imzo bunday qatorlarni e'tiborsiz qoldiradi).
    # `order.items` — `expire_all` dan keyin, qulf ostida bazadan o'qiladi.
    _detal_idlari = {oi.id for oi in order.items}
    for _qator_n, _dq in enumerate(data.items, 1):
        if _dq.order_item_id not in _detal_idlari:
            return {"success": False,
                    "message": (f"'items' {_qator_n}-qator: bu detal shu buyurtmada topilmadi "
                                f"(o'chirilgan bo'lishi mumkin) — sahifani yangilab, qayta kiriting")}

    # kech27: TAKROR YUBORISH — qoldiq tekshiruvidan ham, to'lov chegarasidan
    # ham OLDIN turishi SHART: birinchi so'rov yozilgach qoldiq va qarz
    # kamayadi, takroriy so'rov ularga yetib kelsa foydalanuvchiga
    # "Qoldiqdan ko'p berib bo'lmaydi!" yoki "ortiqcha to'lov" degan
    # chalg'ituvchi xabar chiqardi — holbuki yetkazish haqiqatan saqlangan.
    from datetime import timedelta as _td_dlv
    _imzo = _yetkazish_imzo_sorov(data, _detal_idlari)
    if _imzo[0]:
        # TENANT: `Delivery` da korxona ustuni yo'q — filtr OTA (buyurtma)
        # orqali; buyurtma yuqorida korxona bilan tekshirilgan, bu yerda ham
        # aniq cheklanadi.
        _yaqinda = db.query(Delivery).join(Order, Order.id == Delivery.order_id).filter(
            Delivery.order_id == order.id,
            Order.company_id == order.company_id,
            Delivery.delivered_at >= datetime.utcnow() - _td_dlv(seconds=PUL_TAKROR_SONIYA),
        ).order_by(Delivery.delivered_at.desc(), Delivery.id.desc()).all()
        for _eski in _yaqinda:
            if _yetkazish_imzo_bazadan(db, _eski, order.company_id) == _imzo:
                return {
                    "success": True,
                    "duplicate": True,
                    "message": (f"{_eski.delivery_number} hozirgina saqlangan edi — "
                                f"takroriy so'rov, qayta yozilmadi"),
                    "delivery_id": _eski.id,
                    "delivery_number": _eski.delivery_number,
                    "delivery_percent": order.delivery_percent,
                    "is_fully_delivered": order.is_fully_delivered,
                    "order_status": order.status.value,
                }

    # Tekshirish: qoldiqdan ko'p berilmasin
    errors = []
    valid_items = []
    for di in data.items:
        if di.quantity <= 0:
            continue
        oi = db.query(OrderItem).filter(
            OrderItem.id == di.order_item_id,
            OrderItem.order_id == order.id
        ).first()
        if not oi:
            continue
        remaining = oi.remaining_qty
        if di.quantity > remaining + 0.001:
            errors.append(
                f"{oi.name}: {di.quantity:g} {oi.delivery_unit} berilmoqchi, "
                f"lekin qoldi {remaining:g} {oi.delivery_unit}"
            )
            continue
        valid_items.append((oi, di.quantity))

    if errors:
        return {"success": False, "message": "Qoldiqdan ko'p berib bo'lmaydi!", "shortages": errors}

    if not valid_items:
        return {"success": False, "message": "Yetkazish uchun miqdor kiritilmagan"}

    # 17g (2026-09-22): shu yukka bog'liq to'lov — qo'lda to'lov
    # (`create_payment`) bilan AYNAN bir xil chegaralar ("3 baravar" qoidasi →
    # `ValueError`, qarzdan ko'p → `OverpaymentWarning`, marshrut → 409 va UI
    # tasdig'i), va bu tekshiruv yetkazish YOZILISHIDAN OLDIN: rad etilsa hech
    # narsa saqlanmaydi. Qulf (101, buyurtma — qo'lda to'lov bilan bir fazo)
    # kech27 dan beri funksiya BOSHIDA olinadi (har yetkazishda), ya'ni bir
    # vaqtda kelgan qo'lda to'lov yoki boshqa yetkazish qarzni eskirtirmaydi.
    payment_amount = getattr(data, 'payment_amount', None)
    if payment_amount and payment_amount > 0:
        _tolov_chegarasi(order, payment_amount,
                         bool(getattr(data, 'confirm_overpay', False)))

    # Yetkazish raqami: ORD-010-1/Y-2
    seq = db.query(Delivery).filter(Delivery.order_id == order.id).count() + 1
    delivery_number = f"{order.order_number}/Y-{seq}"

    db_delivery = Delivery(
        order_id=order.id,
        delivery_number=delivery_number,
        delivered_by=delivered_by,
        received_by=data.received_by,
        notes=data.notes,
        transport_carrier=getattr(data, 'transport_carrier', None),
        transport_cost=getattr(data, 'transport_cost', 0) or 0,
        transport_payer=getattr(data, 'transport_payer', 'none') or 'none'
    )
    db.add(db_delivery)
    db.flush()

    mrp_log = []
    for oi, qty in valid_items:
        db.add(DeliveryItem(
            delivery_id=db_delivery.id,
            order_item_id=oi.id,
            quantity=qty,
            unit=oi.delivery_unit
        ))
        # 2026-09-20: MRP orqali shu detalga band qilingan tayyor mahsulot
        # aynan SHU YERDA ombordan chiqadi (yuqoridagi izohga qarang).
        mrp_log.extend(_mrp_deliver_stock(db, oi, qty, company_id=company_id))

    db.flush()
    db.refresh(order)

    # Hammasi berilgan bo'lsa — status
    fully = order.is_fully_delivered
    if fully and order.status not in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        order.status = OrderStatus.DELIVERED
        if not order.completed_at:
            order.completed_at = datetime.utcnow()
        # 2026-09-13: to'liq topshirilgan buyurtma "Pin qilingan" ro'yxatidan
        # o'zi chiqib ketadi — yakunlangan ish uchun "muhim" belgisi kerak
        # emas, ro'yxat vaqt o'tishi bilan eski ishlar bilan to'lib ketmasin.
        order.is_pinned = False

    # Shu yukka bog'liq to'lov (ixtiyoriy) — chegaralari yuqorida, yetkazish
    # yozilishidan OLDIN tekshirilgan (`_tolov_chegarasi`).
    # 17g (2026-09-22): to'lov yetkazish bilan BITTA tranzaksiyada (atomar)
    # yoziladi. Ilgari bu yer `try/except` ichida edi — niyat "to'lov yozilmasa
    # ham yetkazish saqlansin, foydalanuvchiga ogohlantirish" edi, lekin
    # HAQIQIY PostgreSQL da O'LCHANGAN: `flush` xatosidan keyin sessiya
    # tranzaksiyasi bekor bo'ladi va pastdagi `commit` `PendingRollbackError`
    # beradi — ya'ni javob baribir 500, hech narsa saqlanmasdi (ogohlantirish
    # hech qachon yetib bormasdi). Endi summa, usul va sig'im oldindan qat'iy
    # tekshirilgani uchun bu yozuv xato bermaydi; kutilmagan baza xatosi
    # bo'lsa — butun so'rov bekor bo'ladi (yetkazish to'lovsiz, yarim holda
    # qolmaydi), foydalanuvchi qayta yuboradi.
    if payment_amount and payment_amount > 0:
        # kech27: imzo tekshiruvi bilan AYNAN bir xil jadval (`_YETKAZISH_USULI`)
        pay_method = _yetkazish_usuli(getattr(data, 'payment_method', None))
        db.add(Payment(
            order_id=order.id,
            delivery_id=db_delivery.id,
            amount=payment_amount,
            payment_type=PaymentType.PARTIAL,
            payment_method=pay_method,
            received_by=data.received_by,
            notes=f"{delivery_number} yuki uchun to'lov"
        ))
        # MUHIM TUZATISH: avval bu yerda to'lov yozilgandan keyin
        # buyurtmaning "To'lov holati" (payment_status) UMUMAN qayta
        # hisoblanmasdi — chunki bu yerga to'g'ridan-to'g'ri Payment
        # yozilardi, standart create_payment() (u har doim shu
        # yangilashni chaqiradi) chetlab o'tilardi. Natijada, "Yuk
        # xati" orqali to'liq to'lov qilingan buyurtmalar ham hamon
        # "To'lanmagan" bo'lib ko'rinib qolardi (2026-08-21 zaxira
        # tekshiruvida ORD-027-2/ORD-027-3'da aynan shu holat topildi).
        db.flush()
        db.refresh(order)
        _update_order_payment_status(db, order)
        # 17c (2026-09-21): yuk xati to'lovi loyiha "To'langan"
        # summasini YANGILAMASDI — jonli PRJ-033 da aynan shu topildi
        # (buyurtma to'liq to'langan, loyiha "To'langan: 0").
        _loyiha_tolangan_yangila(db, order.project)

    db.commit()
    db.refresh(db_delivery)
    db.refresh(order)

    result = {
        "success": True,
        "message": "Yetkazish saqlandi!",
        "delivery_id": db_delivery.id,
        "delivery_number": delivery_number,
        "delivery_percent": order.delivery_percent,
        "is_fully_delivered": fully,
        "order_status": order.status.value
    }
    if mrp_log:
        result["inventory_log"] = mrp_log   # 2026-09-20: MRP mahsuloti chiqdi
    return result


def get_deadline_urgency(deadline, status_value: str, is_fully_delivered: bool = False) -> str:
    """Topshirish muddatiga qarab holatni qaytaradi: 'overdue' (muddat
    o'tgan), 'today' (bugun), 'tomorrow' (ertaga), yoki 'normal'.
    Allaqachon YETKAZILGAN/BEKOR QILINGAN (yoki TO'LIQ TOPSHIRILGAN —
    holati hali 'ready'da qolgan bo'lsa ham) buyurtmalar uchun muddat
    endi ahamiyatsiz — doim 'normal' qaytariladi (2026-09-13; dastlab
    faqat status tekshirilgan edi, lekin to'liq topshirilgan-u holati
    hamon 'ready' bo'lib qolgan buyurtmalarda ogohlantirish noto'g'ri
    yonib qolayotgani aniqlandi — shuning uchun to'liq topshirilganlik
    ham alohida tekshiriladi).

    MUHIM: server UTC bo'yicha ishlaydi, lekin "bugun" — Toshkent kuni
    (UTC+5) bo'lishi kerak, aks holda ertalabki soat 00:00-04:59
    Toshkent vaqtida (bu hali UTC bo'yicha KECHAGI kun) hisoblash bir
    kunga siljib ketadi (2026-09-13'da aynan shu holat topilgan edi)."""
    if not deadline or status_value in ("delivered", "cancelled") or is_fully_delivered:
        return "normal"
    from datetime import timedelta
    today_tashkent = (datetime.utcnow() + timedelta(hours=5)).date()
    days_left = (deadline.date() - today_tashkent).days
    if days_left < 0:
        return "overdue"
    if days_left == 0:
        return "today"
    if days_left == 1:
        return "tomorrow"
    return "normal"


def toggle_order_pin(db: Session, order_id: int) -> dict:
    """Buyurtmani 'Pin qilingan' ro'yxatiga qo'shadi/olib tashlaydi
    (2026-09-13, muhim buyurtmalarni tepada ko'rsatish uchun)."""
    order = db.query(Order).filter(Order.id == order_id, Order.is_deleted.isnot(True)).first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}
    order.is_pinned = not bool(order.is_pinned)
    db.commit()
    return {"success": True, "is_pinned": order.is_pinned}


def get_pinned_orders(db: Session, company_id: int = None) -> list:
    """Pin qilingan buyurtmalarni, TOPSHIRISH MUDDATI eng yaqinidan
    boshlab (muddat kiritilmaganlar oxirida) qaytaradi."""
    _pq = db.query(Order)
    if company_id is not None:
        _pq = _pq.filter(Order.company_id == company_id)
    rows = _pq.filter(
        Order.is_pinned == True, Order.is_deleted.isnot(True)
    ).all()
    rows.sort(key=lambda o: (o.deadline is None, o.deadline))
    result = []
    for o in rows:
        result.append({
            "id": o.id, "order_number": o.order_number,
            "client_name": o.project.client_name if o.project else "—",
            "project_name": o.project.project_name if o.project else "—",
            "status": o.status.value,
            "total_amount": float(o.total_amount or 0),
            "agreed_amount": float(o.agreed_amount) if o.agreed_amount is not None else None,
            "master_name": o.master.name if o.master else "—",
            "created_at": o.created_at.strftime("%d.%m.%Y") if o.created_at else "—",
            "deadline": o.deadline.strftime("%d.%m.%Y") if o.deadline else None,
            "deadline_urgency": get_deadline_urgency(o.deadline, o.status.value, o.is_fully_delivered),
            "project_id": o.project_id,
        })
    return result


def get_delivery(db: Session, delivery_id: int, company_id: int = None) -> Optional[Delivery]:
    _dq = db.query(Delivery).filter(Delivery.id == delivery_id)
    if company_id is not None:
        _dq = _dq.join(Order, Order.id == Delivery.order_id).filter(
            Order.company_id == company_id)
    return _dq.first()


class YukToloviBor(Exception):
    """kech38 (5-bo'lim 12-band): o'chirilayotgan yuk xatiga to'lov bog'langan,
    foydalanuvchi esa to'lov bilan nima qilishni hali aytmagan (`tolov`).
    Marshrut → 409 (`detail.type = "delivery_has_payment"`), `orders.html`
    `deleteDelivery` uch tugmali oyna ko'rsatadi."""

    def __init__(self, raqam, tolovlar):
        self.raqam = raqam
        self.tolovlar = list(tolovlar)              # [(payment_id, summa)]
        self.jami = round(sum(s for _, s in self.tolovlar), 2)
        jm = f"{self.jami:,.0f}"
        nechta = (f"{jm} so'm to'lov" if len(self.tolovlar) == 1
                  else f"{len(self.tolovlar)} ta to'lov (jami {jm} so'm)")
        super().__init__(
            f"Bu yuk xatiga ({raqam}) {nechta} bog'langan.\n\n"
            f"To'lov ham o'chirilsinmi yoki saqlab qolinsinmi?\n\n"
            f"• \"To'lovni ham o'chirish\" — mijoz bu pulni bermagan bo'lsa "
            f"(qarz {jm} so'mga ko'payadi).\n"
            f"• \"To'lovni saqlab qolish\" — pul haqiqatan olingan bo'lsa "
            f"(to'lov buyurtmada oddiy to'lov bo'lib qoladi, qarz o'zgarmaydi).")


YUK_TOLOV_AMALLARI = ("ochir", "qoldir")


def delete_delivery(db: Session, delivery_id: int, company_id: int = None,
                    tolov: str = None, performed_by: str = None):
    """Yetkazishni (yuk xatini) o'chirish.

    Qaytaradi: muvaffaqiyatda `{"tolov_ochirildi": N, "tolov_saqlandi": M}`
    (doim rost qiymat), topilmasa `False`.

    kech38 (5-bo'lim 12-band) — O'LCHANGAN (asl kod `c7a11f3`):
      * HAQIQIY PostgreSQL da (jonli sinov saytida ham) to'lov bog'langan
        yukni o'chirish → 500 (`payments_delivery_id_fkey`, 23503), hech narsa
        o'zgarmasdi; `orders.html` `deleteDelivery` esa `!res.ok` da HECH
        QANDAY xabar ko'rsatmasdi — tugma "ishlamaydigandek" edi.
      * SQLite da (tashqi kalit tekshirilmaydi) yuk o'char, to'lov esa
        mavjud bo'lmagan yukka ishora qilib qolardi; SQLite id ni qayta
        ishlatgani uchun u keyingi (boshqa buyurtmaning) yukiga \"bog'lanib\"
        qolardi.
    FOYDALANUVCHI QARORI (kech38): \"Har safar so'rasin\" — pul haqiqatan
    olinganini faqat xodim biladi. Shuning uchun:
      * `tolov=None` va yukka to'lov bog'langan → `YukToloviBor` (hech narsa
        o'zgarmaydi; marshrut → 409, UI so'raydi);
      * `tolov="ochir"` → to'lov(lar) ham o'chiriladi (audit izi bilan —
        `delete_payment` dagi AYNAN matn), qarz ko'payadi;
      * `tolov="qoldir"` → to'lov buyurtmada oddiy to'lov bo'lib qoladi
        (`delivery_id = NULL`, izohga belgi, audit izi), qarz o'zgarmaydi;
      * boshqa qiymat → `ValueError` (400). To'lovsiz yukda `tolov` e'tiborsiz.
    Hammasi BITTA tranzaksiyada: `log_activity` o'zi `commit` qiladi (qulfni
    bo'shatib, yarim holatni saqlab qo'yardi) — shuning uchun audit yozuvi
    shu yerda to'g'ridan qo'shiladi.

    QULF (5-bo'lim 14-bandning shu funksiyaga tegishli qismi): (101,
    buyurtma) — `create_delivery` va `create_payment` bilan bir fazo. Qulfsiz
    parallel \"yukni o'chirish\" + \"yangi yuk\" buyurtmani yarim topshirilgan
    holda \"Yetkazildi\" deb qoldirishi mumkin edi (yangi yuk eski yukni
    ko'radi, o'chirish esa yangi yukni ko'rmaydi)."""
    if tolov is not None and tolov not in YUK_TOLOV_AMALLARI:
        raise ValueError("'tolov' noto'g'ri qiymat — faqat 'ochir' yoki 'qoldir'")
    _dq = db.query(Delivery).filter(Delivery.id == delivery_id)
    if company_id is not None:
        _dq = _dq.join(Order, Order.id == Delivery.order_id).filter(
            Order.company_id == company_id)
    d = _dq.first()
    if not d:
        return False
    order = d.order
    # QULF — `create_delivery` naqshi: yozilmagan o'zgarish yo'qolmasin
    # (`flush`), qulf, so'ng qulf ostida HAMMASI bazadan qayta o'qiladi.
    db.flush()
    _pul_qulfi(db, 101, order.id)
    db.expire_all()
    d = db.query(Delivery).join(Order, Order.id == Delivery.order_id).filter(
        Delivery.id == delivery_id, Order.company_id == order.company_id).first()
    if not d:
        return False            # parallel so'rov allaqachon o'chirgan
    order = d.order

    # TENANT: `Payment` da korxona ustuni yo'q — OTA (buyurtma) orqali.
    tolovlar = db.query(Payment).join(Order, Order.id == Payment.order_id).filter(
        Payment.delivery_id == d.id,
        Payment.order_id == order.id,
        Order.company_id == order.company_id,
    ).order_by(Payment.id).all()
    if tolovlar and tolov is None:
        raise YukToloviBor(d.delivery_number,
                           [(p.id, float(p.amount or 0)) for p in tolovlar])

    from models import ActivityLog
    _ochirildi = _saqlandi = 0
    for p in tolovlar:
        if tolov == "ochir":
            db.add(ActivityLog(
                company_id=order.company_id, action="deleted", entity_type="payment",
                entity_id=p.id, entity_label=f"Buyurtma {order.order_number}",
                performed_by=performed_by,
                new_value=_tolov_audit_matni(p) + f" · yuk xati {d.delivery_number} bilan birga"))
            db.delete(p)
            _ochirildi += 1
        else:
            p.delivery_id = None
            p.notes = ((p.notes or "") + f" · yuk xati {d.delivery_number} o'chirilgan, "
                       f"to'lov saqlab qolingan").strip(" ·")
            db.add(ActivityLog(
                company_id=order.company_id, action="updated", entity_type="payment",
                entity_id=p.id, entity_label=f"Buyurtma {order.order_number}",
                performed_by=performed_by, old_value=f"yuk xati {d.delivery_number}",
                new_value="yuk xati o'chirildi — to'lov saqlab qolindi (oddiy to'lov)"))
            _saqlandi += 1
    if tolovlar:
        db.flush()              # tashqi kalit: to'lov yozuvlari yukdan OLDIN

    # 2026-09-20: yuk xati bo'yicha ombordan chiqqan MRP mahsuloti
    # QAYTADI — chiqarish bilan AYNAN simmetrik (barqaror 1 birlik tan
    # narxi ishlatilgani uchun summa ham aynan tiklanadi).
    _cid = order.company_id
    for di in list(d.items or []):
        _oi = db.query(OrderItem).filter(OrderItem.id == di.order_item_id).first()
        if _oi:
            _mrp_deliver_stock(db, _oi, float(di.quantity or 0),
                               company_id=_cid, sign=-1.0)
    db.delete(d)
    db.flush()

    # Status qayta hisoblanadi
    db.refresh(order)
    if not order.is_fully_delivered and order.status == OrderStatus.DELIVERED:
        order.status = OrderStatus.READY
    if tolovlar:
        # to'lov holati va loyiha "To'langan" summasi (`delete_payment` bilan bir xil)
        _update_order_payment_status(db, order)
        _loyiha_tolangan_yangila(db, order.project)

    db.commit()
    return {"tolov_ochirildi": _ochirildi, "tolov_saqlandi": _saqlandi}


def get_delivery_status(db: Session, order_id: int) -> dict:
    """Buyurtmaning yetkazish holati — har detal bo'yicha."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"error": "Buyurtma topilmadi"}

    items = []
    for it in order.items:
        ordered = it.order_qty_normalized
        delivered = it.delivered_qty
        items.append({
            "id": it.id,
            "name": it.name,
            "category": it.category,
            "unit": it.delivery_unit,
            "ordered": round(ordered, 2),
            "delivered": round(delivered, 2),
            # kech60 (57-band): omborga ortiqcha qo'yilgan qism ham chiqqan (`remaining_qty`)
            "remaining": round(it.remaining_qty, 2),
            "ortiqcha": round(it.ortiqcha_qty, 2),
            "percent": round(delivered / ordered * 100, 1) if ordered > 0 else 0,
            "is_done": it.remaining_qty <= 0.001
        })

    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "client_name": order.project.client_name if order.project else None,
        "delivery_percent": order.delivery_percent,
        "is_fully_delivered": order.is_fully_delivered,
        "status": order.status.value,
        "items": items,
        "deliveries": [_delivery_dict(d) for d in
                       sorted(order.deliveries, key=lambda x: x.delivered_at or datetime.min, reverse=True)]
    }


def _delivery_dict(d) -> dict:
    """Yetkazishni dict ga aylantiradi — summasi bilan."""
    items = []
    dsum = 0.0
    for di in d.items:
        oi = di.order_item
        if not oi:
            continue
        ordered = oi.order_qty_normalized
        total_price = float(oi.total_price or 0)
        unit_p = (total_price / ordered) if ordered > 0 else 0.0
        line_sum = unit_p * float(di.quantity or 0)
        dsum += line_sum
        items.append({
            "order_item_id": di.order_item_id,
            "item_name": oi.name,
            "quantity": float(di.quantity),
            "unit": di.unit,
            "unit_price": round(unit_p),
            "sum": round(line_sum)
        })

    return {
        "id": d.id,
        "delivery_number": d.delivery_number,
        "short_number": (d.delivery_number or "").split('/')[-1],
        "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
        "delivered_by": d.delivered_by,
        "received_by": d.received_by,
        "notes": d.notes,
        "transport_carrier": d.transport_carrier,
        "transport_cost": float(d.transport_cost or 0),
        "transport_payer": d.transport_payer or "none",
        "company_transport_cost": d.company_transport_cost,
        "total_sum": round(dsum),
        "items": items
    }


# ============================================================
# FINISHED PRODUCT — Tayyor mahsulotlar ombori
# ============================================================

from models import FinishedProduct, StockSource
from schemas import ProduceCreate


def _fp_unit(category: str) -> str:
    """Profil, panel va blok — metr, termopanel — kvadrat, qolgani — dona."""
    cat = (category or '').lower()
    if cat in ('profil', 'panel', 'blok'):
        return 'metr'
    if cat == 'termopanel':
        return 'kvadrat'
    return 'dona'


def _fp_qty(data) -> float:
    """Ishlab chiqarilayotgan miqdor."""
    cat = (data.category or '').lower()
    if cat == 'profil':
        return float(data.length or 0)
    return float(data.quantity or 0)
def release_finished_product_reservation(db: Session, fp_id: int, performed_by: str = None,
                                         company_id: int = None) -> dict:
    """2026-09-17: Production/MRP orqali biror aniq buyurtma-detaliga
    band qilingan tayyor mahsulotni ozod qiladi — mahsulotning o'zi
    OMBORDA QOLADI, faqat endi UMUMIY SOTUVGA ochiladi (boshqa har
    qanday mijozga sotilishi mumkin bo'ladi). Buyurtma bekor qilingan,
    mijoz pulini to'lamagan yoki uzoq vaqt olib ketmagan holatlar
    uchun — aks holda mahsulot abadiy "band" bo'lib qolib, sex uni
    qayta ishlab chiqarishga majbur bo'lardi."""
    fp = get_finished_product(db, fp_id, company_id)   # M4: faqat shu korxonadan
    if not fp:
        return {"success": False, "message": "Tayyor mahsulot topilmadi"}
    if not fp.reserved_for_order_item_id and not fp.reserved_quantity:
        return {"success": False, "message": "Bu mahsulot hech kimga band qilinmagan"}
    old_reserved = fp.reserved_quantity
    old_order_item_id = fp.reserved_for_order_item_id
    fp.reserved_quantity = 0.0
    fp.reserved_for_order_item_id = None
    log_activity(db, "release_reservation", "finished_product", fp.id,
                 entity_label=fp.name, performed_by=performed_by,
                 company_id=getattr(fp, 'company_id', None),
                 old_value=f"band: {old_reserved} (detal #{old_order_item_id})", new_value="band emas — umumiy sotuvda")
    db.commit()
    return {"success": True, "message": f"{fp.name} endi umumiy sotuv uchun ochiq"}


def record_finished_product_loss(db: Session, data, created_by: str = None,
                                company_id: int = None) -> dict:
    """Tayyor mahsulotdan brak/yo'qotish sababli miqdorni KAMAYTIRADI
    (butunlay o'chirmaydi). Tan narx — o'sha mahsulotning 1 birlik tan
    narxiga proporsional hisoblanadi, va Moliyada Brak xarajatiga qo'shiladi."""
    from models import FinishedProduct, FinishedProductLoss

    # 17-band: tana qiymatlari QAT'IY — hech narsa yozilmasdan OLDIN.
    try:
        _clean_val("Loss", _val_dump(data, "Loss"))
    except ValueError as _e:
        return {"success": False, "message": str(_e)}

    # M4: mahsulot FAQAT joriy korxonadan (aks holda "topilmadi").
    fp = get_finished_product(db, data.finished_product_id, company_id, lock=True)
    if not fp:
        return {"success": False, "message": "Mahsulot topilmadi"}
    if not _fp_tayyormi(fp):
        return {"success": False, "message": _FP_JARAYONDA_XABAR}

    available = float(fp.quantity or 0)
    if data.quantity > available + 0.001:
        return {"success": False, "message": f"Omborda faqat {available:g} {fp.unit} bor, {data.quantity:g} kamaytira olmaysiz"}
    # kech56 (13-band, 7-qadam): javobgar hodim — shu korxonaning hodimi (yozuvdan OLDIN)
    try:
        _brak_javobgar_tekshir(db, getattr(data, 'brak_javobgar_id', None),
                               getattr(fp, 'company_id', None))
    except ValueError as _e:
        return {"success": False, "message": str(_e)}

    unit_cost = (float(fp.cost_price or 0) / available) if available > 0 else 0
    cost_amount = unit_cost * data.quantity

    fp.quantity = available - data.quantity
    if fp.cost_price:
        fp.cost_price = max(0, float(fp.cost_price) - cost_amount)

    loss = FinishedProductLoss(
        company_id=getattr(fp, 'company_id', None),      # M8/F1
        finished_product_id=fp.id,
        product_name=fp.name,
        category=fp.category,
        quantity=data.quantity,
        unit=fp.unit,
        cost_amount=cost_amount,
        # kech57 (K57-1): izoh belgi bilan boshlansa — "Izoh: " (yuqoridagi yordamchi)
        reason=_ish_brak_belgisidan_ajrat(data.reason),
        created_by=created_by,
        # kech53 (13-band, 1-qadam): ixtiyoriy brak bosqichi
        brak_bosqich=getattr(data, 'brak_bosqich', None),
        # kech56 (13-band, 7-qadam): ixtiyoriy sabab va javobgar hodim
        brak_sabab=getattr(data, 'brak_sabab', None),
        brak_javobgar_id=getattr(data, 'brak_javobgar_id', None)
    )
    db.add(loss)
    db.commit()
    db.refresh(loss)
    return {
        "success": True,
        "loss_id": loss.id,
        "cost_amount": float(cost_amount),
        "remaining_stock": float(fp.quantity)
    }


# 18-band (2026-09-21): "ishlab chiqarish braki" yozuvlarining sabab matni
# SHU belgi bilan boshlanadi. Moliya (`services.get_monthly_report`,
# `services.calculate_split_profit_report`) va `get_return_stats` ham aynan shu
# boshlanish bo'yicha ajratadi — belgi o'zgarsa hammasi birga o'zgarishi
# SHART (`tools/test_brak_bekor.py` G bo'limi buni qulflaydi).
_ISH_BRAK_BELGI = "Ishlab chiqarish jarayonida brak"


def _ish_brakimi(loss) -> bool:
    """Yozuv "ishlab chiqarish braki" (mahsulot soniga tegmagan, xomashyo
    sarflangan) mi — `record_finished_product_production_brak` yozgan."""
    return (getattr(loss, "reason", None) or "").startswith(_ISH_BRAK_BELGI)


def _ish_brak_belgisidan_ajrat(reason):
    """kech57 (K57-1, 40-band): "tayyor turgan, keyin yo'qoldi" yozuvining izohi
    (foydalanuvchi matni) ishlab chiqarish braki BELGISI bilan boshlansa, yozuv
    ishlab chiqarish braki deb o'qilardi (O'LCHANGAN, SQLite va PG, `work/probe57.py`):
    mahsulot soni va tan narxi kamaygan, lekin Moliya uni brak xarajatiga
    QO'SHMASDI (sof foyda oshib ko'rinardi), `/returns/stats` ishlab chiqarish
    braki deb sanardi, tahlil turi noto'g'ri, bekor qilish esa rad etilardi.

    Buxgalteriya matnga emas, REJIMGA bo'ysunishi uchun bunday izoh "Izoh: "
    bilan saqlanadi — foydalanuvchi matni o'zgarmaydi, faqat belgi boshida
    qolmaydi. Katta-kichik harf farqsiz: SQLite `LIKE` ASCII da harf farqlamaydi
    (`get_return_stats`), shunda har bazada bir xil."""
    if reason is None:
        return None
    if str(reason).lower().startswith(_ISH_BRAK_BELGI.lower()):
        return "Izoh: " + str(reason)
    return reason


def delete_finished_product_loss(db: Session, loss_id: int, company_id: int = None,
                                 performed_by: str = None) -> dict:
    """Brak (yo'qotish) yozuvini BEKOR QILADI.

    NIMA UCHUN QO'SHILDI (2026-09-20): `record_finished_product_loss()`
    bor edi, lekin uni orqaga qaytarish yo'li HECH QAYERDA yo'q edi —
    xato yozilgan brak Moliya hisobotida abadiy qolib ketardi va
    "Brak xarajati" ni jimgina shishirardi. Bu — haqiqiy bo'shliq:
    aynan shu sabab sinov tozalashi paytida sentabr sof foydasi
    6 573 773 so'mga siljib ketdi.

    Xatti-harakat:
      - Mahsulot hali mavjud bo'lsa — miqdor va tan narx QAYTARILADI
        (haqiqiy "bekor qilish").
      - Mahsulot o'chirilgan bo'lsa — faqat yozuv o'chiriladi.
    Ikkala holatda ham yozuv Faoliyat jurnaliga tushadi.
    """
    from models import FinishedProduct, FinishedProductLoss

    q = db.query(FinishedProductLoss).filter(FinishedProductLoss.id == loss_id)
    if company_id is not None:
        q = q.filter(FinishedProductLoss.company_id == company_id)
    loss = q.first()
    if not loss:
        return {"success": False, "message": "Brak yozuvi topilmadi"}

    # 18-band (2026-09-21, jonli o'lchandi): "ishlab chiqarish braki"
    # mahsulot soniga TEGMAYDI, balki penoplast/loyni ombordan QO'SHIMCHA
    # ayiradi; moliyadagi xarajati esa InventoryMovement ("Brak%") dan
    # hisoblanadi, bu yozuvdan emas. Ilgari bu yerda uni ham oddiy brak
    # kabi "bekor qilardi": mahsulot miqdori YO'QDAN oshardi (2 -> 2.1),
    # tan narxi shishardi, penoplast omborga QAYTMASDI, xarajat moliyada
    # QOLARDI — ya'ni bekor qilish hisobni tuzatmay, aksincha buzardi.
    # Endi rad etiladi, hech narsa o'zgarmaydi. Korxona tekshiruvi
    # YUQORIDA — begona yozuv baribir "topilmadi" (oracle yo'q).
    if _ish_brakimi(loss):
        return {"success": False, "kod": "ishlab_chiqarish_braki",
                "message": ("Ishlab chiqarish brakini bu yo'l bilan bekor "
                            "qilib bo'lmaydi — xomashyo ombordan allaqachon "
                            "sarflangan, mahsulot soni esa o'zgarmagan edi")}

    qty = float(loss.quantity or 0)
    cost = float(loss.cost_amount or 0)
    nomi = loss.product_name
    tiklandi = False

    if loss.finished_product_id:
        fpq = db.query(FinishedProduct).filter(
            FinishedProduct.id == loss.finished_product_id)
        if company_id is not None:
            fpq = fpq.filter(FinishedProduct.company_id == company_id)
        fp = fpq.with_for_update().first()
        if fp:
            fp.quantity = float(fp.quantity or 0) + qty
            fp.cost_price = float(fp.cost_price or 0) + cost
            tiklandi = True

    db.delete(loss)
    try:
        log_activity(db, "delete", "finished_product_loss", loss_id,
                     f"Brak bekor qilindi: {nomi} — {qty:g} {loss.unit or ''} "
                     f"({cost:,.0f} so'm)"
                     + (" · ombor tiklandi" if tiklandi else " · mahsulot o'chirilgan"),
                     performed_by=performed_by, company_id=company_id)
    except Exception:
        pass
    db.commit()
    return {"success": True, "qaytarilgan_summa": cost,
            "ombor_tiklandi": tiklandi, "mahsulot": nomi}


def _ishlab_chiqarish_braki_xomashyo(db: Session, fp, brak_qty, penoplast_vol_needed,
                                     loy_kg_needed, company_id, _brak_inv, log) -> dict:
    """kech52 (13-band, 3-qadam): `record_finished_product_production_brak` ning
    xomashyo yechish qismi (mazmuni O'ZGARMAGAN — faqat ko'chirildi; chaqiruvchi uni
    brak belgisi oynasi ichida `try/finally` bilan chaqiradi). Muvaffaqiyatda
    `{"success": True, "peno_cost", "loy_cost"}`, aks holda chaqiruvchi qaytaradigan
    `{"success": False, "message"}` (hech narsa yozilmasdan OLDIN — avvalgidek).

    K52-1 (kech52, PostgreSQL da O'LCHANDI): harakat sababi 150 belgili mahsulot
    nomi, qoplama va "12.345" kabi miqdor bilan 201 belgi bo'lardi — `reason`
    String(200), COMMIT da 500 ("Serverda kutilmagan xato"), brak yozilmasdi.
    Endi `_jurnal_sabab` (200 belgiga xavfsiz qisqartirish; boshi o'zgarmaydi)."""
    import services
    peno_cost = 0.0
    loy_cost = 0.0

    # 1) Penoplast — QO'SHIMCHA ayiriladi
    if penoplast_vol_needed > 0:
        if not fp.penoplast_id:
            return {"success": False, "message": "Bu mahsulotning Penoplast turi noma'lum — qo'lda hisoblash kerak"}
        p = _brak_inv(fp.penoplast_id)
        if not p:
            return {"success": False, "message": "Penoplast ombordan topilmadi"}
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks = penoplast_vol_needed / vol_per_unit
        if float(p.stock_quantity) < blocks:
            return {"success": False, "message": f"Penoplast yetishmayapti! Kerak: {blocks:.2f} blok, omborda: {float(p.stock_quantity):.2f} blok"}
        p.stock_quantity = float(p.stock_quantity) - blocks
        peno_cost = blocks * float(p.price_per_unit or 0)
        log.append(f"{p.item_name}: -{blocks:.2f} blok")
        # MUHIM (2026-09 audit): oldin bu yerda log_movement() chaqirilmagan
        # edi — Penoplast kamayishi ombor tarixida (InventoryMovement)
        # umuman ko'rinmas edi, va "Brak xarajati" hisobotiga (Returns
        # sahifasidagi get_brak_material_summary, "Brak%" bo'yicha qidiradi)
        # bu miqdor UMUMAN kirmasdi — brak orqali sarflangan xomashyo
        # hisobotdan butunlay yashiringan bo'lardi.
        log_movement(
            db, p.id, p.item_name, movement_type="out",
            quantity=blocks, unit=p.unit,
            reason=_jurnal_sabab(f"Brak (ishlab chiqarish) — {fp.name} ({brak_qty:g} birlik)")
        )

    # 2) Loy — QO'SHIMCHA ayiriladi (agar qoplama bo'lsa), xuddi shu
    # retseptdan (fp.recipe_id), ishlab chiqarishdagi kabi
    if loy_kg_needed > 0:
        # 2026-09-21 — TENANT. Oldin bu yerda `db.query(Recipe).first()`
        # zaxira yo'li bor edi: retsepti YO'Q korxona brak yozsa, BOSHQA
        # korxonaning retsepti olinar va uning ingredientlari o'sha
        # korxonaning omboridan ayirilar edi (o'lchangan: 995 → 992.5 kg).
        _brak_cid = company_id if company_id is not None else getattr(fp, 'company_id', None)
        recipe = services.resolve_recipe(db, recipe_id=fp.recipe_id,
                                         company_id=_brak_cid)
        loy_info = services.get_loy_cost_per_kg(
            db, recipe.id if recipe else None, company_id=_brak_cid)
        loy_cost = loy_kg_needed * float(loy_info.get("cost_per_kg", 0))

        class _FakeOrder:
            def __init__(self, rid, cid):
                self.id = None
                # `company_id` SHART: services.resolve_recipe korxonani
                # buyurtma obyektidan ham oladi.
                self.company_id = cid
                self.order_number = "TAYYOR MAHSULOT — ISHLAB CHIQARISH BRAKI"
        fake = _FakeOrder(recipe.id if recipe else None, _brak_cid)
        log.extend(services.deduct_loy_ingredients(
            db, fake, loy_kg_needed, use_stock=False,
            recipe_id=(recipe.id if recipe else None),
            company_id=_brak_cid,
            # MUHIM (2026-09 audit): reason "Brak" bilan boshlanishi SHART —
            # get_brak_material_summary() aynan "Brak%" naqshi bo'yicha
            # qidiradi (boshqa "Brak (ishlab chiqarish) — ..." yozuvlari
            # bilan bir xil uslubda). Avvalgi matn ("Tayyor mahsulot ishlab
            # chiqarish braki: ...") bu naqshga to'g'ri kelmagani uchun,
            # shu yo'l orqali yozilgan loy sarfi "Brak xarajati" hisobotidan
            # butunlay tashqarida qolar edi.
            reason_override=_jurnal_sabab(f"Brak (ishlab chiqarish) — {fp.name} (qoplama, {brak_qty:g} birlik)")
        ))

    return {"success": True, "peno_cost": peno_cost, "loy_cost": loy_cost}


def _mrp_ishlab_chiqarish_braki_xomashyo(db: Session, fp, brak_qty, qatorlar, log) -> dict:
    """kech54 (13-band, 5-qadam): MRP tayyor mahsuloti ishlab chiqarish braki — yetarliligi
    tekshirilgan surat qatorlarini ombordan yechadi. Chaqiruvchining brak oynasi
    (`_brak_harakat`) ichida: `log_movement` harakatni brak deb belgilaydi va narxni muzlatadi.
    Ombor 0 dan pastga tushmaydi (tekshiruv chaqiruvchida, hech narsa yozilmasdan OLDIN)."""
    xomashyo_cost = 0.0
    for inv, kerak in qatorlar:
        inv.stock_quantity = float(inv.stock_quantity or 0) - kerak
        xomashyo_cost += kerak * float(inv.price_per_unit or 0)
        log_movement(
            db, inv.id, inv.item_name, movement_type="out",
            quantity=kerak, unit=inv.unit,
            reason=_jurnal_sabab(f"Brak (ishlab chiqarish) — {fp.name} ({brak_qty:g} birlik)"))
        log.append(f"{inv.item_name}: -{kerak:g} {inv.unit}")
    return {"success": True, "peno_cost": 0.0, "loy_cost": 0.0, "xomashyo_cost": xomashyo_cost}


def record_finished_product_production_brak(db: Session, finished_product_id: int, brak_qty: float = None,
                                              notes: str = None, created_by: str = None,
                                              company_id: int = None, brak_bosqich: str = None,
                                              brak_sabab: str = None,
                                              brak_javobgar_id: int = None) -> dict:
    """Tayyor mahsulot ISHLAB CHIQARISH JARAYONIDA chiqqan brak (masalan
    kesish yoki qoplama tortish paytida sinib ketishi) — bu, mahsulotdan
    KEYINCHALIK (allaqachon tayyor turgan holda) yo'qotilishidan FARQ
    QILADI: bu yerda YAKUNIY yetkaziladigan/omborga kiritiladigan miqdor
    O'ZGARMAYDI (ustadan qayta ishlab chiqarilib, o'rni to'ldiriladi),
    faqat O'SHA qayta ishlab chiqarish uchun QO'SHIMCHA xomashyo (Penoplast/
    Bazalt+Serpiyanka+Kley, loy) ombordan ayiriladi. Shuning uchun,
    mavjud "Kamaytirish" funksiyasidan farqli o'laroq — fp.quantity
    (ombordagi mahsulot soni) ga UMUMAN TEGILMAYDI.

    Ishlaydi: Profil/Panel/Donali/Blok (Penoplast+loy asosida, unit_volume_m3
    orqali) va Termopanel/Bazalt (Bazalt+Serpiyanka+Kley+loy asosida, aynan
    ishlab chiqarishda ishlatilgan xomashyo/nisbat bo'yicha) — bularda
    `brak_qty` (mahsulot birligida) berilib, xomashyo BARQAROR nisbatdan
    hisoblanadi."""
    from models import FinishedProduct, FinishedProductLoss, Inventory

    # M4: mahsulot FAQAT joriy korxonadan (aks holda "topilmadi").
    # 17-band: qiymatlar QAT'IY — hech narsa yozilmasdan OLDIN.
    try:
        _clean_val("ProductionBrak", {"finished_product_id": finished_product_id,
                                      "brak_qty": brak_qty, "notes": notes,
                                      # kech56 (13-band, 7-qadam): sabab va javobgar hodim
                                      "brak_sabab": brak_sabab,
                                      "brak_javobgar_id": brak_javobgar_id,
                                      "brak_bosqich": brak_bosqich})
    except ValueError as _e:
        return {"success": False, "message": str(_e)}
    fp = get_finished_product(db, finished_product_id, company_id, lock=True)
    if not fp:
        return {"success": False, "message": "Mahsulot topilmadi"}
    # kech56 (13-band, 7-qadam): javobgar hodim — shu korxonaning hodimi (xomashyo
    # yechilishidan va yozuvdan OLDIN)
    try:
        _brak_javobgar_tekshir(db, brak_javobgar_id, getattr(fp, 'company_id', None))
    except ValueError as _e:
        return {"success": False, "message": str(_e)}

    # M4: brak'da ayiriladigan XOMASHYO ham faqat shu korxonaniki bo'lishi
    # shart — aks holda A korxonaning braki B korxonaning omborini
    # kamaytirib qo'yardi.
    _brak_cid = company_id if company_id is not None else getattr(fp, 'company_id', None)

    def _brak_inv(inv_id):
        if not inv_id:
            return None
        _q = db.query(Inventory).filter(Inventory.id == inv_id)
        if _brak_cid is not None:
            _q = _q.filter(Inventory.company_id == _brak_cid)
        return _q.with_for_update().first()

    if brak_qty is None or brak_qty <= 0:
        return {"success": False, "message": "Brak miqdori noto'g'ri"}

    unit_vol = float(fp.unit_volume_m3 or 0)
    unit_loy = float(fp.unit_loy_kg or 0)
    penoplast_vol_needed = brak_qty * unit_vol
    loy_kg_needed = (brak_qty * unit_loy) if fp.is_coated else 0.0

    # kech54 (13-band, 5-qadam): MRP tayyor mahsuloti (`dynamic_bom`) — penoplast / loy
    # nisbati yo'q (O'LCHANGAN, asl kod: 400 "xomashyo nisbati topilmadi"). Qo'shimcha sarf —
    # shu mahsulotni ishlab chiqargan buyurtmaning retsept SURATIDAN, 1 birlikka (qoplama
    # bilan — penoplast yo'lidagi `fp.is_coated` loyi kabi; qadoqsiz). Yetarlilik HAMMASI shu
    # yerda, yozuvdan OLDIN (penoplast yo'li bilan bir xil qat'iy qoida).
    _mrp_qatorlar = None
    if (fp.category or '') == 'dynamic_bom':
        import services as _svc_mrp
        _sarf = _svc_mrp._mrp_birlik_sarfi(db, _brak_cid, finished_product=fp, qoplama=True)
        _mrp_qatorlar = []
        for _inv_id, _birlik in sorted((_sarf or {}).items()):
            _kerak = float(_birlik) * float(brak_qty)
            if _kerak <= 0:
                continue
            _inv = _brak_inv(_inv_id)
            if not _inv:
                return {"success": False, "message": f"Xomashyo ombordan topilmadi (ID {_inv_id})"}
            if float(_inv.stock_quantity or 0) < _kerak:
                return {"success": False,
                        "message": (f"{_inv.item_name} yetishmayapti! Kerak: {_kerak:.2f} {_inv.unit}, "
                                    f"omborda: {float(_inv.stock_quantity or 0):.2f} {_inv.unit}")}
            _mrp_qatorlar.append((_inv, _kerak))
        if not _mrp_qatorlar:
            return {"success": False, "message": ("Bu mahsulotning ishlab chiqarish retsepti surati topilmadi "
                                                  "(hali ishlab chiqarilmagan bo'lishi mumkin) — qo'lda hisoblash kerak")}

    if _mrp_qatorlar is None and penoplast_vol_needed <= 0 and loy_kg_needed <= 0:
        return {"success": False, "message": "Bu mahsulot uchun xomashyo nisbati topilmadi (eski yozuv bo'lishi mumkin) — qo'lda hisoblash kerak"}

    log = []
    peno_cost = 0.0
    loy_cost = 0.0

    # kech52 (13-band, 3-qadam): xomashyo yechish — `_ishlab_chiqarish_braki_xomashyo`.
    # Shu oraliqda yozilgan HAR chiqim harakati (penoplast, loy ingredientlari —
    # `services` ichidagi chuqur chaqiruvlar ham) `log_movement` da brak deb
    # belgilanadi (`db.info["_brak_harakat"]`); belgi `finally` da olinadi —
    # yordamchidagi erta `return` (penoplast yetishmayapti va h.k.) ham uni
    # sessiyada qoldirmaydi.
    db.info["_brak_harakat"] = True
    try:
        if _mrp_qatorlar is not None:
            # kech54 (13-band, 5-qadam): MRP mahsuloti — surat qatorlari (yuqorida tekshirilgan)
            _xom = _mrp_ishlab_chiqarish_braki_xomashyo(db, fp, brak_qty, _mrp_qatorlar, log)
        else:
            _xom = _ishlab_chiqarish_braki_xomashyo(
                db, fp, brak_qty, penoplast_vol_needed, loy_kg_needed, company_id, _brak_inv, log)
    finally:
        db.info.pop("_brak_harakat", None)
    if not _xom.get("success"):
        return _xom
    peno_cost = _xom["peno_cost"]
    loy_cost = _xom["loy_cost"]
    # kech54 (5-qadam): MRP mahsulotining surat xomashyosi (boshqa turlarda 0)
    xomashyo_cost = float(_xom.get("xomashyo_cost", 0.0))

    total_cost = peno_cost + loy_cost + xomashyo_cost

    # MUHIM: fp.quantity GA TEGILMAYDI — yakuniy mahsulot miqdori
    # o'zgarmagani uchun. Faqat Moliyada xarajat sifatida qayd etiladi.
    loss = FinishedProductLoss(
        company_id=getattr(fp, 'company_id', None),      # M8/F1
        finished_product_id=fp.id,
        product_name=fp.name,
        category=fp.category,
        quantity=brak_qty,
        unit=fp.unit,
        cost_amount=total_cost,
        reason=f"{_ISH_BRAK_BELGI} — qo'shimcha xomashyo sarflandi (mahsulot soniga tegmaydi)"
               + (f". Izoh: {notes}" if notes else ""),
        created_by=created_by,
        # kech53 (13-band, 1-qadam): ixtiyoriy brak bosqichi (`_clean_val` tekshirgan)
        brak_bosqich=brak_bosqich,
        # kech56 (13-band, 7-qadam): ixtiyoriy sabab va javobgar hodim (tekshirilgan)
        brak_sabab=brak_sabab,
        brak_javobgar_id=brak_javobgar_id
    )
    db.add(loss)
    db.commit()
    db.refresh(loss)

    return {
        "success": True,
        "loss_id": loss.id,
        "cost_amount": float(total_cost),
        "penoplast_cost": float(peno_cost),
        "loy_cost": float(loy_cost),
        "xomashyo_cost": float(xomashyo_cost),   # kech54 (5-qadam): MRP surat xomashyosi
        "log": log,
    }


def _sotuv_ustasi_xatosi(db: Session, master_id, company_id):
    """17-band: sotuvga biriktirilgan usta SHU korxonadan bo'lishi shart.
    Ilgari mavjud bo'lmagan `master_id` ham yozilardi (SQLite da jim;
    PostgreSQL da FK → 500). Xato matni yoki None qaytaradi."""
    if master_id is None:
        return None
    from models import Master
    q = db.query(Master).filter(Master.id == master_id)
    if company_id is not None:
        q = q.filter(Master.company_id == company_id)
    if not q.first():
        return "Usta topilmadi"
    return None


def sell_finished_products_batch(db: Session, data, created_by: str = None,
                                company_id: int = None) -> dict:
    """Bir nechta turli tayyor mahsulotni, BITTA xaridorga, BITTA Yuk xati
    bilan sotadi ("savatcha"). Barchasi BITTA tranzaksiyada — birortasi
    xato bersa, HECH BIRI saqlanmaydi (rollback)."""
    import uuid
    from models import FinishedProduct, FinishedProductSale

    if not data.items:
        return {"success": False, "message": "Hech qanday mahsulot tanlanmagan"}
    # 17-band: tana qiymatlari QAT'IY — hech narsa yozilmasdan OLDIN.
    try:
        _clean_val("SaleBatch", _val_dump(data, "SaleBatch"))
    except ValueError as _e:
        return {"success": False, "message": str(_e)}
    _usta_xato = _sotuv_ustasi_xatosi(db, getattr(data, "master_id", None), company_id)
    if _usta_xato:
        return {"success": False, "message": _usta_xato}

    group_id = uuid.uuid4().hex[:16]
    # 17-band: BIR mahsulot savatchada bir necha qatorda bo'lsa — qoldiq
    # YIG'INDIGA tekshiriladi (ilgari har qator alohida: 6 + 6, qoldiq 10 →
    # qoldiq -2 ga tushardi, O'LCHANGAN).
    _savatda = {}

    try:
        # ── 1-BOSQICH: har detalning ASL summasini hisoblab, tekshiramiz ──
        # (hali DB'ga yozmaymiz — avval umumiy asl jamini bilishimiz kerak,
        #  chegirma koeffitsientini shundan hisoblaymiz.)
        prepared = []   # {fp, quantity, unit_price, original_total, cost_amount}
        original_grand_total = 0.0
        for item in data.items:
            # M4: har bir mahsulot FAQAT joriy korxonadan. Boshqa
            # korxonaniki bo'lsa — "topilmadi" va BUTUN savatcha rad
            # etiladi (rollback), ya'ni B ning qoldig'iga tegilmaydi.
            fp = get_finished_product(db, item.finished_product_id, company_id, lock=True)
            if not fp:
                db.rollback()
                return {"success": False, "message": f"Mahsulot (ID {item.finished_product_id}) topilmadi"}

            if not _fp_tayyormi(fp):
                db.rollback()
                return {"success": False, "message": f"{fp.name}: {_FP_JARAYONDA_XABAR}"}

            available = float(fp.quantity or 0) - float(fp.reserved_quantity or 0)
            _jami_qty = _savatda.get(fp.id, 0.0) + item.quantity
            if _jami_qty > available + 0.001:
                db.rollback()
                extra = f" (shundan {fp.reserved_quantity:g} {fp.unit} boshqa buyurtmaga band qilingan)" if fp.reserved_quantity else ""
                return {"success": False, "message": f"{fp.name}: sotish mumkin faqat {available:g} {fp.unit} bor{extra}, {_jami_qty:g} sota olmaysiz"}
            _savatda[fp.id] = _jami_qty

            orig_total = item.quantity * item.unit_price
            if round(orig_total, 2) > _ORDER_ITEM_MAX_MONEY:
                db.rollback()
                return {"success": False, "message": f"{fp.name}: sotuv summasi (miqdor × narx) juda katta"}
            # FASA 4B: yagona manba — pastdagi izohga qarang (sell_finished_product)
            unit_cost = _fp_stable_unit_cost(db, fp)
            if unit_cost <= 0 and available > 0:
                unit_cost = float(fp.cost_price or 0) / available

            # XAVFSIZLIK/NAZORAT: sell_finished_product'dagi bilan bir xil —
            # sotuv narxi tan narxidan past bo'lsa, aniq tasdiqlash so'raladi.
            if unit_cost > 0 and float(item.unit_price) < unit_cost and not getattr(data, "confirm_below_cost", False):
                db.rollback()
                return {
                    "success": False,
                    "type": "below_cost_warning",
                    "message": (
                        f"{fp.name}: kiritilgan narx (1 {fp.unit} uchun {item.unit_price:,.0f} so'm) juda past — "
                        f"bu narxda sotib bo'lmaydi. Shunday ham davom etasizmi?"
                    )
                }

            cost_amount = unit_cost * item.quantity

            prepared.append({
                "fp": fp,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "original_total": orig_total,
                "cost_amount": cost_amount,
            })
            original_grand_total += orig_total

        # ── "Kelishilgan summa" (butun savatchaga BITTA) ─────────────────
        # agreed berilmasa yoki asl jamiga teng/katta bo'lsa — chegirma yo'q.
        agreed = getattr(data, "agreed_amount", None)
        if agreed is None or original_grand_total <= 0 or agreed >= original_grand_total - 0.5:
            agreed_grand_total = original_grand_total
            discount_percent = 0.0
        else:
            agreed_grand_total = float(agreed)
            discount_percent = round((1 - agreed_grand_total / original_grand_total) * 100, 2)

        # ── 2-BOSQICH: yozib chiqamiz. Chegirma har qatorga PROPORSIONAL ──
        # total_amount (moliya uchun) = asl summaning kelishilgan ulushi.
        # unit_price/original_total — asl (PDF asl narxni shundan tiklaydi).
        # MUHIM: yaxlitlash qoldig'i yo'qolib/qo'shilib ketmasligi uchun —
        # oxirgi qatorga (agreed − oldingilar yig'indisi) beriladi, shunda
        # qatorlar yig'indisi ANIQ kelishilgan summaga teng bo'ladi.
        sales = []
        total_all = 0.0
        profit_all = 0.0
        n = len(prepared)
        allocated = 0.0
        for idx, p in enumerate(prepared):
            fp = p["fp"]
            if agreed_grand_total == original_grand_total:
                line_total = p["original_total"]
            elif idx < n - 1:
                line_total = round(p["original_total"] * agreed_grand_total / original_grand_total, 2)
                allocated += line_total
            else:
                # oxirgi qator — qoldiqni to'liq oladi (yaxlitlash farqini yutadi)
                line_total = round(agreed_grand_total - allocated, 2)

            fp.quantity = float(fp.quantity or 0) - p["quantity"]
            if fp.cost_price:
                fp.cost_price = float(fp.cost_price) - p["cost_amount"]

            sale = FinishedProductSale(
                company_id=getattr(fp, 'company_id', None),   # M8/F1
                finished_product_id=fp.id,
                product_name=fp.name,
                quantity=p["quantity"],
                unit=fp.unit,
                unit_price=p["unit_price"],
                total_amount=line_total,
                cost_amount=p["cost_amount"],
                original_total=p["original_total"],
                group_discount_percent=discount_percent,
                buyer_name=data.buyer_name,
                payment_method=data.payment_method,
                notes=data.notes,
                created_by=created_by,
                sale_group_id=group_id,
                master_id=getattr(data, 'master_id', None)
            )
            db.add(sale)
            sales.append(sale)
            total_all += line_total
            profit_all += (line_total - p["cost_amount"])

        db.commit()
        for s in sales:
            db.refresh(s)

        return {
            "success": True,
            "sale_group_id": group_id,
            "sale_count": len(sales),
            "original_total": round(original_grand_total),
            "discount_percent": discount_percent,
            "total_amount": round(total_all),   # kelishilgan (chegirilgan) summa
            "profit": round(profit_all)
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Xato yuz berdi: {str(e)}"}


def sell_finished_product(db: Session, data, created_by: str = None,
                         company_id: int = None) -> dict:
    """Tayyor mahsulotni to'g'ridan-to'g'ri sotadi (buyurtma/Yuk xatisiz).
    Qoldiqdan ayiradi, savdo yozuvini yaratadi. cost_amount — mahsulotning
    o'z cost_price'iga proporsional (odatda G'isht kabi mahsulotlarda 0)."""
    from models import FinishedProduct, FinishedProductSale

    # M4: mahsulot FAQAT joriy korxonadan (aks holda "topilmadi").
    # 17-band: tana qiymatlari QAT'IY — hech narsa yozilmasdan OLDIN.
    try:
        _clean_val("Sale", _val_dump(data, "Sale"))
    except ValueError as _e:
        return {"success": False, "message": str(_e)}
    fp = get_finished_product(db, data.finished_product_id, company_id, lock=True)
    if not fp:
        return {"success": False, "message": "Mahsulot topilmadi"}
    if not _fp_tayyormi(fp):
        return {"success": False, "message": _FP_JARAYONDA_XABAR}

    available = float(fp.quantity or 0)
    if data.quantity > available + 0.001:
        return {"success": False, "message": f"Omborda faqat {available:g} {fp.unit} bor, {data.quantity:g} sota olmaysiz"}

    _usta_xato = _sotuv_ustasi_xatosi(db, getattr(data, "master_id", None),
                                      company_id if company_id is not None else fp.company_id)
    if _usta_xato:
        return {"success": False, "message": _usta_xato}

    total_amount = data.quantity * data.unit_price
    if round(total_amount, 2) > _ORDER_ITEM_MAX_MONEY:
        return {"success": False, "message": "Sotuv summasi (miqdor × narx) juda katta"}
    # FASA 4B: "1 birlik tan narxi" endi BARCHA joyda (sotish, buyurtmaga
    # olish/qaytarish, hisobot) BITTA manbadan — _fp_stable_unit_cost'dan
    # olinadi (xomashyoning joriy narxidan hisoblanadi). Avval bu yerda
    # `cost_price / available` ishlatilardi — bu boshqa ikkita joydagi
    # formuladan farq qilib, uchtasi turlicha natija berardi.
    unit_cost = _fp_stable_unit_cost(db, fp)
    if unit_cost <= 0 and available > 0:
        # Orqaga moslik: xomashyo ma'lumoti yo'q (eski/oddiy) yozuvlar uchun
        unit_cost = float(fp.cost_price or 0) / available

    # XAVFSIZLIK/NAZORAT: agar sotuv narxi tan narxidan PAST bo'lsa — bu
    # zarar bilan sotuv (yoki xodimning xatosi/suiiste'moli bo'lishi mumkin).
    # Butunlay TAQIQLAMAYMIZ (chunki chegirma/aksiya kabi qonuniy holatlar
    # ham bo'lishi mumkin), lekin aniq tasdiqlash talab qilamiz. MUHIM: tan
    # narxining o'zi (mahsulot tannarxi — ichki, nozik ma'lumot) xabarda
    # KO'RSATILMAYDI — xodim uni bilmasligi kerak, faqat "bu narxda sotib
    # bo'lmaydi" degan xabarni ko'radi.
    if unit_cost > 0 and float(data.unit_price) < unit_cost and not getattr(data, "confirm_below_cost", False):
        return {
            "success": False,
            "type": "below_cost_warning",
            "message": (
                f"Kiritilgan narx (1 {fp.unit} uchun {data.unit_price:,.0f} so'm) juda past — "
                f"bu narxda sotib bo'lmaydi. Shunday ham davom etasizmi?"
            )
        }

    cost_amount = unit_cost * data.quantity

    fp.quantity = available - data.quantity
    if fp.cost_price:
        fp.cost_price = float(fp.cost_price) - cost_amount

    sale = FinishedProductSale(
        company_id=getattr(fp, 'company_id', None),      # M8/F1
        finished_product_id=fp.id,
        product_name=fp.name,
        quantity=data.quantity,
        unit=fp.unit,
        unit_price=data.unit_price,
        total_amount=total_amount,
        cost_amount=cost_amount,
        buyer_name=data.buyer_name,
        payment_method=data.payment_method,
        notes=data.notes,
        created_by=created_by,
        master_id=getattr(data, 'master_id', None)
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return {
        "success": True,
        "sale_id": sale.id,
        "product_name": fp.name,
        "total_amount": float(total_amount),
        "profit": float(total_amount - cost_amount),
        "remaining_stock": float(fp.quantity)
    }


def produce_finished_product(db: Session, data: ProduceCreate, created_by: str = None,
                            company_id: int = None) -> dict:
    """Ishlab chiqarish boshlanadi:
    - Penoplast DARHOL ombordan yechiladi (kesish boshlanadi)
    - Loy REJA sifatida saqlanadi — "Tayyor" bosilganda aniq miqdor yechiladi
    - Har ishlab chiqarish alohida yozuv — birlashtirilmaydi (loy hisobi aniq bo'lishi uchun)
    """
    import services
    from models import ProductionStatus

    # 17-band: tana qiymatlari QAT'IY — hech narsa yozilmasdan OLDIN
    # (manfiy o'lcham → manfiy hajm → penoplast yechilmay mahsulot BEPUL
    # paydo bo'lardi; NaN / cheksizlik → 500 + yarim yozuv — O'LCHANGAN).
    try:
        _clean_val("Produce", _val_dump(data, "Produce"))
    except ValueError as _e:
        return {"success": False, "message": str(_e)}

    qty = _fp_qty(data)
    if qty <= 0:
        return {"success": False, "message": "Miqdor kiritilmagan"}

    # Hajmni hisoblaymiz
    class _Tmp:
        pass
    tmp = _Tmp()
    tmp.category = data.category
    tmp.width = data.width
    tmp.thickness = data.thickness
    tmp.length = data.length
    tmp.quantity = data.quantity or 1
    tmp.unit_price = getattr(data, 'unit_price_for_volume', None) or data.unit_price
    tmp.penoplast_id = data.penoplast_id
    tmp.price_per_m3 = data.price_per_m3
    tmp.finished_product_id = None

    default_p = services.get_default_penoplast(db, company_id=company_id)
    volume = services._item_volume_m3(db, tmp, default_p)

    pid = data.penoplast_id or (default_p.id if default_p else None)

    # M4 (2026-09-18) — TENANT: Penoplast FAQAT joriy korxonadan olinadi.
    # Ilgari mijoz yuborgan `penoplast_id` faqat id bo'yicha o'qilardi —
    # A korxona xodimi B korxonaning penoplast qoldig'ini kamaytirib
    # yuborishi mumkin edi.
    def _pf_inv(inv_id, lock=False):
        if not inv_id:
            return None
        _q = db.query(Inventory).filter(Inventory.id == inv_id)
        if company_id is not None:
            _q = _q.filter(Inventory.company_id == company_id)
        if lock:
            _q = _q.with_for_update()
        return _q.first()

    # Penoplast yetadimi
    shortages = []
    if volume > 0 and pid:
        p = _pf_inv(pid)
        if company_id is not None and not p:
            return {"success": False, "message": "Tanlangan Penoplast ombordan topilmadi"}
        # 17-band: faqat PENOPLAST material "blok" sifatida yechiladi —
        # ilgari oddiy material (masalan kg dagi kimyo) ham yechilardi.
        if p and not _penoplastmi(p):
            return {"success": False, "message": f"{p.item_name} — penoplast emas"}
        if p:
            vol_per_unit = float(p.volume_per_unit or 1.0)
            blocks = volume / vol_per_unit
            if float(p.stock_quantity) < blocks:
                shortages.append(
                    f"{p.item_name}: kerak {blocks:.1f} blok, qoldi {float(p.stock_quantity):.1f} blok"
                )
    if shortages:
        return {"success": False, "message": "Xomashyo yetishmayapti!", "shortages": shortages}

    log = []
    peno_cost = 0.0
    loy_cost = 0.0

    # 1) Penoplastni DARHOL yechamiz
    if volume > 0 and pid:
        p = _pf_inv(pid, lock=True)
        if p:
            vol_per_unit = float(p.volume_per_unit or 1.0)
            blocks = volume / vol_per_unit
            # 20-band (2026-09-21): 0 ga QIRQILMAYDI. Yetishmovchilik yuqorida
            # rad etiladi; qirqish faqat manfiy "qarz"ni jimgina o'chirardi
            # (jurnalga esa to'liq `blocks` yoziladi).
            p.stock_quantity = float(p.stock_quantity) - blocks
            peno_cost = blocks * float(p.price_per_unit or 0)
            log.append(f"{p.item_name}: -{blocks:.2f} blok")
            # MUHIM: avval bu yerda Ombor harakati (log_movement) UMUMAN
            # yozilmasdi — Penoplast sarfi Omborxonaning "Harakatlar
            # tarixi"da butunlay ko'rinmas edi. Endi, boshqa xomashyolar
            # kabi, aniq mahsulot nomi bilan yoziladi.
            log_movement(
                db, p.id, p.item_name, movement_type="out", quantity=blocks,
                unit=p.unit, reason=f"Ishlab chiqarish: {data.name.strip()}"
            )

    # 2) Loyni ham DARHOL yechamiz (bir marta so'raladi)
    loy_kg = float(data.loy_kg or 0)
    if loy_kg > 0:
        # M4 — TENANT: retsept ham faqat joriy korxonadan. "Birinchi
        # topilgan retsept" (fallback) ham SHU korxona ichidan olinadi.
        # 2026-09-21 — qidiruv `services.resolve_recipe` ga o'tkazildi
        # (yagona manba). Mantiq O'ZGARMADI: avval `data.recipe_id`,
        # topilmasa SHU korxonaning birinchi retsepti.
        recipe = services.resolve_recipe(db, recipe_id=data.recipe_id,
                                         company_id=company_id)

        loy_info = services.get_loy_cost_per_kg(
            db, recipe.id if recipe else None, company_id=company_id)
        loy_cost = loy_kg * float(loy_info.get("cost_per_kg", 0))

        class _FakeOrder:
            def __init__(self, rid, cid):
                class _It:
                    recipe_id = rid
                self.items = [_It()]
                self.id = None
                self.company_id = cid      # 2026-09-21 — TENANT
                self.order_number = "ISHLAB CHIQARISH"
        fake = _FakeOrder(recipe.id if recipe else None, company_id)
        log.extend(services.deduct_loy_ingredients(
            db, fake, loy_kg, use_stock=False, company_id=company_id,
            reason_override=f"Ishlab chiqarish: {data.name.strip()} (loy)"
        ))

    db.flush()

    total_cost = peno_cost + loy_cost

    # Har safar YANGI yozuv — birlashtirmaymiz (loy sarfi har birida boshqacha)
    unit = _fp_unit(data.category)
    fp = FinishedProduct(
        company_id=company_id,          # M4: tenant ANIQ beriladi
        name=data.name.strip(),
        category=data.category,
        width=data.width,
        thickness=data.thickness,
        is_coated=data.is_coated,
        quantity=qty,
        unit=unit,
        unit_price=data.unit_price,
        cost_price=total_cost,
        source=StockSource.PRODUCED,
        penoplast_id=pid,
        volume_m3=volume,
        price_per_m3=data.price_per_m3,
        planned_loy_kg=loy_kg,
        actual_loy_kg=loy_kg,          # Darhol yechilgani uchun aniq
        unit_volume_m3=(volume / qty) if qty > 0 else 0,
        unit_loy_kg=(loy_kg / qty) if qty > 0 else 0,
        recipe_id=data.recipe_id,
        # kech59 (47-band, K59-4): 1 birlik tannarxi ISHLAB CHIQARILGAN paytdagi narxda muzlaydi
        # (32-band qarori "ishlatilgan paytdagi narxda muzlatilsin" bilan bir xil). Ilgari yozilmasdi —
        # `_fp_stable_unit_cost` penoplast / loyning JORIY narxidan hisoblardi: narx oshsa sotuv,
        # buyurtmaga olish va qaytarish tannarxi ham oshardi (O'LCHANGAN — work/probe59_47.py).
        unit_cost_stable=(total_cost / qty) if qty > 0 else None,
        production_status=ProductionStatus.IN_PROGRESS,
        created_by=created_by,
        notes=data.notes
    )
    db.add(fp)
    db.commit()
    db.refresh(fp)

    revenue = float(data.unit_price or 0) * qty
    profit = revenue - total_cost
    margin = (profit / revenue * 100) if revenue > 0 else 0

    # AUDIT: ishlab chiqarish qayd etiladi
    try:
        log_activity(db, "produced", "finished_product", fp.id, fp.name, created_by,
                      new_value=f"{float(fp.quantity):g} {fp.unit}, tan narxi: {round(total_cost):,} so'm".replace(',', ' '),
                      company_id=getattr(fp, 'company_id', None))
    except Exception:
        pass

    return {
        "success": True,
        "message": "Ishlab chiqarish boshlandi!",
        "product_id": fp.id,
        "name": fp.name,
        "quantity": float(fp.quantity),
        "unit": fp.unit,
        "volume_m3": round(volume, 4),
        "penoplast_cost": round(peno_cost),
        "loy_cost": round(loy_cost),
        "total_cost": round(total_cost),
        "revenue": round(revenue),
        "profit": round(profit),
        "margin": round(margin, 1),
        "loy_kg": loy_kg,
        "inventory_log": log
    }


def complete_production(db: Session, fp_id: int, actual_loy_kg: float = 0,
                       company_id: int = None) -> dict:
    """Ishlab chiqarishni yakunlaydi — mahsulot sotuvga tayyor.
    Xomashyo allaqachon yechilgan, bu faqat status o'zgartirish."""
    from models import ProductionStatus

    fp = get_finished_product(db, fp_id, company_id)   # M4: faqat shu korxonadan
    if not fp:
        return {"success": False, "message": "Topilmadi"}

    if fp.source != StockSource.PRODUCED:
        return {"success": False, "message": "Faqat ishlab chiqarilgan mahsulot yakunlanadi"}

    if fp.production_status == ProductionStatus.READY:
        return {"success": False, "message": "Bu mahsulot allaqachon tayyor"}

    fp.production_status = ProductionStatus.READY
    fp.finished_production_at = datetime.utcnow()
    # MUHIM: hodim oyligi hisoblanadigan ASL miqdorni shu yerda "muzlatib"
    # qo'yamiz — keyinroq "Sotish" yoki "Kamaytirish (brak)" orqali
    # `quantity` kamaysa ham, hodimning haqi O'ZGARMASLIGI kerak (chunki u
    # ishni ALLAQACHON bajargan).
    fp.produced_quantity = fp.quantity

    db.commit()
    db.refresh(fp)

    qty = float(fp.quantity or 0)
    revenue = float(fp.unit_price or 0) * qty
    total_cost = float(fp.cost_price or 0)
    profit = revenue - total_cost
    margin = (profit / revenue * 100) if revenue > 0 else 0

    # 1 birlik uchun tan narxi — qisman sotilganda foyda hisoblash uchun
    cost_per_unit = (total_cost / qty) if qty > 0 else 0

    return {
        "success": True,
        "message": "Sotuvga tayyor!",
        "product_id": fp.id,
        "name": fp.name,
        "quantity": qty,
        "unit": fp.unit,
        "loy_kg": float(fp.actual_loy_kg or 0),
        "total_cost": round(total_cost),
        "cost_per_unit": round(cost_per_unit),
        "revenue": round(revenue),
        "profit": round(profit),
        "margin": round(margin, 1)
    }


def get_finished_products(db: Session, source: Optional[str] = None, only_available: bool = False,
                         company_id: int = None) -> List[FinishedProduct]:
    """Tayyor mahsulotlar ro'yxati.

    M4 (2026-09-18) — TENANT: company_id berilsa, FAQAT shu korxona
    mahsulotlari qaytariladi."""
    q = db.query(FinishedProduct)
    if company_id is not None:
        q = q.filter(FinishedProduct.company_id == company_id)
    if source:
        try:
            q = q.filter(FinishedProduct.source == StockSource(source))
        except ValueError:
            pass
    if only_available:
        q = q.filter(FinishedProduct.quantity > 0)
    # kech35 (15-band, jonli O'LCHANGAN kech28): nomi bir xil mahsulotlar orasida
    # tartib aniqlanmagan edi (PG da UPDATE dan keyin o'rin almashardi) —
    # `id` uchinchi (qidiruvda ikkinchi) kalit: tartib doim barqaror.
    return q.order_by(FinishedProduct.source, FinishedProduct.name, FinishedProduct.id).all()


def get_finished_products_for_main_page(db: Session, days: int = 90, show_all: bool = False,
                                       company_id: int = None) -> List[FinishedProduct]:
    """Tayyor mahsulotlar sahifasi uchun — tezlik uchun.

    MUHIM: ombordagi (quantity > 0) VA hali ishlab chiqarilayotgan
    (production_status=IN_PROGRESS) mahsulotlar — necha kunlik bo'lishidan
    qat'i nazar, DOIM ko'rsatiladi. Faqat ALLAQACHON TUGAGAN (quantity=0,
    tayyor) va ESKI yozuvlar standart holatda yashiriladi."""
    from models import ProductionStatus
    from datetime import timedelta

    # M4 (2026-09-18) — TENANT: SAHIFA ro'yxati. Auditda aynan shu
    # funksiya orqali B korxonaning mahsuloti A ning sahifasida
    # ko'ringan edi (H-2).
    base = db.query(FinishedProduct)
    if company_id is not None:
        base = base.filter(FinishedProduct.company_id == company_id)

    if show_all:
        # kech35 (15-band, jonli O'LCHANGAN kech28): nomi bir xil mahsulotlar orasida
        # tartib aniqlanmagan edi (PG da UPDATE dan keyin o'rin almashardi) —
        # `id` uchinchi (qidiruvda ikkinchi) kalit: tartib doim barqaror.
        return base.order_by(FinishedProduct.source, FinishedProduct.name, FinishedProduct.id).all()

    cutoff = datetime.utcnow() - timedelta(days=days)
    return base.filter(
        (FinishedProduct.created_at >= cutoff) |
        (FinishedProduct.quantity > 0) |
        (FinishedProduct.production_status == ProductionStatus.IN_PROGRESS)
    ).order_by(FinishedProduct.source, FinishedProduct.name, FinishedProduct.id).all()


def update_finished_product(db: Session, fp_id: int, data: dict,
                           company_id: int = None) -> Optional[FinishedProduct]:
    # M4: mahsulot FAQAT joriy korxonadan (aks holda None → 404).
    fp = get_finished_product(db, fp_id, company_id)
    if not fp:
        return None
    # M4: company_id hech qachon mijoz so'rovidan qabul qilinmaydi.
    data = {k: v for k, v in (data or {}).items() if k != "company_id"}
    # 14-band: qat'iy tekshiruv — HECH NARSA yozilmasdan OLDIN (ValueError → 400).
    data = _clean_update("FinishedProduct", data)
    for k, v in data.items():
        if v is not None and hasattr(fp, k):
            setattr(fp, k, v)
    db.commit()
    db.refresh(fp)
    return fp


def delete_finished_product(db: Session, fp_id: int, return_to_stock: bool = False,
                            company_id: int = None) -> bool:
    """Tayyor mahsulotni o'chirish.

    MUHIM (real hayot mantig'i): tayyor mahsulot — ALLAQACHON ishlab
    chiqarilgan, xomashyosi HAQIQATAN sarflangan. Shuning uchun:
      • Agar qoldiq > 0 bo'lsa — O'CHIRIB BO'LMAYDI (bu, omborda turgan,
        sotilmagan haqiqiy mahsulot; uni yo'qotish kerak bo'lsa "brak/
        kamaytirish" ishlatiladi, o'chirish EMAS).
      • Faqat qoldiq = 0 (to'liq sotilgan/brak qilingan) bo'lsa — yozuvni
        o'chirish mumkin (faqat ro'yxatni tozalash uchun).
      • Xomashyo HECH QACHON omborga qaytarilmaydi (u allaqachon mahsulotga
        aylangan — real hayotda sindirilsa ham qaytmaydi).
    `return_to_stock` parametri endi ISHLATILMAYDI (eski chaqiruvlar
    buzilmasligi uchun qoldirilgan)."""
    # M4: mahsulot FAQAT joriy korxonadan (aks holda False → 404/xato).
    fp = get_finished_product(db, fp_id, company_id)
    if not fp:
        return False

    # ── "JARAYONDA" (IN_PROGRESS, hali "Sotuvga tayyor" bosilmagan) ──
    # Bu — deyarli har doim XATO tuzatish (noto'g'ri nom/miqdor yozib
    # yuborilgan). Shuning uchun bunda: o'chirishga RUXSAT beramiz VA
    # ishlab chiqarishda ketgan xomashyoni (Penoplast, Loy, Bazalt)
    # OMBORGA QAYTARAMIZ. (READY — "Sotuvga tayyor" bosilgan — mahsulot
    # esa pastdagi qat'iy qoidaga bo'ysunadi: qoldiq 0 bo'lishi kerak,
    # xomashyo qaytmaydi.)
    # kech40 (K40-1) — O'LCHANGAN (asl kod, SQLite va PG, `work/probe40b.py`):
    # qaytgan (RETURNED) mahsulot holati belgilanmay yaratilardi (bazada
    # standart IN_PROGRESS), shuning uchun bu "xato tuzatish" tarmog'iga
    # tushardi: 100 metr qoldig'i bor qaytgan mahsulot jim o'chirilar va uning
    # `volume_m3` si PENOPLAST omboriga QAYTARILARDI (99 → 100 blok) — penoplast
    # allaqachon mahsulotga aylangan, qaytish soxta. Qaytgan mahsulot doim
    # tayyor (`_fp_tayyormi` — UI bilan bir xil), u pastdagi qat'iy qoidaga
    # bo'ysunadi (qoldiq 0 bo'lishi kerak, xomashyo qaytmaydi).
    if not _fp_tayyormi(fp):
        import services as _svc
        from models import Inventory as _Inv
        # M4: qaytariladigan xomashyo ham faqat SHU mahsulotning korxonasidan.
        _del_cid = getattr(fp, 'company_id', None)

        def _del_inv(_q):
            return _q.filter(_Inv.company_id == _del_cid) if _del_cid is not None else _q

        # Penoplast qaytadi
        if fp.penoplast_id and fp.volume_m3:
            p = _del_inv(db.query(_Inv).filter(_Inv.id == fp.penoplast_id)).with_for_update().first()
            if p:
                vpu = float(p.volume_per_unit or 1.0)
                _qaytgan_blok = float(fp.volume_m3) / vpu
                p.stock_quantity = float(p.stock_quantity) + _qaytgan_blok
                # 20-band (2026-09-21): qaytish JURNALGA yoziladi — ilgari
                # `produce` "out" yozardi, o'chirishdagi qaytish esa yozilmasdi
                # (jurnal yig'indisi ombor qoldig'iga mos kelmasdi).
                log_movement(
                    db, p.id, p.item_name, movement_type="in",
                    quantity=_qaytgan_blok, unit=p.unit,
                    reason=_jurnal_sabab(f"Mahsulot o'chirildi — {fp.name} (penoplast qaytarildi)")
                )
        # Loy qaytadi
        if fp.actual_loy_kg and fp.actual_loy_kg > 0:
            # 20-band: jurnal sababi — mahsulot nomi bilan (ilgari soxta
            # buyurtma obyekti tufayli har doim "Buyurtma TERMOPANEL +
            # bekor qilindi" yozilardi).
            _svc.return_loy_ingredients(
                db, _TermoFakeOrder(fp.recipe_id, getattr(fp, 'company_id', None)),
                float(fp.actual_loy_kg),
                company_id=getattr(fp, 'company_id', None),
                reason_override=_jurnal_sabab(f"Mahsulot o'chirildi — {fp.name} (loy qaytarildi)"))
        # Bog'liq yozuvlarni uzamiz (IN_PROGRESS'da sotuv bo'lmaydi, lekin
        # xavfsizlik uchun)
        from models import FinishedProductSale as _FPS, FinishedProductLoss as _FPL, OrderItem as _OI2
        # 2026-09-18: Production/MRP orqali yaratilgan (IN_PROGRESS) mahsulot
        # bo'lsa, `production_orders.finished_product_id` unga ishora qilib
        # turadi — bog'lanish uzilmasa FK cheklovi o'chirishni bloklaydi
        # (cancel_production_order'dagi bilan AYNI xato sinfi).
        try:
            from production_models import ProductionOrder as _PO_unlink
            db.query(_PO_unlink).filter(
                _PO_unlink.finished_product_id == fp_id
            ).update({"finished_product_id": None})
        except Exception:
            pass
        db.query(_FPS).filter(_FPS.finished_product_id == fp_id).update({"finished_product_id": None})
        db.query(_FPL).filter(_FPL.finished_product_id == fp_id).update({"finished_product_id": None})
        db.query(_OI2).filter(_OI2.finished_product_id == fp_id).update({"finished_product_id": None})
        # kech40 (22-band): qaytarish yozuvi endi omborga qo'shilgan mahsulotiga
        # bog'lanadi — uzilmasa PostgreSQL FK o'chirishni bloklaydi.
        db.query(ReturnItem).filter(ReturnItem.finished_product_id == fp_id,
                                    ReturnItem.company_id == fp.company_id).update(
            {"finished_product_id": None}, synchronize_session=False)
        db.delete(fp)
        db.commit()
        return True

    # Qoldiq bor bo'lsa — o'chirishga ruxsat bermaymiz
    if float(fp.quantity or 0) > 0.001:
        return False  # chaqiruvchi (API) buni foydalanuvchiga tushuntiradi

    # MUHIM: bu mahsulotga bog'liq SOTUV yozuvlari (finished_product_sales)
    # bo'lishi mumkin. Ularni to'g'ridan-to'g'ri o'chirsak — moliyaviy tarix
    # yo'qoladi. Shuning uchun bog'lanishni uzamiz (finished_product_id=NULL),
    # sotuv summasi/tarixи esa Moliyada saqlanib qoladi. Aks holda foreign
    # key cheklovi o'chirishни bloklaydi.
    # 2026-09-18: Production/MRP orqali ishlab chiqarilib YAKUNLANGAN
    # (READY) mahsulotda ham `production_orders.finished_product_id` unga
    # ishora qilib turadi — yuqoridagi IN_PROGRESS tarmog'idagi bilan AYNI
    # FK cheklovi (jonli sinovda tasdiqlangan: DELETE /api/finished/44 →
    # "production_orders_finished_product_id_fkey"). Bog'lanish uziladi,
    # ishlab chiqarish buyurtmasi TARIX sifatida saqlanib qoladi.
    try:
        from production_models import ProductionOrder as _PO_unlink2
        db.query(_PO_unlink2).filter(
            _PO_unlink2.finished_product_id == fp_id
        ).update({"finished_product_id": None})
    except Exception:
        pass
    from models import FinishedProductSale, FinishedProductLoss
    db.query(FinishedProductSale).filter(
        FinishedProductSale.finished_product_id == fp_id
    ).update({"finished_product_id": None})
    # Brak (kamaytirish) yozuvlari ham — bog'lanishni uzamiz, tarix
    # (product_name, summa) saqlanadi.
    db.query(FinishedProductLoss).filter(
        FinishedProductLoss.finished_product_id == fp_id
    ).update({"finished_product_id": None})
    # Buyurtma detallari — bog'lanishni uzamiz (detal o'z ma'lumotini
    # saqlaydi, faqat o'chirilgan mahsulotga havolasini yo'qotadi).
    from models import OrderItem as _OI
    db.query(_OI).filter(_OI.finished_product_id == fp_id).update({"finished_product_id": None})
    # kech40 (22-band): qaytarish yozuvlari — bog'lam uziladi (yozuv tarix
    # sifatida qoladi; mahsulot endi yo'q — keyin qaytarish o'chirilsa
    # ayiradigan narsa ham yo'q). Uzilmasa PostgreSQL FK o'chirishni bloklaydi.
    db.query(ReturnItem).filter(ReturnItem.finished_product_id == fp_id,
                                ReturnItem.company_id == fp.company_id).update(
        {"finished_product_id": None}, synchronize_session=False)

    db.delete(fp)
    db.commit()
    return True


def add_returned_to_stock(db: Session, order_item, quantity: float, reason: str,
                          order_id: int = None, notes: str = None,
                          commit: bool = True, natija: dict = None) -> Optional[FinishedProduct]:
    """Buyurtmadan qaytgan detalni tayyor mahsulotlar omboriga qo'shadi.
    Sotuv narxi (unit_price) — buyurtmadagi narx (o'zgarmaydi).
    Tan narxi (cost_price) — asl xomashyo qiymatidan hisoblanadi (avval
    bu doim "0" deb yozilardi, shuning uchun bu mahsulot keyinroq YANGI
    buyurtmada ishlatilsa, o'sha buyurtmaning foydasi — demak usta KPI'si
    ham — sun'iy oshirilgan bo'lib chiqardi)."""
    import services as _svc
    from models import ProductionStatus as _PS_ret

    if quantity <= 0 or not order_item:
        return None

    ordered = order_item.order_qty_normalized
    total_price = float(order_item.total_price or 0)
    unit_p = (total_price / ordered) if ordered > 0 else 0.0
    unit = order_item.delivery_unit

    # kech55 (5-bo'lim 34-band): tannarx — shu buyurtmada ISHLATILGAN paytdagi narxda
    # (buyurtma tan narxi bilan bir manba, `_buyurtma_sarf_narxlari`; MRP — surat narxi).
    # O'LCHANGAN (`work/probe56.py`): narx x3 dan keyin 2 m qaytarish 30 000 (joriy)
    # yozardi, mahsulot esa 10 000 ga qilingan — sotuvda foyda 20 000 kam ko'rinardi.
    unit_cost = _svc.get_order_item_unit_cost(db, order_item.order, order_item, muzlatilgan=True)
    new_cost_price = round(unit_cost * quantity, 2)

    # MUHIM: "Xarajatlar" (Foyda hisobi oynasi) — volume_m3'ga tayanib,
    # Penoplast narxini ko'rsatadi. AVVAL bu yerda volume_m3 umuman
    # yozilmasdi — shuning uchun "Tan narxi" to'g'ri ko'rinsa ham,
    # "Xarajatlar → Penoplast" qatori noto'g'ri "0" ko'rsatardi.
    per_unit_volume = 0.0
    if ordered > 0:
        # kech55 (34-band): donaning zaxira hajm yo'li (penoplast narxidan) — ishlatilgan
        # paytdagi narxda (`calculate_order_profit` bilan bir xil).
        _ret_pid = getattr(order_item, 'penoplast_id', None)
        _ret_narx = (_svc._buyurtma_sarf_narxlari(db, order_item.order).get(_ret_pid)
                     if (_ret_pid and getattr(order_item, 'order', None) is not None) else None)
        full_volume = _svc._item_volume_m3(db, order_item, None, penoplast_narxi=_ret_narx)
        per_unit_volume = full_volume / ordered
    new_volume = round(per_unit_volume * quantity, 6)
    # kech40 (22-band): chaqiruvchiga AYNAN nima qo'shilgani (qaytarish yozuvi
    # o'chirilganda shu ayiriladi — tan narxi keyin o'zgarishi mumkin).
    if natija is not None:
        natija.update(qty=float(quantity), cost=new_cost_price, volume=new_volume)

    # Bir xili bo'lsa birlashtiramiz.
    # M4 (2026-09-18) — TENANT: bu "birlashtirish" so'rovi korxona
    # filtrisiz edi — A korxonadan qaytgan detal, nomi/o'lchami/narxi
    # tasodifan bir xil kelsa, B korxonaning qaytgan mahsulotiga
    # qo'shilib ketishi mumkin edi.
    _ret_cid = getattr(getattr(order_item, 'order', None), 'company_id', None)
    _rq = db.query(FinishedProduct).filter(
        FinishedProduct.name == order_item.name,
        FinishedProduct.source == StockSource.RETURNED,
        FinishedProduct.width == order_item.width,
        FinishedProduct.thickness == order_item.thickness,
        FinishedProduct.is_coated == order_item.is_coated,
        FinishedProduct.unit_price == unit_p,
    )
    if _ret_cid is not None:
        _rq = _rq.filter(FinishedProduct.company_id == _ret_cid)
    # QO'SHILDI 2026-09-20 (Bosqich 3, 10-band). Birlashtirish sharti
    # turkumni ham, mahsulot TURINI ham tekshirmasdi — nomi, o'lchami va
    # narxi tasodifan bir xil bo'lgan IKKI XIL TURDAGI mahsulot bitta
    # yozuvga qo'shilib ketishi mumkin edi. Eski yozuvlarda bu ustun
    # NULL, shuning uchun `IS NULL` sharti eski xatti-harakatni
    # AYNAN saqlaydi (SQL da `= NULL` hech qachon mos kelmaydi).
    _ret_pt = getattr(order_item, "product_type_id", None)
    if _ret_pt is None:
        _rq = _rq.filter(FinishedProduct.product_type_id.is_(None))
    else:
        _rq = _rq.filter(FinishedProduct.product_type_id == _ret_pt)
    # kech40 (22-band): qator QULFLANADI — sotuv / kamaytirish / qaytarishni
    # o'chirish ham `FOR UPDATE` bilan o'qiydi; qulfsiz o'qib-yozish parallel
    # sotuvning kamaytirishini ustidan yozib yuborardi (yo'qolgan yangilanish).
    existing = _rq.with_for_update().first()

    if existing:
        # kech59 (47-band): qaytgan qismning muzlagan tannarxi mavjud qoldiq bilan og'irlikli o'rtacha
        # (qaytarish o'chirilsa `delete_return_item` teskarisini qiladi). Qoldiq QO'SHISHDAN OLDIN o'qiladi.
        _eski_q59 = float(existing.quantity or 0)
        _eski_b59 = _fp_stable_unit_cost(db, existing)
        if _eski_b59 <= 0 and _eski_q59 > 0 and existing.cost_price:
            _eski_b59 = float(existing.cost_price) / _eski_q59
        if _eski_q59 + quantity > 0:
            existing.unit_cost_stable = (_eski_b59 * _eski_q59 + new_cost_price) / (_eski_q59 + quantity)
        existing.quantity = float(existing.quantity or 0) + quantity
        existing.produced_quantity = float(existing.produced_quantity or 0) + quantity
        existing.cost_price = float(existing.cost_price or 0) + new_cost_price
        existing.volume_m3 = float(existing.volume_m3 or 0) + new_volume
        # Agar mavjud yozuvda hali rasm bo'lmasa — asl detal rasmini olamiz
        if not existing.image_url and order_item.image_url:
            existing.image_url = order_item.image_url
        if commit:
            db.commit()
        else:
            db.flush()
        db.refresh(existing)
        return existing

    fp = FinishedProduct(
        company_id=_ret_cid,            # M4: tenant ANIQ beriladi
        name=order_item.name,
        category=order_item.category,
        width=order_item.width,
        thickness=order_item.thickness,
        is_coated=order_item.is_coated,
        quantity=quantity,
        produced_quantity=quantity,
        unit=unit,
        unit_price=unit_p,
        cost_price=new_cost_price,
        # kech59 (47-band): qaytgan mahsulotning 1 birlik tannarxi — buyurtmada ISHLATILGAN paytdagi
        # narx (34-band) muzlaydi; aks holda buyurtmaga olinganda / foyda hisobida
        # `cost_price / produced_quantity` qoldiq kamaygan sari siljirdi (K59-1).
        unit_cost_stable=(new_cost_price / quantity) if (quantity > 0 and new_cost_price > 0) else None,
        volume_m3=new_volume,
        source=StockSource.RETURNED,
        from_order_id=order_id or order_item.order_id,
        return_reason=reason,
        penoplast_id=order_item.penoplast_id,
        # QO'SHILDI 2026-09-20 (Bosqich 3, 10-band). MRP mahsuloti
        # (`category='mrp_product'`) buyurtmadan qaytarilganda, turi
        # yo'qolmasin. Eski turkumlarda bu maydon NULL — bu ATAYLAB.
        product_type_id=getattr(order_item, "product_type_id", None),
        image_url=order_item.image_url,
        notes=notes,
        # kech40 (K40-1): qaytgan mahsulot DOIM tayyor (sotiladi) — holat aniq
        # yoziladi (ilgari bazada standart IN_PROGRESS qolardi; eski qatorlar
        # `main._migrate_qaytarish_orqaga` da tuzatiladi).
        production_status=_PS_ret.READY,
    )
    db.add(fp)
    if commit:
        db.commit()
    else:
        db.flush()
    db.refresh(fp)
    return fp


def search_finished_products(db: Session, query: str, category: str = None, exclude_category: str = None,
                            company_id: int = None) -> List[dict]:
    """Nom bo'yicha tayyor mahsulot qidirish — buyurtmada taklif uchun.
    category — agar berilsa, FAQAT shu turdagi mahsulotlar qaytariladi.
    exclude_category — aksincha, shu turdagi mahsulotlar RO'YXATDAN
    CHIQARIB TASHLANADI."""
    q = (query or '').strip()
    if len(q) < 2:
        return []

    filters = [
        FinishedProduct.quantity > 0,
        FinishedProduct.name.ilike(f"%{q}%")
    ]
    # M4 (2026-09-18) — TENANT: auditda `?q=ZZZB` B korxonaning
    # mahsulotini topib berardi (H-4).
    if company_id is not None:
        filters.append(FinishedProduct.company_id == company_id)
    if category:
        filters.append(FinishedProduct.category == category)
    elif exclude_category:
        filters.append(FinishedProduct.category != exclude_category)

    # kech35 (15-band, jonli O'LCHANGAN kech28): nomi bir xil mahsulotlar orasida
    # tartib aniqlanmagan edi (PG da UPDATE dan keyin o'rin almashardi) —
    # `id` uchinchi (qidiruvda ikkinchi) kalit: tartib doim barqaror.
    items = db.query(FinishedProduct).filter(*filters).order_by(FinishedProduct.name, FinishedProduct.id).limit(10).all()

    result = []
    for fp in items:
        try:
            src = fp.source.value if fp.source else "produced"
            result.append({
                "id": fp.id,
                "name": fp.name,
                "category": fp.category,
                "product_type_id": fp.product_type_id,   # Bosqich 3, 10-band
                "width": fp.width,
                "thickness": fp.thickness,
                "is_coated": fp.is_coated,
                "quantity": float(fp.quantity or 0),
                "unit": fp.unit,
                "unit_price": float(fp.unit_price or 0),
                "source": src,
                "source_label": "♻️ Qaytgan" if src == "returned" else "🏭 Tayyor",
                "notes": fp.notes,
            })
        except Exception as e:
            # Bitta yozuvda muammo bo'lsa ham — QIDIRUVNING BARCHASI 500
            # xato bilan yiqilib ketmasin, shu yozuvni o'tkazib yuboramiz.
            try:
                log_error(db, f"search_finished_products: FP#{fp.id} o'tkazib yuborildi — {e}",
                          endpoint="search_finished_products")
            except Exception:
                pass
            continue

    return result




def get_finished_stats(db: Session, company_id: int = None) -> dict:
    """Tayyor mahsulotlar statistikasi.

    M4 (2026-09-18) — TENANT: auditda `produced_count` ichiga B
    korxonaning mahsuloti ham sanalardi (H-3)."""
    from models import ProductionStatus

    _sq = db.query(FinishedProduct).filter(FinishedProduct.quantity > 0)
    if company_id is not None:
        _sq = _sq.filter(FinishedProduct.company_id == company_id)
    items = _sq.all()

    produced = [i for i in items if i.source == StockSource.PRODUCED]
    returned = [i for i in items if i.source == StockSource.RETURNED]
    in_progress = [i for i in produced if i.production_status == ProductionStatus.IN_PROGRESS]

    def _val(lst):
        return sum(float(i.quantity or 0) * float(i.unit_price or 0) for i in lst)

    return {
        "produced_count": len(produced),
        "returned_count": len(returned),
        "in_progress_count": len(in_progress),
        "produced_value": round(_val(produced)),
        "returned_value": round(_val(returned)),
        "total_value": round(_val(items)),
    }


class _TermoFakeOrder:
    """Termopanel '+' qo'shishda loy ayirish uchun soxta buyurtma obyekti."""
    def __init__(self, recipe_id, company_id=None):
        class _It:
            pass
        _it = _It()
        _it.recipe_id = recipe_id
        self.items = [_it]
        self.id = None
        # 2026-09-21 — TENANT: `services.resolve_recipe` korxonani
        # buyurtma obyektidan ham oladi, shuning uchun SHART.
        self.company_id = company_id
        self.order_number = "TERMOPANEL +"
        self.deliveries = []
        self.is_fully_delivered = False


def add_to_production(db: Session, fp_id: int, add_qty: float, performed_by: str = None,
                     company_id: int = None) -> dict:
    """Mavjud tayyor mahsulotga miqdor qo'shadi.
    Penoplast va loy proporsional hisoblanib ombordan yechiladi.

    Masalan: 100 m uchun 1.2 m³ penoplast va 120 kg loy ketgan bo'lsa,
             +50 m qo'shilsa → 0.6 m³ penoplast va 60 kg loy yechiladi.
    """
    import services

    # 17-band: miqdor QAT'IY (NaN / cheksizlik / manfiy / juda katta).
    try:
        _json_son("quantity", add_qty, bosh_mumkin=False, musbat=True, chegara=_UPD_SON_CHEGARA)
    except ValueError as _e:
        return {"success": False, "message": str(_e)}
    fp = get_finished_product(db, fp_id, company_id)   # M4: faqat shu korxonadan
    if not fp:
        return {"success": False, "message": "Topilmadi"}

    # M4: "+" qo'shishda ayiriladigan xomashyo ham faqat SHU korxonadan.
    _add_cid = company_id if company_id is not None else getattr(fp, 'company_id', None)

    def _add_inv(_q):
        return _q.filter(Inventory.company_id == _add_cid) if _add_cid is not None else _q

    if add_qty <= 0:
        return {"success": False, "message": "Miqdor musbat bo'lishi kerak"}

    if fp.source != StockSource.PRODUCED:
        return {"success": False, "message": "Faqat ishlab chiqarilgan mahsulotga qo'shiladi"}

    # kech61 (K61-1) — O'LCHANGAN (`work/probe61.py`, asl `5e736a8`, SQLite + PG): MRP (Ishlab
    # chiqarish moduli) mahsulotida `unit_volume_m3` / `unit_loy_kg` / `volume_m3` bo'sh — "+" 1 birlik
    # xomashyoni 0 deb olib, 10 m² ni HECH NARSA yechmasdan qo'shdi (tannarx 30 000 da qoldi, 1 birlik
    # 3 000 -> 1 500). MRP mahsuloti retsept (BOM) bo'yicha FAQAT ishlab chiqarish buyurtmasi orqali
    # ko'paytiriladi — u yerda xomashyo yechiladi va tannarx muzlaydi.
    if fp.category == "dynamic_bom" or getattr(fp, "product_type_id", None) is not None:
        return {"success": False,
                "message": "Bu mahsulot «Ishlab chiqarish» bo'limida retsept bo'yicha tayyorlanadi — "
                           "qo'shimcha partiyani o'sha yerda yarating (xomashyo retsept bo'yicha yechiladi)"}

    base_qty = float(fp.quantity or 0)
    # kech59 (47-band): qo'shishdan OLDINGI 1 birlik tannarxi (og'irlikli o'rtacha uchun)
    _eski_birlik59 = _fp_stable_unit_cost(db, fp)
    if _eski_birlik59 <= 0 and base_qty > 0 and fp.cost_price:
        _eski_birlik59 = float(fp.cost_price) / base_qty

    # MUHIM: Profil uchun — "quantity" odatda 1 (bitta buyum), lekin HAJM
    # aslida UZUNLIK (metr) bo'yicha hisoblangan. Shuning uchun "1 birlikka
    # hajm"ni quantity=1 ga bo'lsak — butun hajm 1 birlikка tegishli deb
    # xato hisoblanardi (keyin "+" qo'shganda 100 barobar shishardi).
    # To'g'risi: Profil uchun "birlik" = 1 METR, shuning uchun hajmni
    # haqiqiy metr soniga bo'lish kerak. Bu metr — unit_volume_m3 saqlangan
    # bo'lsa undan aniq keladi; aks holda pastdagi fallback ishlaydi.
    # MUHIM: 1 birlikka qancha xomashyo ketishini — JORIY qoldiq/hajmdan
    # EMAS, balki ishlab chiqarilganda saqlangan BARQAROR nisbatdan
    # olamiz. Sababi: mahsulot sotilganda faqat "quantity" kamayadi,
    # "volume_m3" o'zgarmay qoladi — shuning uchun joriy nisbat vaqt
    # o'tishi bilan (ayniqsa qoldiq 0'ga yaqinlashganda yoki 0 bo'lganda)
    # noto'g'ri bo'lib qolar edi. Eski (bu tuzatishdan oldingi) yozuvlarda
    # bu maydon bo'lmasa — orqaga moslik uchun joriy nisbatga qaytamiz.
    if fp.unit_volume_m3 is not None or fp.unit_loy_kg is not None:
        unit_volume = float(fp.unit_volume_m3 or 0)
        unit_loy = float(fp.unit_loy_kg or 0)
    elif base_qty > 0:
        # kech61 (K61-3) — O'LCHANGAN: `volume_m3` / `actual_loy_kg` sotuvda KAMAYMAYDI (jami), shuning
        # uchun ular JAMI ishlab chiqarilgan miqdorga bo'linadi. Qoldiqqa bo'linsa 100 m dan 80 m sotilgach
        # "+10" 0.1 blok o'rniga 0.5 blok yechardi (5 barobar). `produced_quantity` bo'sh bo'lsa — qoldiq.
        _jami_q61 = float(fp.produced_quantity or 0)
        _bol61 = _jami_q61 if _jami_q61 > 0 else base_qty
        unit_volume = float(fp.volume_m3 or 0) / _bol61
        unit_loy = float(fp.actual_loy_kg or 0) / _bol61
    else:
        return {
            "success": False,
            "message": "Bu eski yozuv — 1 birlikka qancha xomashyo ketishi noma'lum (qoldiq ham 0). "
                       "Yangi ishlab chiqarish yarating."
        }

    add_volume = unit_volume * add_qty
    add_loy = unit_loy * add_qty

    # kech61 (K61-1): hech qanday xomashyo yechilmasa "+" bepul mahsulot yaratadi (tannarx o'zgarmaydi,
    # 1 birlik tannarxi pasayadi) — rad etiladi.
    if add_volume <= 0 and add_loy <= 0:
        return {"success": False,
                "message": "Bu mahsulotning 1 birligiga qancha xomashyo ketishi noma'lum — "
                           "\"+\" xomashyosiz miqdor qo'sha olmaydi. Yangi ishlab chiqarish yarating."}

    # Xomashyo yetadimi
    shortages = []
    if add_volume > 0 and fp.penoplast_id:
        p = _add_inv(db.query(Inventory).filter(Inventory.id == fp.penoplast_id)).first()
        if p:
            vol_per_unit = float(p.volume_per_unit or 1.0)
            blocks = add_volume / vol_per_unit
            if float(p.stock_quantity) < blocks:
                shortages.append(
                    f"{p.item_name}: kerak {blocks:.2f} blok, qoldi {float(p.stock_quantity):.2f} blok"
                )
    if shortages:
        return {"success": False, "message": "Xomashyo yetishmayapti!", "shortages": shortages}

    log = []
    peno_cost = 0.0
    loy_cost = 0.0

    # 1) Penoplast
    if add_volume > 0 and fp.penoplast_id:
        p = _add_inv(db.query(Inventory).filter(Inventory.id == fp.penoplast_id)).with_for_update().first()
        if p:
            vol_per_unit = float(p.volume_per_unit or 1.0)
            blocks = add_volume / vol_per_unit
            # 20-band (2026-09-21): 0 ga QIRQILMAYDI (yetishmovchilik yuqorida
            # rad etiladi) va sarf ombor JURNALIGA yoziladi — ilgari "+"
            # qo'shishdagi penoplast sarfi "Harakatlar tarixi"da ko'rinmasdi
            # (`produce` va brak yo'llari esa yozardi).
            p.stock_quantity = float(p.stock_quantity) - blocks
            peno_cost = blocks * float(p.price_per_unit or 0)
            log.append(f"{p.item_name}: -{blocks:.2f} blok")
            log_movement(
                db, p.id, p.item_name, movement_type="out", quantity=blocks,
                unit=p.unit,
                reason=_jurnal_sabab(f"Ishlab chiqarish (+{add_qty:g}): {fp.name}")
            )

    # 2) Loy
    if add_loy > 0:
        # 2026-09-21 — TENANT. Penoplast qismi yuqorida `_add_inv` bilan
        # korxonaga bog'langan edi, LOY qismi esa bog'lanmagan: retsept
        # global qidirilar, ingredientlar esa retseptning ichidan
        # (`ing.inventory_id`) olinar — ya'ni `_add_inv` ni butunlay
        # chetlab o'tib, BOSHQA korxonaning omboridan ayirilar edi.
        # O'lchangan: B ning "+10 metr" amali A ning SEMENT qoldig'ini
        # 1000 → 995 kg qildi.
        recipe = services.resolve_recipe(db, recipe_id=fp.recipe_id,
                                         company_id=_add_cid)

        loy_info = services.get_loy_cost_per_kg(
            db, recipe.id if recipe else None, company_id=_add_cid)
        loy_cost = add_loy * float(loy_info.get("cost_per_kg", 0))

        class _FakeOrder:
            def __init__(self, rid, cid):
                class _It:
                    recipe_id = rid
                self.items = [_It()]
                self.id = None
                self.company_id = cid      # 2026-09-21 — TENANT
                self.order_number = "ISHLAB CHIQARISH"
        fake = _FakeOrder(recipe.id if recipe else None, _add_cid)
        log.extend(services.deduct_loy_ingredients(
            db, fake, add_loy, use_stock=False, company_id=_add_cid,
            reason_override=f"Ishlab chiqarish: {fp.name} (+{add_qty:g} {fp.unit}, loy)"
        ))

    # 3) Mahsulotni yangilaymiz
    fp.quantity = base_qty + add_qty
    # MUHIM: hodim oyligi (Qoplamachi bonusi va h.k.) — "quantity"dan EMAS,
    # "produced_quantity"dan hisoblanadi (chunki quantity sotuv/brak bilan
    # kamayadi, produced_quantity esa "hodim haqiqatan qancha ishlab
    # chiqargani"ni ko'rsatishi kerak). AVVAL bu yerda produced_quantity'ga
    # tegilmasdi — shuning uchun "+" orqali qo'shilgan miqdor hodim
    # oyligiga HECH QACHON qo'shilmasdi.
    base_produced = float(fp.produced_quantity if fp.produced_quantity is not None else base_qty)
    fp.produced_quantity = base_produced + add_qty
    fp.volume_m3 = float(fp.volume_m3 or 0) + add_volume
    fp.actual_loy_kg = float(fp.actual_loy_kg or 0) + add_loy
    fp.planned_loy_kg = float(fp.planned_loy_kg or 0) + add_loy
    fp.cost_price = float(fp.cost_price or 0) + peno_cost + loy_cost
    # kech59 (47-band): yangi partiya SHU paytdagi narxda — qoldiq bilan og'irlikli o'rtacha
    # (omborda turgan eski qism eski narxda qoladi, butun mahsulot joriy narxga o'tmaydi).
    _jami_qty59 = base_qty + add_qty
    if _jami_qty59 > 0:
        fp.unit_cost_stable = (_eski_birlik59 * base_qty + peno_cost + loy_cost) / _jami_qty59

    db.commit()
    db.refresh(fp)

    try:
        log_activity(db, "produced", "finished_product", fp.id, fp.name, performed_by,
                      new_value=f"+{add_qty:g} {fp.unit} qo'shildi, jami: {float(fp.quantity):g} {fp.unit}",
                      company_id=getattr(fp, 'company_id', None))
    except Exception:
        pass

    return {
        "success": True,
        "message": f"+{add_qty:g} {fp.unit} qo'shildi",
        "product_id": fp.id,
        "name": fp.name,
        "added_qty": add_qty,
        "new_qty": float(fp.quantity),
        "unit": fp.unit,
        "add_volume": round(add_volume, 4),
        "add_loy": round(add_loy, 1),
        "add_cost": round(peno_cost + loy_cost),
        "inventory_log": log
    }


def reduce_production(db: Session, fp_id: int, reduce_qty: float, reason: str = None,
                     company_id: int = None) -> dict:
    """Tayyor mahsulot miqdorini kamaytiradi (brak/singan).
    Xomashyo omborga QAYTARILMAYDI — tan narxi saqlanadi."""
    # 17-band: qiymatlar QAT'IY (NaN / cheksizlik / manfiy / juda katta).
    try:
        _clean_val("StockAdjust", {"quantity": reduce_qty, "reason": reason})
    except ValueError as _e:
        return {"success": False, "message": str(_e)}
    fp = get_finished_product(db, fp_id, company_id)   # M4: faqat shu korxonadan
    if not fp:
        return {"success": False, "message": "Topilmadi"}
    if not _fp_tayyormi(fp):
        return {"success": False, "message": _FP_JARAYONDA_XABAR}

    if reduce_qty <= 0:
        return {"success": False, "message": "Miqdor musbat bo'lishi kerak"}

    current = float(fp.quantity or 0)
    if reduce_qty > current + 0.001:
        return {
            "success": False,
            "message": f"Omborda {current:g} {fp.unit} bor, {reduce_qty:g} ayirib bo'lmaydi"
        }

    fp.quantity = max(0, current - reduce_qty)

    # Izohga yozib qo'yamiz
    note = f"brak: -{reduce_qty:g}{fp.unit}"
    if reason:
        note += f" ({reason})"
    fp.notes = (fp.notes + " · " + note) if fp.notes else note

    db.commit()
    db.refresh(fp)

    # Yo'qotilgan qiymat
    lost_value = reduce_qty * float(fp.unit_price or 0)

    return {
        "success": True,
        "message": f"-{reduce_qty:g} {fp.unit} chiqarildi (brak)",
        "product_id": fp.id,
        "name": fp.name,
        "new_qty": float(fp.quantity),
        "unit": fp.unit,
        "lost_value": round(lost_value)
    }


def get_finished_profit(db: Session, fp_id: int, company_id: int = None) -> dict:
    """Tayyor mahsulot foydasi — to'liq tafsilot bilan.

    M4 (2026-09-18) — TENANT: auditda aynan shu funksiya orqali
    (`GET /api/finished/41/profit`) B korxonaning to'liq tannarx va
    foyda ma'lumoti chiqib ketgan edi (CR-1)."""
    import services

    fp = get_finished_product(db, fp_id, company_id)
    if not fp:
        return {"success": False, "message": "Topilmadi"}

    # M4: tannarx tafsilotidagi material qidiruvlari ham shu korxonadan.
    _pf_cid = getattr(fp, 'company_id', None)

    def _pf_inv(_q):
        return _q.filter(Inventory.company_id == _pf_cid) if _pf_cid is not None else _q

    qty = float(fp.quantity or 0)
    unit_price = float(fp.unit_price or 0)
    revenue = qty * unit_price
    total_cost = float(fp.cost_price or 0)

    # kech61 (46-band) — O'LCHANGAN (`work/probe61.py`): `volume_m3` / `actual_loy_kg` JAMI ishlab
    # chiqarilgan (qaytgan) miqdorniki — sotuv / buyurtmaga olish / kamaytirishda kamaymaydi, `cost_price`
    # esa kamayadi. 100 m dan 60 m sotilgach oyna "Penoplast 500 000 + Loy 260 000" va "Tan narxi 304 000"
    # ko'rsatardi. Xarajat qatorlari endi QOLDIQ ulushi bilan (qoldiq / jami ishlab chiqarilgan).
    _jami_q46 = float(fp.produced_quantity or 0)
    _ulush46 = min(1.0, qty / _jami_q46) if _jami_q46 > 0 else 1.0
    jami_volume = float(fp.volume_m3 or 0)
    jami_loy = float(fp.actual_loy_kg or 0)
    qoldiq_volume = jami_volume * _ulush46

    # Loy narxi
    loy_cost = 0.0
    loy_per_kg = 0.0
    recipe_name = None
    loy_kg = jami_loy * _ulush46
    if loy_kg > 0:
        # 2026-09-21 — TENANT: korxona aniq beriladi. Oldin berilmagani
        # uchun, `fp.recipe_id` bo'sh mahsulotning foyda hisobotida
        # BOSHQA korxonaning retsept NOMI va narxi chiqardi (o'lchangan).
        info = services.get_loy_cost_per_kg(
            db, fp.recipe_id,
            company_id=company_id if company_id is not None
            else getattr(fp, 'company_id', None))
        loy_per_kg = float(info.get("cost_per_kg", 0))
        loy_cost = loy_kg * loy_per_kg
        recipe_name = info.get("recipe")

    # Penoplast narxi — TO'G'RIDAN-TO'G'RI, saqlangan haqiqiy hajm
    # (fp.volume_m3) va joriy Penoplast narxidan hisoblanadi. AVVAL bu
    # "umumiy tan narxidan Loy narxini ayirib" (max(total_cost-loy_cost,0))
    # hisoblanardi — bu, agar Loy narxi (joriy narxlarda) mahsulot birinchi
    # marta tayyorlangandagi umumiy tan narxidan OSHIB ketsa (masalan
    # xomashyo narxlari vaqt o'tishi bilan ko'tarilgan bo'lsa), manfiy
    # chiqib, "Penoplast: 0 so'm" deb noto'g'ri ko'rsatilardi.
    peno_cost = 0.0
    if fp.penoplast_id and qoldiq_volume > 0:
        peno_inv = _pf_inv(db.query(Inventory).filter(Inventory.id == fp.penoplast_id)).first()
        if peno_inv and peno_inv.volume_per_unit and peno_inv.price_per_unit:
            price_per_m3 = float(peno_inv.price_per_unit) / float(peno_inv.volume_per_unit)
            peno_cost = qoldiq_volume * price_per_m3

    profit = revenue - total_cost
    margin = (profit / revenue * 100) if revenue > 0 else 0

    return {
        "success": True,
        "id": fp.id,
        "name": fp.name,
        "quantity": qty,
        "unit": fp.unit,
        "unit_price": unit_price,
        "revenue": round(revenue),
        "penoplast_cost": round(peno_cost),
        "loy_kg": loy_kg,
        "loy_cost_per_kg": round(loy_per_kg),
        "loy_cost": round(loy_cost),
        "recipe": recipe_name,
        "total_cost": round(total_cost),
        "profit": round(profit),
        "margin": round(margin, 1),
        "cost_per_unit": round(total_cost / qty) if qty > 0 else 0,
        "profit_per_unit": round(profit / qty) if qty > 0 else 0,
        # kech61 (46-band): qoldiq uchun (xarajat qatorlari bilan bir xil); jami — tarix uchun.
        "volume_m3": round(qoldiq_volume, 6),
        "jami_volume_m3": jami_volume,
        "jami_loy_kg": jami_loy,
        "source": fp.source.value,
        "production_status": fp.production_status.value if fp.production_status else None,
    }


# ============================================================
# INVENTORY PURCHASES — Xarid statistikasi
# ============================================================

def get_purchases(db: Session, limit: int = 100, item_id: int = None,
                  company_id: int = None) -> List:
    """Xaridlar tarixi.

    M3: InventoryPurchase'da company_id ustuni YO'Q — filtrlash ota
    (material) orqali, JOIN bilan."""
    from models import InventoryPurchase
    q = db.query(InventoryPurchase)
    if company_id is not None:
        q = q.join(Inventory, Inventory.id == InventoryPurchase.inventory_id).filter(
            Inventory.company_id == company_id)
    if item_id:
        q = q.filter(InventoryPurchase.inventory_id == item_id)
    return q.order_by(InventoryPurchase.purchased_at.desc()).limit(limit).all()


def get_purchase_stats(db: Session, year: int = None, month: int = None,
                       company_id: int = None) -> dict:
    """Material bo'yicha xarid statistikasi — Moliya/Dashboard uchun.
    year/month berilmasa — joriy oy."""
    from models import InventoryPurchase
    from datetime import datetime as dt

    now = dt.utcnow()
    year = year or now.year
    month = month or now.month

    start = dt(year, month, 1)
    end = dt(year + 1, 1, 1) if month == 12 else dt(year, month + 1, 1)

    _pq = db.query(InventoryPurchase)
    if company_id is not None:
        _pq = _pq.join(Inventory, Inventory.id == InventoryPurchase.inventory_id).filter(
            Inventory.company_id == company_id)
    purchases = _pq.filter(
        InventoryPurchase.purchased_at >= start,
        InventoryPurchase.purchased_at < end,
        InventoryPurchase.is_opening_stock.isnot(True)
    ).all()

    by_material = {}
    total = 0.0
    for p in purchases:
        key = p.item_name
        if key not in by_material:
            by_material[key] = {"name": key, "quantity": 0.0, "total": 0.0, "unit": p.unit, "category": p.category or "Boshqa"}
        by_material[key]["quantity"] += float(p.quantity)
        by_material[key]["total"] += float(p.total_amount)
        total += float(p.total_amount)

    items = sorted(by_material.values(), key=lambda x: x["total"], reverse=True)
    for it in items:
        it["avg_price"] = round(it["total"] / it["quantity"]) if it["quantity"] > 0 else 0
        it["total"] = round(it["total"])

    return {
        "year": year,
        "month": month,
        "total_amount": round(total),
        "purchase_count": len(purchases),
        "by_material": items
    }


def get_purchase_stats_range(db: Session, months: int = 6, company_id: int = None) -> dict:
    """Oxirgi N oy bo'yicha xarid tendensiyasi (dashboard grafik uchun)."""
    from models import InventoryPurchase
    from datetime import datetime as dt

    now = dt.utcnow()
    result = []
    y, m = now.year, now.month
    for _ in range(months):
        start = dt(y, m, 1)
        end = dt(y + 1, 1, 1) if m == 12 else dt(y, m + 1, 1)
        _prq = db.query(InventoryPurchase).filter(
            InventoryPurchase.purchased_at >= start,
            InventoryPurchase.purchased_at < end,
            InventoryPurchase.is_opening_stock.isnot(True)
        )
        if company_id is not None:      # M6: ota (material) orqali
            _prq = _prq.join(Inventory, Inventory.id == InventoryPurchase.inventory_id).filter(
                Inventory.company_id == company_id)
        total = _prq.all()
        s = sum(float(p.total_amount) for p in total)
        result.append({"year": y, "month": m, "total": round(s)})
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return {"months": list(reversed(result))}


# ============================================================
# TRANSPORT EXPENSE — Kirish transporti
# ============================================================

from models import TransportExpense
from schemas import TransportExpenseCreate


def create_transport_expense(db: Session, data: TransportExpenseCreate, created_by: str = None,
                            company_id: int = None) -> TransportExpense:
    """Kirish transporti xarajatini yozadi."""
    # 17f (2026-09-22): ILDIZ — tana QAT'IY (summa musbat, chekli, sig'im
    # ichida va kamida 1 tiyin; `materials_note` ≤ 255; `production_type`
    # ro'yxatdan), bazaga tegishdan OLDIN. Marshrut ham tekshiradi; bu qatlam
    # ichki chaqiruvchi (xarid marshrutidagi "o'z hisobimdan" transport) va
    # boshqa chaqiruvchilar uchun. `data` — lug'at, pydantic yoki oddiy obyekt.
    toza = _clean_val("TransportExpense", _val_dump(data, "TransportExpense"))
    # M6 — TENANT: company_id ANIQ beriladi.
    exp = TransportExpense(
        company_id=company_id,
        amount=toza["amount"],
        materials_note=toza.get("materials_note"),
        created_by=created_by,
        notes=toza.get("notes"),
        production_type=toza.get("production_type")
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def get_transport_expenses(db: Session, limit: int = 100,
                          company_id: int = None) -> List[TransportExpense]:
    q = db.query(TransportExpense)
    if company_id is not None:      # M6
        q = q.filter(TransportExpense.company_id == company_id)
    return q.order_by(TransportExpense.expense_date.desc()).limit(limit).all()


def delete_transport_expense(db: Session, exp_id: int, company_id: int = None) -> bool:
    _q = db.query(TransportExpense).filter(TransportExpense.id == exp_id)
    if company_id is not None:      # M6: faqat shu korxonadan
        _q = _q.filter(TransportExpense.company_id == company_id)
    exp = _q.first()
    if not exp:
        return False
    db.delete(exp)
    db.commit()
    return True


def get_transport_stats(db: Session, year: int = None, month: int = None,
                       company_id: int = None) -> dict:
    """Transport xarajatlari statistikasi (kirish + chiqish) — joriy oy bo'yicha.

    M6 — TENANT: kirish transporti `TransportExpense.company_id` bo'yicha,
    chiqish transporti esa ota (Delivery → Order) orqali cheklanadi."""
    from models import Delivery, Order as _Ord_ts
    from datetime import datetime as dt

    now = dt.utcnow()
    year = year or now.year
    month = month or now.month
    start = dt(year, month, 1)
    end = dt(year + 1, 1, 1) if month == 12 else dt(year, month + 1, 1)

    # Kirish transporti
    _iq = db.query(TransportExpense).filter(
        TransportExpense.expense_date >= start,
        TransportExpense.expense_date < end
    )
    if company_id is not None:
        _iq = _iq.filter(TransportExpense.company_id == company_id)
    inbound = _iq.all()
    inbound_total = sum(float(e.amount) for e in inbound)

    # Chiqish transporti (kompaniya ulushi)
    _dq = db.query(Delivery).filter(
        Delivery.delivered_at >= start,
        Delivery.delivered_at < end,
        Delivery.transport_cost > 0
    )
    if company_id is not None:
        _dq = _dq.join(_Ord_ts, _Ord_ts.id == Delivery.order_id).filter(
            _Ord_ts.company_id == company_id)
    deliveries = _dq.all()
    outbound_company = sum(d.company_transport_cost for d in deliveries)
    outbound_client = sum(d.client_transport_cost for d in deliveries)
    outbound_total = sum(float(d.transport_cost or 0) for d in deliveries)

    return {
        "year": year,
        "month": month,
        "inbound_total": round(inbound_total),
        "inbound_count": len(inbound),
        "outbound_total": round(outbound_total),
        "outbound_company": round(outbound_company),
        "outbound_client": round(outbound_client),
        "outbound_count": len(deliveries),
        "grand_total_company": round(inbound_total + outbound_company)
    }


# ============================================================
# EMPLOYEE — Moslashuvchan hodim to'lovi
# ============================================================

from models import Employee, PayType
from schemas import EmployeeCreate, EmployeeUpdate


def create_employee(db: Session, data: EmployeeCreate, company_id: int = None) -> Employee:
    """Yangi xodim qo'shadi.

    2026-09-18 — M8/F1: `company_id` ANIQ beriladi (ilgari endpoint uni
    keyin qo'yardi, funksiya ichidagi commit esa `DEFAULT 1` ga tayanardi)."""
    from models import EmployeeCompensationHistory
    # 15-band: qat'iy tekshiruv — HECH NARSA yozilmasdan OLDIN (ValueError → 400).
    # O'LCHANGAN: ilgari noto'g'ri `pay_type` JIMGINA "fixed" ga aylanardi
    # (200), `per_unit_type` / `production_type` ixtiyoriy matn yozilardi.
    # Tanlov maydonlari tozalangan (kanonik) qiymatdan olinadi.
    toza = _clean_create("Employee", data.model_dump(exclude_unset=True))
    pt = PayType(toza["pay_type"])

    emp = Employee(
        company_id=company_id,
        name=data.name.strip(),
        position=data.position,
        pay_type=pt,
        fixed_amount=data.fixed_amount,
        percent_value=data.percent_value,
        per_unit_rate=data.per_unit_rate,
        per_unit_type=toza.get("per_unit_type", data.per_unit_type),
        extra_monthly=getattr(data, 'extra_monthly', None),
        production_type=toza.get("production_type"),
        notes=data.notes
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)

    # Boshlang'ich to'lov tarixi yozuvi — ishga kirgan oyidan boshlab
    hire = emp.hire_date or datetime.utcnow()
    db.add(EmployeeCompensationHistory(
        employee_id=emp.id,
        effective_year=hire.year, effective_month=hire.month,
        pay_type=emp.pay_type, fixed_amount=emp.fixed_amount,
        percent_value=emp.percent_value, per_unit_rate=emp.per_unit_rate,
        per_unit_type=emp.per_unit_type,
        extra_monthly=emp.extra_monthly, reason="Ishga kirgan — boshlang'ich"
    ))
    db.commit()
    return emp


def get_employees(db: Session, only_active: bool = True,
                  company_id: int = None) -> List[Employee]:
    """2026-09-18 — M1: company_id berilsa, faqat o'sha korxona xodimlari."""
    q = db.query(Employee).filter(Employee.is_deleted.isnot(True))
    if company_id is not None:
        q = q.filter(Employee.company_id == company_id)
    if only_active:
        q = q.filter(Employee.is_active == True)
    return q.order_by(Employee.name).all()


def get_employee_monthly_adjustment(db: Session, employee_id: int, year: int, month: int):
    """Hodim uchun, shu oy uchun saqlangan qo'lda kamaytirishni qaytaradi (yo'q bo'lsa None)."""
    from models import EmployeeMonthlyAdjustment
    return db.query(EmployeeMonthlyAdjustment).filter(
        EmployeeMonthlyAdjustment.employee_id == employee_id,
        EmployeeMonthlyAdjustment.year == year,
        EmployeeMonthlyAdjustment.month == month
    ).first()


def set_employee_monthly_adjustment(db: Session, employee_id: int, year: int, month: int,
                                      reduction_amount: float = None, reason: str = None,
                                      bonus_amount: float = None, bonus_reason: str = None,
                                      created_by: str = None):
    """Hodim uchun, shu oy uchun qo'lda kamaytirish VA/YOKI bonusni yozadi/yangilaydi.
    Faqat berilgan (None bo'lmagan) qiymatlar yangilanadi — ikkinchisiga tegilmaydi.
    Ikkalasi ham 0/bo'sh bo'lsa — yozuv butunlay o'chiriladi (endi kerak emas)."""
    from models import EmployeeMonthlyAdjustment

    # 17c (2026-09-21): ILDIZ tekshiruvi — yil/oy oralig'i, summalar chekli
    # va manfiy emas (manfiy ilgari mavjud yozuvni JIMGINA o'chirardi).
    toza = _clean_oylik_tuzatish(year, month, reduction_amount, reason,
                                 bonus_amount, bonus_reason)
    year, month = toza["year"], toza["month"]
    reduction_amount, reason = toza["reduction_amount"], toza["reason"]
    bonus_amount, bonus_reason = toza["bonus_amount"], toza["bonus_reason"]

    existing = get_employee_monthly_adjustment(db, employee_id, year, month)

    new_reduction = float(reduction_amount) if reduction_amount is not None else float(existing.reduction_amount or 0) if existing else 0
    new_bonus = float(bonus_amount) if bonus_amount is not None else float(existing.bonus_amount or 0) if existing else 0

    if new_reduction <= 0 and new_bonus <= 0:
        if existing:
            db.delete(existing)
            db.commit()
        return None

    if existing:
        if reduction_amount is not None:
            existing.reduction_amount = new_reduction
            existing.reason = reason
        if bonus_amount is not None:
            existing.bonus_amount = new_bonus
            existing.bonus_reason = bonus_reason
        existing.created_by = created_by
    else:
        existing = EmployeeMonthlyAdjustment(
            employee_id=employee_id, year=year, month=month,
            reduction_amount=new_reduction, reason=reason,
            bonus_amount=new_bonus, bonus_reason=bonus_reason,
            created_by=created_by
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def create_employee_advance(db: Session, employee_id: int, amount: float, notes: str = None,
                              given_by: str = None, adv_date=None):
    """Hodimga avans (oldindan pul) berilganini qayd etadi.
    adv_date — agar berilsa, aynan shu sana bilan yoziladi (masalan
    avans kechroq kiritilgan, lekin haqiqatda boshqa kunda berilgan bo'lsa)."""
    from models import EmployeeAdvance

    # 17c (2026-09-21): ILDIZ tekshiruvi — marshrut chetlab o'tilsa ham
    # (`services.close_employee_debt`, ichki chaqiruvlar) cheksiz / manfiy /
    # sig'imdan katta avans yoki noto'g'ri sana yozilmaydi (`ValueError`).
    toza = _clean_avans(amount, notes, adv_date)
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        return None
    adv = EmployeeAdvance(employee_id=employee_id, amount=toza["amount"],
                          notes=toza["notes"], given_by=given_by)
    if toza["adv_date"]:
        adv.date = toza["adv_date"]
    db.add(adv)
    db.commit()
    db.refresh(adv)
    return adv


def delete_employee_advance(db: Session, advance_id: int) -> bool:
    from models import EmployeeAdvance
    adv = db.query(EmployeeAdvance).filter(EmployeeAdvance.id == advance_id).first()
    if not adv:
        return False
    db.delete(adv)
    db.commit()
    return True


def get_employee_compensation_for_month(db: Session, employee_id: int, year: int, month: int):
    """Berilgan (year, month) uchun hodimning O'SHA PAYTDA amal qilgan
    to'lov parametrlarini qaytaradi (joriy/hozirgi qiymat emas!).

    Qidiruv: (effective_year, effective_month) <= (year, month) bo'lgan
    ENG SO'NGGI (eng yaqin o'tmishdagi) yozuv olinadi. Agar hech qanday
    tarix yozuvi topilmasa (masalan, migratsiyadan oldin backfill
    qilinmagan eski ma'lumot) — xavfsiz variant sifatida hodimning
    joriy (Employee jadvalidagi) qiymatlariga qaytiladi."""
    from models import EmployeeCompensationHistory

    rows = db.query(EmployeeCompensationHistory).filter(
        EmployeeCompensationHistory.employee_id == employee_id
    ).all()

    candidates = [r for r in rows if (r.effective_year, r.effective_month) <= (year, month)]
    if candidates:
        best = max(candidates, key=lambda r: (r.effective_year, r.effective_month, r.id))
        return {
            "pay_type": best.pay_type, "fixed_amount": best.fixed_amount,
            "percent_value": best.percent_value, "per_unit_rate": best.per_unit_rate,
            "per_unit_type": best.per_unit_type,
            "extra_monthly": best.extra_monthly,
        }

    # Zaxira variant — tarix yo'q bo'lsa, joriy qiymatdan foydalanish
    emp = get_employee(db, employee_id)
    if not emp:
        return None
    return {
        "pay_type": emp.pay_type, "fixed_amount": emp.fixed_amount,
        "percent_value": emp.percent_value, "per_unit_rate": emp.per_unit_rate,
        "per_unit_type": emp.per_unit_type,
        "extra_monthly": emp.extra_monthly,
    }


def backfill_employee_compensation_history(db: Session, company_id: int = None) -> dict:
    """Bir martalik migratsiya: to'lov tarixi yozuvi HALI YO'Q bo'lgan
    hodimlar uchun, joriy qiymatlarini ishga kirgan oyidan boshlab amal
    qiladigan qilib belgilaydi. Bir necha marta xavfsiz chaqirsa bo'ladi —
    allaqachon tarixi bor hodimlarga tegilmaydi (2026-09-06)."""
    from models import EmployeeCompensationHistory

    created = 0
    # M5 (2026-09-18) — TENANT: ilgari bu funksiya BARCHA korxonalar
    # xodimlarini aylanib chiqib, ularga tarix yozib qo'yardi.
    _eq = db.query(Employee).filter(Employee.is_deleted.isnot(True))
    if company_id is not None:
        _eq = _eq.filter(Employee.company_id == company_id)
    employees = _eq.all()
    for emp in employees:
        has_history = db.query(EmployeeCompensationHistory).filter(
            EmployeeCompensationHistory.employee_id == emp.id
        ).first()
        if has_history:
            continue
        hire = emp.hire_date or datetime.utcnow()
        db.add(EmployeeCompensationHistory(
            employee_id=emp.id,
            effective_year=hire.year, effective_month=hire.month,
            pay_type=emp.pay_type, fixed_amount=emp.fixed_amount,
            percent_value=emp.percent_value, per_unit_rate=emp.per_unit_rate,
            per_unit_type=emp.per_unit_type,
            extra_monthly=emp.extra_monthly,
            reason="Avtomatik backfill — tizimga qo'shilgandan beri shunday deb belgilandi"
        ))
        created += 1
    db.commit()
    return {"created": created, "total_employees": len(employees)}


def get_employee(db: Session, emp_id: int) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.id == emp_id).first()


def update_employee(db: Session, emp_id: int, data: EmployeeUpdate, updated_by: str = None) -> Optional[Employee]:
    from models import EmployeeCompensationHistory

    emp = get_employee(db, emp_id)
    if not emp:
        return None

    update_data = data.model_dump(exclude_unset=True)
    # 14-band: qat'iy tekshiruv — HECH NARSA yozilmasdan OLDIN (ValueError → 400).
    # `pay_type` kanonik qiymatga keltiriladi; noto'g'ri tur endi JIM
    # e'tiborsiz qolmaydi (quyidagi `except ValueError` ga yetib kelmaydi).
    update_data = _clean_update("Employee", update_data)
    effective_year = update_data.pop("effective_year", None)
    effective_month = update_data.pop("effective_month", None)
    reason = update_data.pop("reason", None)

    if "pay_type" in update_data:
        try:
            update_data["pay_type"] = PayType(update_data["pay_type"])
        except ValueError:
            del update_data["pay_type"]

    # To'lovga tegishli maydonlardan BIRORTASI o'zgartirilayotgan bo'lsa —
    # eski qiymatni "ustidan yozib" yubormasdan, YANGI tarix yozuvi ochamiz.
    # Shunda o'tgan oylarning hisob-kitobi hech qachon o'zgarib qolmaydi
    # (calculate_monthly_employee_pay shu tarixdan o'qiydi, joriy
    # Employee maydonidan emas — quyidagi services.py o'zgarishiga qarang).
    comp_fields = {"pay_type", "fixed_amount", "percent_value", "per_unit_rate",
                   "per_unit_type", "extra_monthly"}
    comp_changed = comp_fields.intersection(update_data.keys())

    for k, v in update_data.items():
        setattr(emp, k, v)

    if comp_changed:
        now = datetime.utcnow()
        eff_year = effective_year or now.year
        eff_month = effective_month or now.month

        # Shu (hodim, oy, yil) uchun tarix yozuvi ALLAQACHON bo'lsa (masalan,
        # shu oy ichida ikkinchi marta tuzatilyapti) — yangisini qo'shmasdan,
        # o'shani yangilaymiz (bitta oy uchun bitta haqiqiy qiymat bo'lsin).
        existing = db.query(EmployeeCompensationHistory).filter(
            EmployeeCompensationHistory.employee_id == emp_id,
            EmployeeCompensationHistory.effective_year == eff_year,
            EmployeeCompensationHistory.effective_month == eff_month
        ).first()

        hist = existing or EmployeeCompensationHistory(
            employee_id=emp_id, effective_year=eff_year, effective_month=eff_month
        )
        hist.pay_type = emp.pay_type
        hist.fixed_amount = emp.fixed_amount
        hist.percent_value = emp.percent_value
        hist.per_unit_rate = emp.per_unit_rate
        hist.per_unit_type = emp.per_unit_type
        hist.extra_monthly = emp.extra_monthly
        if reason:
            hist.reason = reason
        hist.created_by = updated_by
        if not existing:
            db.add(hist)

    db.commit()
    db.refresh(emp)
    return emp


def delete_employee(db: Session, emp_id: int, performed_by: str = None) -> bool:
    """Xodimni o'chirish — YUMSHOQ (is_deleted=True). Ma'lumot yo'qolmaydi,
    'O'chirilganlar' bo'limidan tiklash mumkin (inson xatosidan himoya)."""
    emp = get_employee(db, emp_id)
    if not emp:
        return False
    emp.is_deleted = True
    db.commit()
    log_activity(db, "deleted", "employee", emp_id, emp.name, performed_by,
                 company_id=getattr(emp, 'company_id', None))
    return True


def restore_employee(db: Session, emp_id: int, performed_by: str = None) -> bool:
    """O'chirilgan xodimni tiklaydi."""
    emp = db.query(Employee).filter(Employee.id == emp_id).first()
    if not emp:
        return False
    emp.is_deleted = False
    db.commit()
    log_activity(db, "restored", "employee", emp_id, emp.name, performed_by,
                 company_id=getattr(emp, 'company_id', None))
    return True


def permanent_delete_employee(db: Session, emp_id: int, performed_by: str = None) -> bool:
    """YUMSHOQ o'chirilgan xodimni BAZADAN BUTUNLAY o'chiradi. Avval unga
    bog'liq barcha yozuvlarni (sessiya, avans tarixi) tozalaydi — aks holda
    baza (Postgres) "chet el kaliti" xatosi berib, o'chirishga yo'l qo'ymaydi."""
    emp = db.query(Employee).filter(Employee.id == emp_id, Employee.is_deleted.is_(True)).first()
    if not emp:
        return False
    name = emp.name
    _emp_cid = getattr(emp, "company_id", None)   # M7: o'chirishdan OLDIN saqlanadi
    from models import EmployeeSession, EmployeeAdvance
    db.query(EmployeeSession).filter(EmployeeSession.employee_id == emp_id).delete()
    db.query(EmployeeAdvance).filter(EmployeeAdvance.employee_id == emp_id).delete()
    db.delete(emp)
    db.commit()
    log_activity(db, "permanently_deleted", "employee", emp_id, name, performed_by,
                 company_id=_emp_cid)
    return True


def get_deleted_employees(db: Session, company_id: int = None) -> List[Employee]:
    """O'chirilgan (lekin hali bazada saqlanayotgan) xodimlar."""
    _dq = db.query(Employee).filter(Employee.is_deleted.is_(True))
    if company_id is not None:      # M5
        _dq = _dq.filter(Employee.company_id == company_id)
    return _dq.order_by(Employee.name).all()


# ============================================================
# XODIM PANELI — login sozlash va avans so'rovlari
# ============================================================

def set_employee_login(db: Session, emp_id: int, phone: str, pin: str) -> Optional[Employee]:
    """Admin xodimga telefon+PIN belgilaydi (xodim panelga kirishi uchun)."""
    import auth
    emp = get_employee(db, emp_id)
    if not emp:
        return None
    emp.phone = phone.strip()
    emp.pin_hash = auth.hash_pin(pin.strip())
    db.commit()
    db.refresh(emp)
    return emp


def resolve_company_by_code(db: Session, code: str):
    """Korxona KODI bo'yicha korxonani topadi. Mijoz yuborgan kodga
    ISHONILMAYDI — u faqat qidiruv kaliti, natija bazadan olinadi.

    2026-09-18 — M1. Agar tizimda BITTA korxona bo'lsa, kod shart emas:
    server o'sha yagona korxonani oladi. Ikkinchi korxona paydo bo'lishi
    bilan kod majburiy bo'ladi — bu mavjud (bir korxonali) o'rnatmalarni
    buzmaslik uchun ataylab shunday."""
    from production_models import Company
    from sqlalchemy import func as _func
    kod = (code or "").strip()
    if kod:
        return db.query(Company).filter(
            _func.upper(Company.code) == kod.upper()).first()
    korxonalar = db.query(Company).limit(2).all()
    return korxonalar[0] if len(korxonalar) == 1 else None


def authenticate_employee(db: Session, phone: str, pin: str, company_id: int = None):
    """Telefon+PIN to'g'riligini tekshiradi — KORXONA ICHIDA.

    2026-09-18 — M1 (CRITICAL). W2b da `employees.phone` cheklovi
    (company_id, phone) juftligiga o'tkazildi, ya'ni IKKI KORXONADA bir xil
    telefonli xodim bo'lishi mumkin. Bu funksiya esa faqat telefon bo'yicha
    qidirib `.first()` olardi — qaysi qator kelishi tartibga bog'liq edi.
    Natijada B korxona admini o'z xodimiga A korxona xodimining telefonini
    berib, A ning xodim paneliga kirib qolishi mumkin edi.

    Endi korxona majburiy: topish (company_id, phone) juftligi bo'yicha."""
    import auth
    if not company_id:
        return None
    emp = db.query(Employee).filter(
        Employee.company_id == company_id,
        Employee.phone == phone.strip(),
        Employee.is_active == True
    ).first()
    if not emp or not emp.pin_hash:
        return None
    if not auth.verify_pin(pin.strip(), emp.pin_hash):
        return None
    # MUHIM: agar PIN hali eski (SHA-256) formatda bo'lsa — muvaffaqiyatli
    # kirishning o'zida, sezilmas tarzda bcrypt'ga yangilaymiz (parol bilan
    # bir xil mantiq — auth.verify_and_upgrade_password'ga qarang).
    if not auth._is_bcrypt_hash(emp.pin_hash):
        emp.pin_hash = auth.hash_pin(pin.strip())
        db.commit()
    return emp


def create_advance_request(db: Session, employee_id: int, amount: float, requested_date, notes: str = None):
    """Xodim o'zi 'avans oldim' deb yozadi — hali TASDIQLANMAGAN holatda."""
    from models import AdvanceRequest, AdvanceRequestStatus
    req = AdvanceRequest(
        employee_id=employee_id, amount=amount,
        requested_date=requested_date, notes=notes,
        status=AdvanceRequestStatus.PENDING
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def get_pending_advance_requests(db: Session, company_id: int = None) -> List[dict]:
    """Admin tasdiqlashi kerak bo'lgan, hali ko'rib chiqilmagan so'rovlar.

    M5 (2026-09-18) — TENANT: ilgari BARCHA korxonalarning so'rovlari
    qaytarilardi. `AdvanceRequest`da company_id ustuni yo'q — tenant
    otasi (Employee) orqali cheklanadi."""
    from models import AdvanceRequest, AdvanceRequestStatus
    q = db.query(AdvanceRequest).filter(
        AdvanceRequest.status == AdvanceRequestStatus.PENDING
    )
    if company_id is not None:
        q = q.join(Employee, Employee.id == AdvanceRequest.employee_id
                   ).filter(Employee.company_id == company_id)
    rows = q.order_by(AdvanceRequest.requested_date.asc()).all()
    result = []
    for r in rows:
        result.append({
            "id": r.id, "employee_id": r.employee_id,
            "employee_name": r.employee.name if r.employee else "—",
            "amount": float(r.amount), "requested_date": r.requested_date.isoformat(),
            "notes": r.notes, "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None
        })
    return result


def _advance_request_of_company(db: Session, request_id: int, company_id: int = None):
    """So'rovni FAQAT shu korxona xodimining so'rovi sifatida topadi (M5)."""
    from models import AdvanceRequest
    q = db.query(AdvanceRequest).filter(AdvanceRequest.id == request_id)
    if company_id is not None:
        q = q.join(Employee, Employee.id == AdvanceRequest.employee_id
                   ).filter(Employee.company_id == company_id)
    return q.first()


def confirm_advance_request(db: Session, request_id: int, confirmed_by: str,
                            company_id: int = None) -> Optional[dict]:
    """Admin tasdiqlaydi — shu bilan HAQIQIY EmployeeAdvance yozuvi yaratiladi
    (Moliya/Hisobotga to'g'ridan-to'g'ri ta'sir qiladigan)."""
    from models import AdvanceRequest, AdvanceRequestStatus, EmployeeAdvance
    req = _advance_request_of_company(db, request_id, company_id)   # M5
    if not req or req.status != AdvanceRequestStatus.PENDING:
        return None

    advance = EmployeeAdvance(
        employee_id=req.employee_id, amount=req.amount,
        date=req.requested_date,
        notes=(req.notes or "") + " (xodim o'zi yozgan, admin tasdiqladi)",
        given_by=confirmed_by
    )
    db.add(advance)

    req.status = AdvanceRequestStatus.CONFIRMED
    req.confirmed_at = datetime.utcnow()
    req.confirmed_by = confirmed_by
    db.commit()
    return {"success": True, "advance_id": advance.id}


def reject_advance_request(db: Session, request_id: int, confirmed_by: str,
                           company_id: int = None) -> bool:
    """Admin rad etadi — hech qanday moliyaviy yozuv yaratilmaydi."""
    from models import AdvanceRequest, AdvanceRequestStatus
    req = _advance_request_of_company(db, request_id, company_id)   # M5
    if not req or req.status != AdvanceRequestStatus.PENDING:
        return False
    req.status = AdvanceRequestStatus.REJECTED
    req.confirmed_at = datetime.utcnow()
    req.confirmed_by = confirmed_by
    db.commit()
    return True


def get_employee_own_requests(db: Session, employee_id: int, limit: int = 20) -> List[dict]:
    """Xodimning o'zi yuborgan so'rovlari tarixi (o'z paneli uchun)."""
    from models import AdvanceRequest
    rows = db.query(AdvanceRequest).filter(
        AdvanceRequest.employee_id == employee_id
    ).order_by(AdvanceRequest.submitted_at.desc()).limit(limit).all()
    return [{
        "id": r.id, "amount": float(r.amount),
        "requested_date": r.requested_date.isoformat(),
        "status": r.status.value, "notes": r.notes,
        "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None
    } for r in rows]


# ============================================================
# MASTER KPI — Yillik KPI (sotuvdan %, yil oxiri sovg'a)
# ============================================================

def update_master_kpi(db: Session, master_id: int, kpi_percent: float,
                      company_id: int = None) -> Optional[Master]:
    m = get_master(db, master_id, company_id)   # M5: faqat shu korxonadan
    if not m:
        return None
    m.kpi_percent = kpi_percent
    db.commit()
    db.refresh(m)
    return m


def get_master_kpi_detail(db: Session, master_id: int, year: int,
                          company_id: int = None) -> list:
    """Bitta usta uchun — shu yilgi HAR BIR buyurtmadan qancha KPI (sovg'a ulushi)
    chiqqanini ko'rsatadi. Faqat o'qish — hech qanday hisob-kitobga ta'sir qilmaydi,
    calculate_order_profit() dan olingan tayyor foyda asosida hisoblanadi."""
    import services
    from models import Order, OrderStatus, Master
    from sqlalchemy import extract

    master = get_master(db, master_id, company_id)   # M5: faqat shu korxonadan
    if not master:
        return []

    # MUHIM: o'chirilgan buyurtmalar ham hisobga olinadi — moliyaviy
    # tarix o'zgarmasligi kerak.
    orders = db.query(Order).filter(
        Order.master_id == master_id,
        Order.status == OrderStatus.READY,
        extract('year', Order.completed_at) == year
    ).order_by(Order.completed_at.desc()).all()

    kpi_pct = float(master.kpi_percent or 0)
    result = []
    for o in orders:
        try:
            profit_data = services.calculate_order_profit(db, o.id)
            profit = float(profit_data.get("foyda", 0))
        except Exception:
            db.rollback()
            profit = 0.0
        result.append({
            "order_id": o.id,
            "order_number": o.order_number,
            "completed_at": o.completed_at.isoformat() if o.completed_at else None,
            "total_amount": float(o.total_amount or 0),
            "profit": round(profit),
            "kpi_amount": round(profit * kpi_pct / 100),
        })

    # MUHIM (2026-09): Tayyor mahsulot bo'limidan TO'G'RIDAN-TO'G'RI
    # (buyurtmasiz) sotilgan, lekin sotuv paytida shu ustaga BIRIKTIRILGAN
    # (master_id) sotuvlar — ular ham shu ro'yxatga, alohida qator sifatida
    # qo'shiladi (buyurtma emasligi "order_id: null" orqali bilinadi).
    from models import FinishedProductSale as _FPS_detail
    fp_sales = db.query(_FPS_detail).filter(
        _FPS_detail.master_id == master_id,
        extract('year', _FPS_detail.sold_at) == year
    ).all()
    for s in fp_sales:
        profit = float(s.total_amount or 0) - float(s.cost_amount or 0)
        result.append({
            "order_id": None,
            "order_number": f"🏪 {s.product_name}",
            "completed_at": s.sold_at.isoformat() if s.sold_at else None,
            "total_amount": float(s.total_amount or 0),
            "profit": round(profit),
            "kpi_amount": round(profit * kpi_pct / 100),
        })

    result.sort(key=lambda x: x["completed_at"] or "", reverse=True)
    return result


def get_masters_kpi_report(db: Session, year: int, include_inactive: bool = False,
                          company_id: int = None) -> dict:
    """Har usta uchun yillik SOF FOYDA, KPI% va hisoblangan sovg'a.
    include_inactive=False bo'lsa — avvalgidek faqat faol ustalar (eski xatti-harakat saqlanadi)."""
    import services
    from models import Order, OrderStatus, FinishedProductSale as _FPS_report
    from sqlalchemy import extract

    q = db.query(Master)
    if company_id is not None:       # M5: faqat shu korxona ustalari
        q = q.filter(Master.company_id == company_id)
    if not include_inactive:
        q = q.filter(Master.is_active == True)
    masters = q.all()
    rows = []
    total_gift = 0.0

    # N+1 o'rniga — BARCHA ustalarning shu yillik buyurtmalarini
    # BITTA so'rov bilan olib, keyin usta bo'yicha guruhlaymiz.
    master_ids = [m.id for m in masters]
    # MUHIM: o'chirilgan buyurtmalar ham hisobga olinadi — moliyaviy
    # tarix (shu jumladan Usta KPI hisoboti) o'zgarmasligi kerak.
    all_orders = db.query(Order).filter(
        Order.master_id.in_(master_ids),
        Order.status == OrderStatus.READY,
        extract('year', Order.completed_at) == year
    ).all() if master_ids else []

    orders_by_master = {}
    for o in all_orders:
        orders_by_master.setdefault(o.master_id, []).append(o)

    # MUHIM (2026-09): Tayyor mahsulot bo'limidan TO'G'RIDAN-TO'G'RI
    # (buyurtmasiz) sotilgan, lekin shu ustaga BIRIKTIRILGAN sotuvlar —
    # ular ham yillik sotuv/foyda/sovg'a hisobiga qo'shiladi.
    all_fp_sales = db.query(_FPS_report).filter(
        _FPS_report.master_id.in_(master_ids),
        extract('year', _FPS_report.sold_at) == year
    ).all() if master_ids else []
    fp_sales_by_master = {}
    for s in all_fp_sales:
        fp_sales_by_master.setdefault(s.master_id, []).append(s)

    for m in masters:
        orders = orders_by_master.get(m.id, [])

        yearly_sales = 0.0
        yearly_profit = 0.0
        for o in orders:
            yearly_sales += float(o.total_amount or 0)
            try:
                profit_data = services.calculate_order_profit(db, o.id)
                yearly_profit += float(profit_data.get("foyda", 0))
            except Exception as e:
                db.rollback()
                try:
                    log_error(db, str(e), endpoint=f"get_masters_kpi_report:calculate_order_profit order#{o.id}")
                except Exception:
                    pass

        for s in fp_sales_by_master.get(m.id, []):
            yearly_sales += float(s.total_amount or 0)
            yearly_profit += float(s.total_amount or 0) - float(s.cost_amount or 0)

        gift = yearly_profit * (m.kpi_percent or 0) / 100
        total_gift += gift

        last_order = db.query(Order).filter(
            Order.master_id == m.id, Order.status == OrderStatus.READY
        ).order_by(Order.completed_at.desc()).first()

        rows.append({
            "id": m.id,
            "name": m.name,
            "phone": m.phone,
            "region": m.region,
            "is_active": m.is_active,
            "kpi_percent": m.kpi_percent or 0,
            # MUHIM (2026-08-27): avval bu yerda telegram_id umuman
            # qaytarilmasdi — shuning uchun Usta tahrirlash oynasi buni
            # HAR DOIM bo'sh ko'rsatardi (saqlagan bo'lsangiz ham), chunki
            # tahrirlash oynasi aynan shu ro'yxatdan ma'lumot oladi.
            "telegram_id": m.telegram_id or "",
            "yearly_sales": round(yearly_sales),
            "yearly_profit": round(yearly_profit),
            "orders_count": len(orders),
            "gift_amount": round(gift),
            "last_order_date": last_order.completed_at.isoformat() if last_order and last_order.completed_at else None
        })

    rows.sort(key=lambda x: x["gift_amount"], reverse=True)
    return {"year": year, "masters": rows, "total_gift": round(total_gift)}


# ══════════════════════════════════════════════════════════════════
# "Sovg'a DAVRI" — 2026-09-12, savdo-summasi asosidagi, davriy tizim.
# Eski (yillik/foyda-asosidagi, KPI% × sof foyda) MasterGift tizimidan
# FARQLI: (1) doimiy emas — admin "davr" ochib-yopadi (yiliga ~2 marta);
# (2) bosqichlar SAVDO SUMMASIGA (Order.total_amount + to'g'ridan-to'g'ri
# tayyor mahsulot sotuvi) qarab, foydaga emas; (3) har "Berildi"dan keyin
# hisoblagich RESET bo'ladi — chegaraga yetish o'zi hech narsani
# avtomatik bermaydi, usta yuqoriroq bosqichgacha "kutishi" ham mumkin;
# (4) davr davomidagi buyurtmalar oddiy keshbek (Bonuslarim) hisobidan
# CHIQARIB TASHLANADI — ikki marta hisoblanmasligi uchun; davr yopilganda,
# hech bir bosqichga yetmagan/ulgurmagan qoldiq FOYDASI orqali avtomatik
# keshbekka qaytariladi.
# ══════════════════════════════════════════════════════════════════

def get_active_gift_period(db: Session, company_id: int = None):
    """Joriy FAOL sovg'a davri.

    M5 (2026-09-18) — TENANT: ilgari bu so'rov korxona filtrisiz edi va
    `.first()` butun tizimdagi BIRINCHI faol davrni qaytarardi. Natijada
    (a) A korxona B ning davrini ko'rar/o'zgartira olardi, (b) B da faol
    davr bo'lsa A umuman yangi davr ocha olmasdi. Endi har bir korxona
    o'z davrida, mustaqil ishlaydi."""
    from models import GiftPeriod
    q = db.query(GiftPeriod).filter(GiftPeriod.is_active == True)
    if company_id is not None:
        q = q.filter(GiftPeriod.company_id == company_id)
    return q.first()


def get_gift_period_participant_ids(db: Session, period_id: int) -> set:
    # ESLATMA: bu yerda alohida korxona filtri SHART EMAS — `period_id`
    # allaqachon tenant-tekshirilgan davrdan keladi, ishtirokchilar esa
    # o'sha davrga bog'langan.
    """Bo'sh to'plam qaytarsa — demak BARCHA faol ustalar ishtirok etadi
    (standart holat, ustalar aniq tanlanmagan)."""
    from models import GiftPeriodParticipant
    rows = db.query(GiftPeriodParticipant.master_id).filter(
        GiftPeriodParticipant.period_id == period_id
    ).all()
    return {r[0] for r in rows}


def _gift_period_eligible_masters(db: Session, period) -> list:
    """Davrda ishtirok etadigan FAOL ustalar ro'yxatini (Master obyektlari) qaytaradi.

    M5 — TENANT: "barcha faol ustalar" rejimi endi FAQAT davrning O'Z
    korxonasi ustalarini oladi. Ilgari B korxonaning ustasi A ning
    davrida avtomatik ishtirok etardi (jonli sinovda tasdiqlangan)."""
    participant_ids = get_gift_period_participant_ids(db, period.id)
    q = db.query(Master).filter(Master.is_active == True)
    _pcid = getattr(period, "company_id", None)
    if _pcid is not None:
        q = q.filter(Master.company_id == _pcid)
    if participant_ids:
        q = q.filter(Master.id.in_(participant_ids))
    return q.order_by(Master.name).all()


def master_in_active_gift_period(db: Session, master_id: int,
                                 company_id: int = None) -> bool:
    """Berilgan usta joriy faol davrda ishtirok etadimi (davr umuman
    faol bo'lmasa ham, yoki ishtirokchi sifatida tanlanmagan bo'lsa ham
    — False)."""
    period = get_active_gift_period(db, company_id)
    if not period:
        return False
    # M5: usta davrning o'z korxonasidan bo'lishi shart.
    if not get_master(db, master_id, getattr(period, "company_id", None)):
        return False
    participant_ids = get_gift_period_participant_ids(db, period.id)
    if not participant_ids:
        return True
    return master_id in participant_ids


_SOVGA_USTA_MAX = 1000
_SOVGA_NOM_MAX = 100    # `gift_period_tiers.gift_name` — String(100)


def _sovga_ustalari(master_ids) -> list:
    """17f: sovg'a davri ishtirokchilari — `None` / bo'sh (barcha faol ustalar)
    yoki musbat butun sonlar ro'yxati (`true` / matn / kasr — yo'q; ilgari
    `int(True)` → 1-usta jimgina qo'shilardi, matn esa jim tashlanardi)."""
    if master_ids is None:
        return []
    if not isinstance(master_ids, list):
        raise ValueError("'master_ids' ro'yxat bo'lishi kerak")
    if len(master_ids) > _SOVGA_USTA_MAX:
        raise ValueError(f"'master_ids' juda ko'p ({_SOVGA_USTA_MAX} tadan ko'p)")
    natija = []
    for i, mid in enumerate(master_ids):
        if isinstance(mid, bool) or not isinstance(mid, int) or not (1 <= mid <= 2_147_483_647):
            raise ValueError(f"'master_ids' {i + 1}-qiymat: musbat butun son bo'lishi kerak")
        if mid not in natija:
            natija.append(mid)
    return natija


def open_gift_period(db: Session, tiers: list, master_ids: list = None, performed_by: str = None,
                    company_id: int = None) -> dict:
    """Yangi sovg'a davrini ochadi. `tiers` — [{"gift_name": str,
    "threshold_amount": float}, ...], kamida bitta. Har bosqichning
    threshold_amount'i — RESET'dan keyingi YANGI savdo summasi (jami emas).
    `master_ids` — ixtiyoriy: bo'sh/berilmagan bo'lsa, BARCHA faol ustalar
    ishtirok etadi (standart); ro'yxat berilsa, FAQAT o'sha ustalar."""
    from models import GiftPeriod, GiftPeriodTier, GiftPeriodParticipant
    if get_active_gift_period(db, company_id):
        return {"success": False, "message": "Allaqachon faol sovg'a davri bor — avval uni yoping"}
    # 17f (2026-09-22) — HAQIQIY PostgreSQL da O'LCHANGAN (`work/probe17f_pg.py`):
    # bosqichlar `float(t.get(...))` bilan TEKSHIRUVSIZ o'qilardi — `tiers`
    # matn / `[5]` / summa "abc" / nom son / summa `Infinity` / `1e20` / 101
    # belgili nom — HAMMASI 500; `0.001` → 0.00 so'mlik bosqich (har qanday
    # savdo darhol "sovg'aga yetdi"); `"5000"` va `true` jimgina songa
    # aylanardi; `master_ids` dagi `true` → 1-usta. `kpi.html` bo'sh
    # qatorlarni O'ZI tashlab yuboradi va faqat {gift_name, threshold_amount}
    # hamda butun sonli `master_ids` yuboradi — endi aynan shu talab qilinadi
    # (yozishdan OLDIN, xato → 400).
    if tiers is None or (isinstance(tiers, list) and not tiers):
        return {"success": False, "message": "Kamida bitta to'g'ri bosqich (nomi va musbat summasi bilan) kiriting"}
    try:
        toza = _clean_val("GiftPeriodOpen", {"tiers": tiers})
        toza_ustalar = _sovga_ustalari(master_ids)
    except ValueError as e:
        return {"success": False, "message": str(e)}
    clean_tiers = [(t["gift_name"].strip(), t["threshold_amount"]) for t in toza["tiers"]]
    clean_tiers.sort(key=lambda x: x[1])
    # M5: davr ANIQ joriy korxonaga tegishli bo'ladi (ilgari company_id
    # berilmagani uchun yozuv bazadagi vaqtinchalik DEFAULT 1 ga tushardi).
    period = GiftPeriod(company_id=company_id, is_active=True, created_by=performed_by)
    db.add(period)
    db.flush()
    for i, (name, amt) in enumerate(clean_tiers):
        db.add(GiftPeriodTier(period_id=period.id, gift_name=name, threshold_amount=amt, sort_order=i))
    for mid in toza_ustalar:
        # M5: faqat SHU korxonaning ustasi ishtirokchi bo'la oladi.
        if company_id is not None and not get_master(db, mid, company_id):
            continue
        db.add(GiftPeriodParticipant(period_id=period.id, master_id=mid))
    db.commit()
    db.refresh(period)
    return {"success": True, "period_id": period.id}


def _gift_period_sales_since(db: Session, master_id: int, start_dt, end_dt,
                             company_id: int = None) -> float:
    """(start_dt < vaqt <= end_dt] oralig'idagi ustaning umumiy savdo
    summasi — buyurtmalar (Order.total_amount) VA to'g'ridan-to'g'ri tayyor
    mahsulot sotuvlari (FinishedProductSale.total_amount) qo'shilib."""
    from models import Order, OrderStatus, FinishedProductSale
    # M5 — TENANT: savdo yig'indisiga faqat SHU korxonaning buyurtma va
    # sotuvlari kiradi.
    q1 = db.query(Order).filter(
        Order.master_id == master_id, Order.status == OrderStatus.READY,
        Order.completed_at > start_dt,
    )
    if company_id is not None:
        q1 = q1.filter(Order.company_id == company_id)
    if end_dt:
        q1 = q1.filter(Order.completed_at <= end_dt)
    total = sum(float(o.total_amount or 0) for o in q1.all())

    q2 = db.query(FinishedProductSale).filter(
        FinishedProductSale.master_id == master_id,
        FinishedProductSale.sold_at > start_dt,
    )
    if company_id is not None:
        q2 = q2.filter(FinishedProductSale.company_id == company_id)
    if end_dt:
        q2 = q2.filter(FinishedProductSale.sold_at <= end_dt)
    total += sum(float(s.total_amount or 0) for s in q2.all())
    return total


def _gift_period_profit_since(db: Session, master_id: int, start_dt, end_dt,
                              company_id: int = None) -> float:
    """Xuddi yuqoridagi kabi, lekin SAVDO emas, FOYDA — davr yopilganda
    keshbekka aylantirish uchun ishlatiladi."""
    import services
    from models import Order, OrderStatus, FinishedProductSale
    total = 0.0
    q1 = db.query(Order).filter(
        Order.master_id == master_id, Order.status == OrderStatus.READY,
        Order.completed_at > start_dt, Order.completed_at <= end_dt,
    )
    if company_id is not None:      # M5
        q1 = q1.filter(Order.company_id == company_id)
    for o in q1.all():
        try:
            total += float(services.calculate_order_profit(db, o.id).get("foyda", 0))
        except Exception:
            db.rollback()
    q2 = db.query(FinishedProductSale).filter(
        FinishedProductSale.master_id == master_id,
        FinishedProductSale.sold_at > start_dt, FinishedProductSale.sold_at <= end_dt,
    )
    if company_id is not None:      # M5
        q2 = q2.filter(FinishedProductSale.company_id == company_id)
    for s in q2.all():
        total += float(s.total_amount or 0) - float(s.cost_amount or 0)
    return total


def _master_gift_period_checkpoint(db: Session, master_id: int, period) -> datetime:
    """Ustaning shu davrdagi oxirgi 'reset' vaqti — oxirgi 'gift' turidagi
    olingan sovg'asi vaqti, bo'lmasa davr boshlangan vaqt."""
    from models import MasterGiftPeriodRedemption
    last = db.query(MasterGiftPeriodRedemption).filter(
        MasterGiftPeriodRedemption.period_id == period.id,
        MasterGiftPeriodRedemption.master_id == master_id,
        MasterGiftPeriodRedemption.kind == "gift",
    ).order_by(MasterGiftPeriodRedemption.redeemed_at.desc()).first()
    return last.redeemed_at if last else period.started_at


def get_master_gift_period_progress(db: Session, master_id: int,
                                   company_id: int = None) -> dict:
    """Faol davr bo'yicha — ustaning joriy (oxirgi reset'dan keyingi)
    savdosi, barcha bosqichlar va ENG YUQORI qaysi biriga 'tayyor' ekani.
    Agar davr faol bo'lsa-yu, bu usta unda ISHTIROK ETMASA — 'active: False'
    qaytariladi (usta uchun davr umuman ko'rinmasligi kerak)."""
    period = get_active_gift_period(db, company_id)
    if not period or not master_in_active_gift_period(db, master_id, company_id):
        return {"active": False}
    _cid = getattr(period, "company_id", None)
    checkpoint = _master_gift_period_checkpoint(db, master_id, period)
    sales = _gift_period_sales_since(db, master_id, checkpoint, None, company_id=_cid)
    tiers = sorted(period.tiers, key=lambda t: t.threshold_amount)
    result_tiers = []
    highest_ready = None
    for t in tiers:
        ready = sales >= float(t.threshold_amount) - 0.01
        if ready:
            highest_ready = t
        result_tiers.append({
            "id": t.id, "gift_name": t.gift_name,
            "threshold_amount": float(t.threshold_amount), "ready": ready,
        })
    return {
        "active": True, "period_id": period.id, "current_sales": sales,
        "tiers": result_tiers,
        "ready_tier_id": highest_ready.id if highest_ready else None,
        "ready_tier_name": highest_ready.gift_name if highest_ready else None,
    }


def update_gift_period_tier(db: Session, tier_id: int, gift_name: str, threshold_amount: float,
                           company_id: int = None) -> dict:
    """Faol davrdagi bir bosqichning nomi/summasini o'zgartiradi. Bu —
    ALLAQACHON berilgan sovg'alar tarixiga (MasterGiftPeriodRedemption)
    ta'sir qilmaydi, chunki tarix o'z nusxasini (gift_name, sales_amount)
    alohida saqlaydi."""
    from models import GiftPeriodTier
    # M5: davr joriy korxonanikidan olinadi — bosqich esa SHU davrga
    # tegishli bo'lishi shart, ya'ni begona `tier_id` topilmaydi.
    period = get_active_gift_period(db, company_id)
    if not period:
        return {"success": False, "message": "Faol sovg'a davri yo'q"}
    tier = db.query(GiftPeriodTier).filter(
        GiftPeriodTier.id == tier_id, GiftPeriodTier.period_id == period.id
    ).first()
    if not tier:
        return {"success": False, "message": "Bosqich topilmadi"}
    # 2026-09-21 — O'LCHANGAN: matnli summa (`float("abc")`) va matn
    # bo'lmagan nom (`5.strip()`) → 500 edi; `1e20` summa SQLite da
    # yozilardi, PostgreSQL da Numeric(12,2) sig'imidan oshib 500 berardi.
    if gift_name is not None and not isinstance(gift_name, str):
        return {"success": False, "message": "Sovg'a nomi matn bo'lishi kerak"}
    name = (gift_name or "").strip()
    try:
        amt = _json_son("threshold_amount", threshold_amount, bosh_mumkin=True,
                        musbat=False, chegara=_ORDER_ITEM_MAX_MONEY) or 0
    except ValueError:
        return {"success": False, "message": "Summa to'g'ri son bo'lishi kerak "
                                             "(musbat, 9 999 999 999.99 dan oshmasin)"}
    if not name or amt <= 0:
        return {"success": False, "message": "Sovg'a nomi va musbat summa shart"}
    # 17f (2026-09-22) — HAQIQIY PostgreSQL da O'LCHANGAN: `0.001` → 0.00 so'mlik
    # bosqich (200); 101+ belgili nom → String(100) → 500.
    if round(amt, 2) < _PUL_ENG_KAM:
        return {"success": False, "message": f"Summa kamida {_PUL_ENG_KAM} so'm bo'lishi kerak "
                                             "(1 tiyindan kichik summa bazada 0 ga aylanadi)"}
    if len(name) > _SOVGA_NOM_MAX:
        return {"success": False, "message": f"Sovg'a nomi juda uzun ({_SOVGA_NOM_MAX} belgidan ko'p)"}
    tier.gift_name = name
    tier.threshold_amount = amt
    db.commit()
    return {"success": True}


def redeem_gift_period_tier(db: Session, master_id: int, tier_id: int, performed_by: str = None,
                           company_id: int = None) -> dict:
    """Bir bosqichni ustaga 'berildi' deb belgilaydi. Muvaffaqiyatli
    bo'lsa, ustaning hisoblagichi shu paytdan RESET bo'ladi (checkpoint
    funksiyasi keyingi so'rovda avtomatik shu yozuvni topadi)."""
    from models import GiftPeriodTier, Master, MasterGiftPeriodRedemption
    period = get_active_gift_period(db, company_id)
    if not period:
        return {"success": False, "message": "Faol sovg'a davri yo'q"}
    _cid = getattr(period, "company_id", None)
    tier = db.query(GiftPeriodTier).filter(
        GiftPeriodTier.id == tier_id, GiftPeriodTier.period_id == period.id
    ).first()
    if not tier:
        return {"success": False, "message": "Bosqich topilmadi"}
    master = get_master(db, master_id, _cid)    # M5: faqat shu korxona ustasi
    if not master:
        return {"success": False, "message": "Usta topilmadi"}
    checkpoint = _master_gift_period_checkpoint(db, master_id, period)
    sales = _gift_period_sales_since(db, master_id, checkpoint, None, company_id=_cid)
    if sales < float(tier.threshold_amount) - 0.01:
        return {"success": False,
                "message": f"Usta hali bu bosqichga yetmagan (kerak: {tier.threshold_amount:,.0f}, mavjud: {sales:,.0f})"}
    db.add(MasterGiftPeriodRedemption(
        period_id=period.id, master_id=master_id, tier_id=tier.id,
        gift_name=tier.gift_name, sales_amount=sales, kind="gift", redeemed_by=performed_by,
    ))
    db.commit()
    return {"success": True}


def get_gift_period_overview(db: Session, company_id: int = None) -> dict:
    """Admin panel uchun — faol davr, uning bosqichlari, va har bir
    ISHTIROKCHI ustaning joriy holati (savdosi, tayyor bo'lsa qaysi bosqichga)."""
    period = get_active_gift_period(db, company_id)
    if not period:
        return {"active": False}
    _cid = getattr(period, "company_id", None)
    masters = _gift_period_eligible_masters(db, period)
    participant_ids = get_gift_period_participant_ids(db, period.id)
    rows = []
    pending = []
    for m in masters:
        prog = get_master_gift_period_progress(db, m.id, company_id=_cid)
        row = {
            "master_id": m.id, "master_name": m.name,
            "current_sales": prog["current_sales"], "tiers": prog["tiers"],
            "ready_tier_id": prog["ready_tier_id"], "ready_tier_name": prog["ready_tier_name"],
        }
        if prog["ready_tier_id"]:
            pending.append(m.name)
        rows.append(row)
    return {
        "active": True, "period_id": period.id,
        "started_at": period.started_at.isoformat() if period.started_at else None,
        "tiers": [{"id": t.id, "gift_name": t.gift_name, "threshold_amount": float(t.threshold_amount)}
                  for t in sorted(period.tiers, key=lambda t: t.threshold_amount)],
        "masters": rows, "pending_master_names": pending,
        "all_masters": not bool(participant_ids),
        "participant_ids": sorted(participant_ids),
    }


def add_master_to_active_gift_period(db: Session, master_id: int, performed_by: str = None,
                                    company_id: int = None) -> dict:
    """2026-09-16 (foydalanuvchi so'rovi bo'yicha): davr ANIQ ustalar
    ro'yxati bilan (hammasi emas) ochilgan bo'lsa, keyinroq ishga
    qabul qilingan/faollashtirilgan yangi ustani davrni TO'XTATMASDAN
    shu ro'yxatga qo'shish imkonini beradi.

    MUHIM: agar davr "barcha faol ustalar" rejimida ochilgan bo'lsa
    (hech qanday GiftPeriodParticipant yozuvi yo'q — get_gift_period_
    participant_ids() bo'sh to'plam qaytaradi), unga BITTA aniq
    ishtirokchi qo'shib bo'lmaydi — bu, aksincha, davrni "faqat shu
    bitta usta" rejimiga aylantirib, boshqa BARCHA ustalarni davrdan
    chiqarib tashlagan bo'lardi. Bunday holda hech narsa o'zgartirilmaydi
    — yangi usta ALLAQACHON avtomatik ishtirok etadi (dinamik so'rov
    orqali), shunchaki shu haqda xabar qaytariladi.
    """
    period = get_active_gift_period(db, company_id)
    if not period:
        return {"success": False, "message": "Faol sovg'a davri yo'q"}
    # M5: faqat davrning O'Z korxonasidagi usta qo'shilishi mumkin.
    master = get_master(db, master_id, getattr(period, "company_id", None))
    if not master:
        return {"success": False, "message": "Usta topilmadi"}
    if not master.is_active:
        return {"success": False, "message": f"{master.name} faol emas — avval uni faollashtiring"}

    from models import GiftPeriodParticipant
    participant_ids = get_gift_period_participant_ids(db, period.id)
    if not participant_ids:
        return {
            "success": True, "already_included": True, "all_masters_mode": True,
            "message": f"{master.name} qo'shish shart emas — bu davr \"barcha faol ustalar\" rejimida ochilgan, u allaqachon avtomatik ishtirok etadi.",
        }
    if master_id in participant_ids:
        return {"success": True, "already_included": True, "all_masters_mode": False,
                "message": f"{master.name} allaqachon shu davrda ishtirok etmoqda."}

    db.add(GiftPeriodParticipant(period_id=period.id, master_id=master_id))
    log_activity(db, "gift_period_add_master", "gift_period", period.id,
                 company_id=getattr(period, 'company_id', None),
                 entity_label=master.name, performed_by=performed_by)
    db.commit()
    return {"success": True, "already_included": False, "all_masters_mode": False,
            "message": f"{master.name} davrga qo'shildi — bu daqiqadan boshlab uning savdosi hisoblana boshlaydi."}


def close_gift_period(db: Session, performed_by: str = None, force: bool = False,
                     company_id: int = None) -> dict:
    """Faol davrni yopadi. Agar biror usta biror bosqichga 'tayyor' bo'lib,
    hali 'Berildi' deb belgilanmagan bo'lsa va force=False bo'lsa — YOPMAY,
    ogohlantirish qaytaradi (aks holda uning haqli sovg'asi bekorga
    keshbekka aylanib ketadi). force=True bo'lsa, har bir ISHTIROKCHI
    ustaning checkpoint'dan keyingi qoldiq savdosi FOYDA orqali (KPI% ×)
    avtomatik keshbek hisobiga o'tkaziladi."""
    from models import MasterGiftPeriodRedemption
    period = get_active_gift_period(db, company_id)
    if not period:
        return {"success": False, "message": "Faol sovg'a davri yo'q"}
    _cid = getattr(period, "company_id", None)

    overview = get_gift_period_overview(db, company_id=_cid)
    if overview["pending_master_names"] and not force:
        return {
            "success": False,
            "message": "Ba'zi ustalar sovg'aga yetgan, lekin hali \"Berildi\" deb belgilanmagan.",
            "pending_master_names": overview["pending_master_names"],
        }

    now = datetime.utcnow()
    masters = _gift_period_eligible_masters(db, period)
    for m in masters:
        checkpoint = _master_gift_period_checkpoint(db, m.id, period)
        sales = _gift_period_sales_since(db, m.id, checkpoint, now, company_id=_cid)
        if sales <= 0.01:
            continue
        profit = _gift_period_profit_since(db, m.id, checkpoint, now, company_id=_cid)
        cashback_amount = profit * float(m.kpi_percent or 0) / 100
        db.add(MasterGiftPeriodRedemption(
            period_id=period.id, master_id=m.id, tier_id=None,
            gift_name="(Keshbekka o'tkazildi)", sales_amount=sales,
            profit_amount=cashback_amount, kind="cashback_conversion", redeemed_by=performed_by,
        ))
    period.is_active = False
    period.closed_at = now
    db.commit()
    return {"success": True}


def get_master_yearly_cashback(db: Session, master_id: int, year: int,
                              company_id: int = None) -> dict:
    """'Bonuslarim' (bot) uchun — yillik keshbek hisoboti. Har qanday
    sovg'a davri (o'tgan yoki joriy) davomida bo'lgan buyurtmalar/sotuvlar
    bu yerdan CHIQARIB TASHLANADI (ular sovg'aga ketgan yoki hali
    ketayapti); o'rniga, yopilgan davrlarning 'cashback_conversion'
    yozuvlari (ushbu yilga tegishlilari) qo'shiladi."""
    import services
    from sqlalchemy import extract
    from models import Order, OrderStatus, FinishedProductSale, GiftPeriod, MasterGiftPeriodRedemption, Master

    # M5 (2026-09-18) — TENANT: usta, davrlar, buyurtmalar, sotuvlar va
    # o'tkazmalar — hammasi SHU korxona ichidan.
    master = get_master(db, master_id, company_id)
    if not master:
        return {"yearly_profit": 0.0, "kpi_percent": 0.0, "jami_bonus": 0.0,
                "orders": [], "gift_period_conversion": 0.0}
    kpi_pct = float(master.kpi_percent or 0)
    cid = company_id if company_id is not None else getattr(master, "company_id", None)

    _pq = db.query(GiftPeriod)
    if cid is not None:
        _pq = _pq.filter(GiftPeriod.company_id == cid)
    periods = _pq.all()

    def _in_any_period(dt):
        if not dt:
            return False
        for p in periods:
            end = p.closed_at or datetime.utcnow()
            if p.started_at < dt <= end:
                return True
        return False

    _oq = db.query(Order).filter(
        Order.master_id == master_id, Order.status == OrderStatus.READY,
        extract('year', Order.completed_at) == year,
    )
    if cid is not None:
        _oq = _oq.filter(Order.company_id == cid)
    orders = _oq.order_by(Order.completed_at.desc()).all()

    yearly_profit = 0.0
    buyurtmalar = []
    for o in orders:
        if _in_any_period(o.completed_at):
            continue
        try:
            foyda = float(services.calculate_order_profit(db, o.id).get("foyda", 0))
        except Exception:
            db.rollback()
            foyda = 0.0
        yearly_profit += foyda
        buyurtmalar.append((o.order_number, foyda))

    _sq = db.query(FinishedProductSale).filter(
        FinishedProductSale.master_id == master_id,
        extract('year', FinishedProductSale.sold_at) == year,
    )
    if cid is not None:
        _sq = _sq.filter(FinishedProductSale.company_id == cid)
    fp_sales = _sq.all()
    for s in fp_sales:
        if _in_any_period(s.sold_at):
            continue
        yearly_profit += float(s.total_amount or 0) - float(s.cost_amount or 0)

    jami_bonus = yearly_profit * kpi_pct / 100

    _cq = db.query(MasterGiftPeriodRedemption).filter(
        MasterGiftPeriodRedemption.master_id == master_id,
        MasterGiftPeriodRedemption.kind == "cashback_conversion",
        extract('year', MasterGiftPeriodRedemption.redeemed_at) == year,
    )
    if cid is not None:
        # MasterGiftPeriodRedemption'da company_id ustuni yo'q — tenant
        # otasi (GiftPeriod) orqali cheklanadi.
        _cq = _cq.join(GiftPeriod, GiftPeriod.id == MasterGiftPeriodRedemption.period_id
                       ).filter(GiftPeriod.company_id == cid)
    conversions = _cq.all()
    conversion_total = sum(float(c.profit_amount or 0) for c in conversions)
    jami_bonus += conversion_total

    return {
        "yearly_profit": yearly_profit, "kpi_percent": kpi_pct,
        "jami_bonus": jami_bonus, "orders": buyurtmalar,
        "gift_period_conversion": conversion_total,
    }


from models import Supplier, SupplierPayment, InventoryPurchase
from schemas import SupplierCreate, SupplierUpdate, SupplierPaymentCreate


def create_supplier(db: Session, data: SupplierCreate, company_id: int = None) -> Supplier:
    """Yangi ta'minotchi qo'shadi.

    2026-09-18 — M8/F1a: `company_id` UMUMAN berilmasdi va yozuv faqat
    bazadagi vaqtinchalik `DEFAULT 1` tufayli saqlanardi — ya'ni B korxona
    admini ta'minotchi yaratsa, u A korxonaga tushib qolardi. Endi tenant
    ANIQ beriladi (mijoz so'rovidan emas, sessiyadan)."""
    # 15-band: qat'iy tekshiruv — HECH NARSA yozilmasdan OLDIN (ValueError → 400).
    _clean_create("Supplier", data.model_dump(exclude_unset=True))
    s = Supplier(company_id=company_id,
                 name=data.name.strip(), phone=data.phone, notes=data.notes)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def get_suppliers(db: Session, only_active: bool = True,
                  company_id: int = None) -> List[Supplier]:
    q = db.query(Supplier)
    if company_id is not None:
        q = q.filter(Supplier.company_id == company_id)
    if only_active:
        q = q.filter(Supplier.is_active == True)
    return q.order_by(Supplier.name).all()


def get_supplier(db: Session, supplier_id: int, company_id: int = None) -> Optional[Supplier]:
    q = db.query(Supplier).filter(Supplier.id == supplier_id)
    if company_id is not None:
        q = q.filter(Supplier.company_id == company_id)
    return q.first()


def update_supplier(db: Session, supplier_id: int, data: SupplierUpdate) -> Optional[Supplier]:
    s = get_supplier(db, supplier_id)
    if not s:
        return None
    # 14-band: qat'iy tekshiruv — HECH NARSA yozilmasdan OLDIN (ValueError → 400).
    toza = _clean_update("Supplier", data.model_dump(exclude_unset=True))
    for k, v in toza.items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


def delete_supplier(db: Session, supplier_id: int, force: bool = False) -> dict:
    """Yetkazib beruvchini o'chiradi.
    Qarzi bo'lsa force=True bo'lmaguncha o'chirmaydi (xato qaytaradi).
    force=True bo'lsa — tarixi (xaridlar, to'lovlar) bilan birga butunlay o'chadi."""
    s = get_supplier(db, supplier_id)
    if not s:
        return {"success": False, "message": "Topilmadi"}

    debt_info = get_supplier_debt(db, supplier_id)
    if debt_info["debt"] > 0 and not force:
        return {
            "success": False,
            "message": f"Bu yetkazib beruvchida {debt_info['debt']:,.0f} so'm qarz bor".replace(",", " "),
            "has_debt": True,
            "debt": debt_info["debt"]
        }

    # Bog'liq xaridlarni supplier_id=NULL qilamiz (tarixi Omborxonada saqlanib qoladi,
    # lekin endi hech kimga bog'lanmaydi) — to'lovlarni esa o'chiramiz (faqat shu supplierga tegishli)
    #
    # 21-band (2026-09-21, JONLI VA LOKAL O'LCHANGAN): `suppliers.id` ga
    # ishora qiluvchi TO'RTTA ustun bor (models.py):
    #     InventoryPurchase.supplier_id   (nullable)  — quyida NULL qilinardi
    #     SupplierPayment.supplier_id     (NOT NULL)  — quyida o'chirilardi
    #     InventoryMovement.supplier_id   (nullable)  — TEGILMASDI  ← nuqson
    #     InventoryReceipt.supplier_id    (nullable)  — TEGILMASDI  ← nuqson
    # Har kirimda `log_movement(..., supplier_id=...)` yoziladi, ya'ni BIR
    # MARTA ham xarid qilingan ta'minotchini o'chirib bo'lmasdi: PostgreSQL
    # `inventory_movements_supplier_id_fkey` cheklovini buzib COMMIT da
    # yiqilardi va foydalanuvchi "Serverda kutilmagan xato yuz berdi" (500)
    # ko'rardi. Xaridsiz ta'minotchi o'chgani uchun bu ilgari sezilmagan
    # (kech13 nazorati aynan shunday edi). SQLite da FK cheklovi standart
    # HOLATDA o'chiq — shuning uchun lokal testlarda ham ko'rinmagan
    # (`tools/test_tamin_ochirish.py` `PRAGMA foreign_keys=ON` bilan
    # ishlaydi va shu yo'lni qulflaydi).
    from models import InventoryMovement, InventoryReceipt
    db.query(InventoryPurchase).filter(InventoryPurchase.supplier_id == supplier_id).update(
        {"supplier_id": None}
    )
    db.query(InventoryMovement).filter(InventoryMovement.supplier_id == supplier_id).update(
        {"supplier_id": None}
    )
    db.query(InventoryReceipt).filter(InventoryReceipt.supplier_id == supplier_id).update(
        {"supplier_id": None}
    )
    db.query(SupplierPayment).filter(SupplierPayment.supplier_id == supplier_id).delete()

    db.delete(s)
    db.commit()
    return {"success": True}


def get_supplier_debt(db: Session, supplier_id: int, company_id: int = None) -> dict:
    """Yetkazib beruvchiga qancha qarzdorlik bor.

    M6 — TENANT: ta'minotchi boshqa korxonaniki bo'lsa, bo'sh natija
    qaytadi (xarid/to'lov summalari umuman o'qilmaydi)."""
    if company_id is not None:
        _sup = db.query(Supplier).filter(
            Supplier.id == supplier_id, Supplier.company_id == company_id).first()
        if not _sup:
            return {"total_credit": 0, "total_paid": 0, "debt": 0, "purchase_count": 0}

    purchases = db.query(InventoryPurchase).filter(
        InventoryPurchase.supplier_id == supplier_id,
        InventoryPurchase.is_credit == True
    ).all()
    payments = db.query(SupplierPayment).filter(SupplierPayment.supplier_id == supplier_id).all()

    total_credit = sum(float(p.total_amount) for p in purchases)
    total_paid = sum(float(p.amount) for p in payments)
    debt = max(0, total_credit - total_paid)

    return {
        "total_credit": round(total_credit),
        "total_paid": round(total_paid),
        "debt": round(debt),
        "purchase_count": len(purchases)
    }


def get_supplier_payment_due_dates(db: Session, company_id: int = None) -> List[dict]:
    """Qarzdor yetkazib beruvchilar orasida, TO'LOV MUDDATI belgilangan
    xaridlarni topadi — har bir yetkazib beruvchi uchun ENG YAQIN
    (eng shoshilinch) muddatni qaytaradi. Dashboard ogohlantirishi uchun.
    Faqat o'qish — hech narsani o'zgartirmaydi."""
    from datetime import datetime as dt

    now = dt.utcnow()
    _uq = db.query(InventoryPurchase).filter(
        InventoryPurchase.is_credit == True,
        InventoryPurchase.payment_due_date.isnot(None),
        InventoryPurchase.supplier_id.isnot(None)
    )
    if company_id is not None:      # M6: ota (ta'minotchi) orqali
        _uq = _uq.join(Supplier, Supplier.id == InventoryPurchase.supplier_id).filter(
            Supplier.company_id == company_id)
    unpaid_with_due = _uq.order_by(InventoryPurchase.payment_due_date.asc()).all()

    # Har bir yetkazib beruvchi uchun eng yaqin muddatni saqlaymiz
    earliest_by_supplier = {}
    for p in unpaid_with_due:
        sid = p.supplier_id
        if sid not in earliest_by_supplier or p.payment_due_date < earliest_by_supplier[sid]:
            earliest_by_supplier[sid] = p.payment_due_date

    result = []
    for sid, due_date in earliest_by_supplier.items():
        debt_info = get_supplier_debt(db, sid, company_id=company_id)
        if debt_info["debt"] <= 0:
            continue  # To'lab bo'lingan — ogohlantirish kerak emas
        _sq = db.query(Supplier).filter(Supplier.id == sid)
        if company_id is not None:
            _sq = _sq.filter(Supplier.company_id == company_id)
        supplier = _sq.first()
        if not supplier:
            continue
        days_left = (due_date.date() - now.date()).days
        status = "overdue" if days_left < 0 else ("due_soon" if days_left <= 3 else "ok")
        result.append({
            "supplier_id": sid, "supplier_name": supplier.name,
            "debt": debt_info["debt"], "due_date": due_date.isoformat(),
            "days_left": days_left, "status": status
        })

    result.sort(key=lambda x: x["days_left"])
    return result


def get_suppliers_with_debt(db: Session, company_id: int = None) -> List[dict]:
    """Barcha yetkazib beruvchilar va ularning qarzdorligi + oxirgi xarid, oylik statistika."""
    from datetime import datetime as dt

    now = dt.utcnow()
    suppliers = get_suppliers(db, only_active=True, company_id=company_id)
    result = []
    for s in suppliers:
        debt_info = get_supplier_debt(db, s.id)

        all_purchases = db.query(InventoryPurchase).filter(
            InventoryPurchase.supplier_id == s.id
        ).order_by(InventoryPurchase.purchased_at.desc()).all()

        last_purchase_at = all_purchases[0].purchased_at.isoformat() if all_purchases else None

        month_purchases = [p for p in all_purchases
                           if p.purchased_at and p.purchased_at.year == now.year
                           and p.purchased_at.month == now.month]
        month_total = sum(float(p.total_amount) for p in month_purchases)

        result.append({
            "id": s.id,
            "name": s.name,
            "phone": s.phone,
            "notes": s.notes,
            "last_purchase_at": last_purchase_at,
            "month_count": len(month_purchases),
            "month_total": round(month_total),
            **debt_info
        })
    result.sort(key=lambda x: x["debt"], reverse=True)
    return result


def _purchase_of_company(db: Session, purchase_id: int, company_id: int = None):
    """Xaridni ota (material) orqali tekshiradi — InventoryPurchase'da
    company_id ustuni yo'q (M6, ikkilamchi himoya)."""
    q = db.query(InventoryPurchase).filter(InventoryPurchase.id == purchase_id)
    if company_id is not None:
        q = q.join(Inventory, Inventory.id == InventoryPurchase.inventory_id).filter(
            Inventory.company_id == company_id)
    return q.first()


def _xarid_son(value, nom: str, pul: bool = False) -> float:
    """21-band (2026-09-21): xarid yozuvidagi son — musbat, chekli,
    `true/false` emas, sig'imdan katta emas. Aks holda ValueError (→ 400).

    17f (2026-09-22): `pul=True` — narx (`InventoryPurchase.price_per_unit`,
    Numeric(12,2)). HAQIQIY PostgreSQL da O'LCHANGAN: narx uchun chegara
    `_UPD_SON_CHEGARA` (1e12, Float ustunlar uchun) edi, ya'ni `1e10` narx
    tekshiruvdan o'tib, COMMIT da "numeric field overflow" → 500; `0.001`
    esa 0.00 bo'lib yozilardi (jami 0.01 bilan — narx va jami bir-biriga zid).
    Endi narx — pul sig'imi ichida va kamida 1 tiyin.

    Nima uchun kerak: `schemas.PurchaseUpdate` da `Field(gt=0)` bor, lekin
    `float('inf') > 0` — ROST, ya'ni cheksizlik pydantic dan O'TADI. Tahrir
    endi OMBORGA ham ta'sir qilgani uchun (pastga qarang), cheksiz yoki
    haddan tashqari katta qiymat qoldiqni butunlay buzardi."""
    import math
    if value is None:
        raise ValueError(f"'{nom}' bo'sh bo'lishi mumkin emas")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"'{nom}' son bo'lishi kerak")
    v = float(value)
    if math.isnan(v) or math.isinf(v):
        raise ValueError(f"'{nom}' son bo'lishi kerak")
    if v <= 0:
        raise ValueError(f"'{nom}' 0 dan katta bo'lishi kerak")
    if v > (_ORDER_ITEM_MAX_MONEY if pul else _UPD_SON_CHEGARA):
        raise ValueError(f"'{nom}' juda katta")
    if pul and round(v, 2) < _PUL_ENG_KAM:
        raise ValueError(f"'{nom}' kamida {_PUL_ENG_KAM} bo'lishi kerak "
                         "(1 tiyindan kichik summa bazada 0 ga aylanadi)")
    return v


# Xarid yozuvidagi izoh — `InventoryPurchase.notes` ustuni `Text` (cheklovsiz),
# lekin cheksiz uzun matn sahifalarni va Telegram xabarlarini buzadi.
_XARID_IZOH_MAX = 1000


def _clean_xarid_tahrir(data) -> dict:
    """Marshrut tanasi (xom JSON) → {"quantity", "price_per_unit",
    "is_credit", "notes"}. Ruxsat ro'yxati + QAT'IY turlar; buzilsa
    ValueError (→ 400). 19-band dagi `_clean_stock_change` naqshi.

    Nima uchun pydantic yetarli emas: `schemas.PurchaseUpdate` "lax" rejimda
    `true` ni JIMGINA `1.0` ga o'giradi (O'LCHANGAN: `{"quantity": true}` →
    200 va qoldiq 1 ga tushardi). Tahrir endi OMBORGA ta'sir qilgani uchun
    bunday jim o'girish ombor hisobini buzardi."""
    if not isinstance(data, dict):
        raise ValueError("Noto'g'ri so'rov")
    RUXSAT = ("quantity", "price_per_unit", "is_credit", "notes")
    notogri = sorted(str(k)[:40] for k in data if k not in RUXSAT)
    if notogri:
        raise ValueError("Noma'lum maydon: " + ", ".join(notogri[:10]))

    toza = {}
    if "quantity" in data and data["quantity"] is not None:
        toza["quantity"] = _xarid_son(data["quantity"], "quantity")
    if "price_per_unit" in data and data["price_per_unit"] is not None:
        toza["price_per_unit"] = _xarid_son(data["price_per_unit"], "price_per_unit", pul=True)
    if "is_credit" in data and data["is_credit"] is not None:
        if not isinstance(data["is_credit"], bool):
            raise ValueError("'is_credit' ha/yo'q (true/false) bo'lishi kerak")
        toza["is_credit"] = data["is_credit"]
    if "notes" in data:
        izoh = data["notes"]
        if izoh is not None:
            if not isinstance(izoh, str):
                raise ValueError("'notes' matn bo'lishi kerak")
            if len(izoh) > _XARID_IZOH_MAX:
                raise ValueError(f"'notes' juda uzun ({_XARID_IZOH_MAX} belgidan ko'p)")
        toza["notes"] = izoh
    return toza


def update_purchase(db: Session, purchase_id: int, data: dict,
                   company_id: int = None) -> Optional[InventoryPurchase]:
    """Xarid yozuvini tahrirlaydi.

    21-band (2026-09-21, O'LCHANGAN — lokal `work/probe20d.py`): ilgari bu
    funksiya ATAYLAB omborga tegmasdi ("faqat tarixiy yozuv va qarz hisobi").
    Lekin `delete_purchase` o'chirishda yozuvning JORIY `quantity` sini
    ombordan ayiradi — ya'ni ikki amal bir-biriga zid edi:

        kirim 3 kg  → qoldiq 3
        tahrir 3→10 → qoldiq 3 (ombor tegilmaydi)
        o'chirish   → qoldiq −7   (to'g'risi 0 — faqat 3 kg qo'shilgan edi)

        kirim 10 kg → qoldiq 3 (oldingi holatdan)
        tahrir 10→2 → qoldiq 3
        o'chirish   → qoldiq 1    (to'g'risi −7)

    Ya'ni yo'qdan 7 kg paydo bo'lardi (yoki 8 kg yo'qolardi) — 19/20-band
    qoidasiga ("ombor va jurnal bir-biriga ZID BO'LMASIN") to'g'ridan-to'g'ri
    qarshi.

    TEXNIK YECHIM (ikki variantdan tanlandi): tahrirda FARQ omborga ham
    qo'llanadi (jurnal yozuvi bilan). Shunda "xarid yozuvidagi miqdor" =
    "shu xarid omborga qo'shgan miqdor" — invariant HAR DOIM to'g'ri, va
    `delete_purchase` ning joriy `quantity` ni ayirishi avtomatik to'g'ri
    bo'ladi. Ikkinchi variant (o'chirishda ASL kirim miqdorini saqlash)
    yangi DB ustuni + migratsiya talab qilardi va eski yozuvlar baribir
    xato qolardi; bundan tashqari ikkita "haqiqat manbai" saqlanib qolardi.

    Foydalanuvchi uchun ham shu to'g'ri: miqdor tahrirlanishining sababi —
    "kiritilgan son noto'g'ri edi", ya'ni OMBORDAGI son ham noto'g'ri.
    Ilgari UI "kerak bo'lsa Omborxonada qo'lda tuzating" derdi — endi shart
    emas (UI matni ham yangilandi).

    O'rtacha NARX tegilmaydi (o'chirishda ham tegilmaydi — bir xil qoida):
    tarixiy xarid narxi tuzatilsa, joriy o'rtacha tan narx qayta
    hisoblanmaydi. Miqdor kamaytirilib qoldiq manfiyga tushsa — 20-band
    qoidasi: manfiy ruxsat, keyingi kirimda qoplanadi."""
    # 1) HECH NARSA yozilmasdan (va obyekt qidirilmasdan) OLDIN — tana
    #    qat'iy tekshiriladi (ValueError → 400).
    toza = _clean_xarid_tahrir(data)

    p = _purchase_of_company(db, purchase_id, company_id)    # M6
    if not p:
        return None

    eski_qty = float(p.quantity or 0)

    # 17f (2026-09-22): miqdor va narx ALOHIDA chegaradan o'tsa ham, KO'PAYTMASI
    # `total_amount` (Numeric(12,2)) sig'imidan oshishi mumkin — HAQIQIY
    # PostgreSQL da O'LCHANGAN: 1e6 × 1e5 → COMMIT da 500 (17b yaratish yo'lida
    # shu tekshiruv bor edi, tahrirda yo'q edi). Faqat BITTASI berilsa, ikkinchisi
    # yozuvning joriy qiymatidan olinadi. Hech narsa o'zgartirilmasdan OLDIN.
    _yangi_qty = toza.get("quantity", float(p.quantity or 0))
    _yangi_narx = toza.get("price_per_unit", float(p.price_per_unit or 0))
    # 17g: jami YAXLITLANGAN narxdan yoziladi — sig'im ham shunga nisbatan.
    if _yangi_qty * _yangi_narx > _ORDER_ITEM_MAX_MONEY or \
            _xarid_narx_jami(_yangi_qty, _yangi_narx)[1] > _ORDER_ITEM_MAX_MONEY:
        raise ValueError("'quantity' × 'price_per_unit' juda katta "
                         "(jami summa sig'imdan oshdi)")

    # 2) Yozuvning o'zi
    if "quantity" in toza:
        p.quantity = toza["quantity"]
    if "price_per_unit" in toza:
        p.price_per_unit = toza["price_per_unit"]
    if "is_credit" in toza:
        p.is_credit = toza["is_credit"]
    if "notes" in toza:
        p.notes = toza["notes"]

    # 17g (2026-09-22): narx va jami bazadagidek yaxlitlanadi — jami SHU narxdan
    # (HAQIQIY PostgreSQL da O'LCHANGAN: tahrir 7 × 0.125 → narx 0.13, jami 0.88).
    p.price_per_unit, p.total_amount = _xarid_narx_jami(float(p.quantity),
                                                        float(p.price_per_unit))

    # 3) Ombor — FAQAT miqdor farqi (narx emas)
    farq = float(p.quantity) - eski_qty
    if p.inventory_id and abs(farq) > 1e-9:
        # QAT'IY filtr + qator qulfi (19-band `update_stock` bilan bir xil).
        # `_purchase_of_company` allaqachon materialni korxona bo'yicha
        # tekshirgan — bu ikkilamchi himoya.
        inv = get_item_locked(db, p.inventory_id, company_id)
        if inv:
            joriy = float(inv.stock_quantity or 0)
            yangi = joriy + farq
            if -1e-9 < yangi < 0:
                yangi = 0.0     # suzuvchi nuqta qoldig'i (19/20-band bilan bir xil)
            inv.stock_quantity = yangi
            try:
                log_movement(
                    db, inv.id, inv.item_name,
                    movement_type=("in" if farq > 0 else "out"),
                    quantity=abs(farq), unit=inv.unit,
                    supplier_id=p.supplier_id,
                    reason=_jurnal_sabab(
                        f"Xarid tahrirlandi — #{purchase_id}: "
                        f"{eski_qty:g} → {float(p.quantity):g} {inv.unit or ''}".rstrip() +
                        (f" ⚠️ qoldiq manfiy: {yangi:g} {inv.unit or ''} — keyingi kirimda qoplanadi"
                         if yangi < 0 else "")))
            except Exception:
                pass

    db.commit()
    db.refresh(p)
    return p


def delete_purchase(db: Session, purchase_id: int, reverse_stock: bool = True,
                   company_id: int = None) -> bool:
    """Xarid yozuvini o'chiradi.
    reverse_stock=True (standart) bo'lsa — bu xaridda qo'shilgan miqdorni
    ombordan ham QAYTARIB oladi (ya'ni to'liq bekor qiladi — ham pul oqimi,
    ham ombor). Bu, ayniqsa "boshlang'ich ombor"ni xato kirim qilib, keyin
    tuzatmoqchi bo'lganda kerak."""
    p = _purchase_of_company(db, purchase_id, company_id)    # M6
    if not p:
        return False

    if reverse_stock and p.inventory_id and p.quantity:
        inv = db.query(Inventory).filter(Inventory.id == p.inventory_id).with_for_update().first()
        if inv:
            # MUHIM (2026-09 audit): agar shu xariddan kelgan xomashyoning
            # bir qismi ALLAQACHON ishlab chiqarishda ishlatilgan bo'lsa
            # (masalan xato kiritilgan yozuvni darrov emas, biroz vaqtdan
            # keyin o'chirishsa) — bu yerda tekshiruv yo'q edi, zaxira
            # manfiyga tushib qolar edi. Boshqa joylardagi (masalan
            # update_stock()) "manfiy bo'lmasin" qoidasiga moslashtirildi.
            # 20-band (2026-09-21, FOYDALANUVCHI QARORI — "hammasi"): xarid
            # o'chirilganda qoldiq ARIFMETIK kamayadi, BARCHA materiallar
            # uchun (penoplast ham). Ilgari 0 da qirqilardi: manfiy qoldiqdagi
            # "qarz" o'chardi, ishlatilgan xariddan keyin o'chirilsa sarflangan
            # qism yo'qolardi, jurnalga esa to'liq miqdor yozilardi (ombor va
            # jurnal bir-biriga zid). Manfiy qoldiq keyingi kirimda qoplanadi
            # (`_purchase_stock_no_commit`), qo'lda chiqim esa manfiyda rad
            # etiladi (`update_stock`, 19-band).
            current = float(inv.stock_quantity or 0)
            new_qty = current - float(p.quantity)
            if -1e-9 < new_qty < 0:
                new_qty = 0.0       # suzuvchi nuqta qoldig'i (19-band bilan bir xil)
            inv.stock_quantity = new_qty
            try:
                log_movement(db, inv.id, inv.item_name, movement_type="out",
                             quantity=float(p.quantity), unit=inv.unit,
                             reason=_jurnal_sabab(
                                 f"Xarid o'chirildi (bekor qilindi) — #{purchase_id}" +
                                 (f" ⚠️ qoldiq manfiy: {new_qty:g} {inv.unit or ''} — keyingi kirimda qoplanadi"
                                  if new_qty < 0 else "")))
            except Exception:
                pass

    db.delete(p)
    db.commit()
    return True


def create_supplier_payment(db: Session, data: SupplierPaymentCreate, paid_by: str = None,
                            company_id: int = None, ichki: bool = False) -> SupplierPayment:
    """Yetkazib beruvchiga to'lov — bir nechta xaridni birdaniga yopishi mumkin.

    `ichki=True` (17g, 2026-09-22) — xarid marshruti (`POST /api/inventory/
    {id}/purchase`) "hoziroq to'langan" qismni XARID BILAN BIRGA yozganda.
    Bu holda takror-yuborish himoyasi va ortiqcha to'lov ogohlantirishi
    QO'LLANILMAYDI, chunki:
      * xarid o'zi allaqachon saqlangan (marshrut to'lovni xarid COMMIT
        qilingandan KEYIN yozadi) — O'LCHANGAN (kech23): 8 s ichida shu
        ta'minotchiga shu summada qo'lda to'lov bo'lsa, xarid 200 qaytarardi,
        lekin uning to'lovi YARATILMASDI (xarid to'liq nasiya bo'lib qolardi,
        qarz ortiqcha ko'rinardi);
      * summa marshrutda shu xarid jamisi bilan cheklangan (`min(paid_now,
        jami)`), ya'ni bu "ortiqcha to'lov" bo'lishi mumkin emas; qarz esa
        (`get_supplier_debt`) butun so'mga yaxlitlanadi va avans holatida 0 dan
        pastga tushmaydi — ogohlantirish bu yerda 409 emas, xarid saqlangandan
        keyingi 500 (yarim saqlanish) bo'lardi.
    Kirim hujjati (`create_inventory_receipt`) o'z to'lovini xuddi shu sabab
    bilan to'g'ridan yozadi. Tana va korxona tekshiruvi ikkala holda ham bor."""
    # 17c (2026-09-21): ILDIZ tekshiruvi — pydantic `Field(gt=0)` cheksizlik
    # (`Infinity`, ortiqcha to'lov tasdig'i bilan SAQLANARDI va ta'minotchilar
    # hamda qarzdorlar sahifalarini buzardi), `true` (→ 1 so'm), `"5000"`
    # matni va sig'imdan katta summani o'tkazib yuborardi (O'LCHANGAN).
    _clean_val("SupplierPayment", _val_dump(data, "SupplierPayment"))
    # M6 — TENANT: to'lov faqat SHU korxona ta'minotchisiga yozilishi mumkin.
    if company_id is not None:
        if not db.query(Supplier).filter(
                Supplier.id == data.supplier_id, Supplier.company_id == company_id).first():
            from fastapi import HTTPException as _HE_sp
            raise _HE_sp(status_code=404, detail="Yetkazib beruvchi topilmadi")
    # ── TAKROR YUBORISH HIMOYASI (buyurtma to'lovi bilan bir xil) ──────
    _pul_qulfi(db, 102, data.supplier_id)

    if not ichki:
        # TENANT: yuqoridagi bilan bir xil sabab — ta'minotchi korxonasi
        # SHU FUNKSIYANING BOSHIDA tekshirilgan (mos kelmasa 404), shuning
        # uchun bu supplier_id faqat shu korxonaniki bo'lishi mumkin.
        from datetime import timedelta as _td_sp
        _summa_sp = round(float(data.amount or 0), 2)
        _oldingi_sp = db.query(SupplierPayment).filter(
            SupplierPayment.supplier_id == data.supplier_id,
            SupplierPayment.amount == _summa_sp,
            SupplierPayment.paid_at >= datetime.utcnow() - _td_sp(seconds=PUL_TAKROR_SONIYA),
        ).order_by(SupplierPayment.paid_at.desc()).first()
        if _oldingi_sp is not None:
            _oldingi_sp._is_duplicate_submit = True
            return _oldingi_sp

        debt_info = get_supplier_debt(db, data.supplier_id, company_id=company_id)
        current_debt = debt_info["debt"]
        if float(data.amount) > current_debt and not data.confirm_overpay:
            raise OverpaymentWarning(
                amount=float(data.amount), debt=current_debt,
                excess=float(data.amount) - current_debt
            )

    p = SupplierPayment(
        supplier_id=data.supplier_id,
        amount=data.amount,
        paid_by=paid_by,
        notes=data.notes
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# kech52 (13-band, 3-qadam): ESKI (belgi yozilmagan) harakatlar uchun brak
# ta'rifi — 33 / 37-band migratsiyalari va `main._migrate_brak_belgisi` bilan
# AYNAN bir xil (yozuvga bog'langan YOKI sabab shu naqsh bilan boshlanadi).
BRAK_ESKI_NAQSH = "Brak%"


def brak_harakati_sharti(IM=None):
    """kech52 (13-band, 3-qadam) — "bu harakat brakmi" ning YAGONA SQL sharti.

    Yangi harakat — `is_brak` belgisi (sabab matnidan qat'i nazar). Belgi NULL
    (shu yangilanishdan oldin yozilgan, migratsiya hali to'ldirmagan yoki
    deploy paytida eski server yozgan) — eski ta'rif: `return_item_id` bor YOKI
    sabab "Brak%" bilan boshlanadi. Sabab NULL bo'lsa ham natija aniq True /
    False (NULL emas) — `not_(...)` bilan xavfsiz ishlatiladi.
    Chaqiruvchilar: `get_brak_material_summary` (+ "out"),
    `services._buyurtma_sarf_narxlari` (inkor)."""
    from sqlalchemy import and_ as _and_bs, or_ as _or_bs
    if IM is None:
        from models import InventoryMovement as IM
    return _or_bs(
        IM.is_brak.is_(True),
        _and_bs(IM.is_brak.is_(None),
                _or_bs(IM.return_item_id.isnot(None),
                       _and_bs(IM.reason.isnot(None), IM.reason.like(BRAK_ESKI_NAQSH)))))


def get_brak_material_summary(db: Session, start_date=None, end_date=None,
                             company_id: int = None) -> dict:
    """Brak (defekt) sabab ombordan yechilgan XOMASHYO bo'yicha xulosa.

    Qaytaradi:
    - by_material: har bir material nomi bo'yicha JAMI (barcha buyurtmalar
      birlashtirilgan) — Penoplast uchun m³ ham hisoblanadi.
    - by_order: har bir BUYURTMA bo'yicha ALOHIDA — o'sha buyurtmada qaysi
      xomashyo qancha brak bo'lganini ko'rsatadi.
    - total_value, total_penoplast_m3: umumiy jami.

    Faqat o'qish. kech46 (13-band, 2-qadam): har harakat CHIQIM paytidagi
    muzlatilgan narx (`unit_cost`) bilan baholanadi; u yo'q (eski harakat)
    bo'lsa — materialning joriy narxi (`price_per_unit`), avvalgidek.
    `by_material[].unit_price` — o'rtacha narx (qiymat / miqdor)."""
    from models import Inventory, InventoryMovement, Order

    def _harakat_narxi(harakat, inv):
        if harakat.unit_cost is not None:
            return float(harakat.unit_cost)
        return float(inv.price_per_unit or 0) if inv else 0.0

    # kech52 (13-band, 3-qadam): brak — `is_brak` belgisi (eski harakatlar —
    # eski ta'rif), sabab matni EMAS: matn o'zgarsa hisobot nolga tushmaydi.
    q = db.query(InventoryMovement).filter(
        InventoryMovement.movement_type == "out",
        brak_harakati_sharti(InventoryMovement)
    )
    if company_id is not None:      # M6
        q = q.filter(InventoryMovement.company_id == company_id)
    if start_date:
        q = q.filter(InventoryMovement.created_at >= start_date)
    if end_date:
        q = q.filter(InventoryMovement.created_at <= end_date)
    rows = q.order_by(InventoryMovement.created_at.desc()).all()

    if not rows:
        return {"by_material": [], "by_order": [], "total_value": 0, "total_penoplast_m3": 0,
                "gips_brak_value": 0, "penoplast_brak_value": 0}

    # Barcha kerakli Inventory va Order obyektlarini oldindan yuklaymiz
    inv_ids = {r.inventory_id for r in rows if r.inventory_id}
    order_ids = {r.order_id for r in rows if r.order_id}
    inv_map = {i.id: i for i in db.query(Inventory).filter(Inventory.id.in_(inv_ids)).all()} if inv_ids else {}
    order_map = {o.id: o for o in db.query(Order).filter(Order.id.in_(order_ids)).all()} if order_ids else {}

    def m3_for(inv, qty):
        """Agar bu Penoplast bo'lsa — blok sonini m³ ga aylantiradi."""
        if inv and inv.is_penoplast and inv.volume_per_unit:
            return float(qty) * float(inv.volume_per_unit)
        return 0.0

    # ── Material bo'yicha JAMI ──
    by_material_agg = {}
    total_value = 0.0
    total_m3 = 0.0
    gips_brak_value = 0.0
    penoplast_brak_value = 0.0
    for r in rows:
        inv = inv_map.get(r.inventory_id)
        price = _harakat_narxi(r, inv)
        value = float(r.quantity or 0) * price
        m3 = m3_for(inv, r.quantity)
        total_value += value
        total_m3 += m3
        if inv and (inv.category or '').lower() == 'gips':
            gips_brak_value += value
        else:
            penoplast_brak_value += value
        key = r.item_name
        if key not in by_material_agg:
            by_material_agg[key] = {"item_name": r.item_name, "quantity": 0.0, "unit": r.unit,
                                     "unit_price": price, "value": 0.0, "m3": 0.0}
        by_material_agg[key]["quantity"] += float(r.quantity or 0)
        by_material_agg[key]["value"] += value
        by_material_agg[key]["m3"] += m3

    by_material = sorted(by_material_agg.values(), key=lambda x: -x["value"])
    for m in by_material:
        # Turli narxdagi harakatlar birlashganda — o'rtacha narx
        if m["quantity"] > 0:
            m["unit_price"] = m["value"] / m["quantity"]
        m["quantity"] = round(m["quantity"], 3)
        m["value"] = round(m["value"])
        m["m3"] = round(m["m3"], 3) if m["m3"] > 0 else None

    # ── Buyurtma bo'yicha ALOHIDA ──
    by_order_agg = {}
    for r in rows:
        if not r.order_id:
            continue
        inv = inv_map.get(r.inventory_id)
        price = _harakat_narxi(r, inv)
        value = float(r.quantity or 0) * price
        m3 = m3_for(inv, r.quantity)
        if r.order_id not in by_order_agg:
            order = order_map.get(r.order_id)
            by_order_agg[r.order_id] = {
                "order_id": r.order_id,
                "order_number": order.order_number if order else f"#{r.order_id}",
                "client_name": (order.project.client_name if order and order.project else None),
                "items": [], "total_value": 0.0, "total_m3": 0.0
            }
        by_order_agg[r.order_id]["items"].append({
            "item_name": r.item_name, "quantity": round(float(r.quantity or 0), 3),
            "unit": r.unit, "value": round(value), "m3": round(m3, 3) if m3 > 0 else None,
            "date": r.created_at.isoformat() if r.created_at else None
        })
        by_order_agg[r.order_id]["total_value"] += value
        by_order_agg[r.order_id]["total_m3"] += m3

    by_order = sorted(by_order_agg.values(), key=lambda x: -x["total_value"])
    for o in by_order:
        o["total_value"] = round(o["total_value"])
        o["total_m3"] = round(o["total_m3"], 3) if o["total_m3"] > 0 else None

    return {
        "by_material": by_material,
        "by_order": by_order,
        "total_value": round(total_value),
        "total_penoplast_m3": round(total_m3, 3),
        "gips_brak_value": round(gips_brak_value),
        "penoplast_brak_value": round(penoplast_brak_value)
    }



def get_supplier_purchased_items(db: Session, supplier_id: int,
                                 company_id: int = None) -> List[dict]:
    """Shu yetkazib beruvchidan ILGARI xarid qilingan materiallar ro'yxati
    (takrorlanmas) — Kirim sahifasida qulaylik uchun, tanlov ro'yxatini
    shu yetkazib beruvchiga xos materiallar bilan cheklash uchun."""
    from models import Inventory
    # 2026-09-18 — TENANT (M7 validatsiyasida B sessiyasidan topilgan
    # HAQIQIY sizish): `company_id` parametri qabul qilinardi, lekin
    # so'rovda UMUMAN ishlatilmasdi. Natijada B korxona admini A ning
    # ta'minotchi ID sini yuborib, A ning material nomlarini o'qiy olardi
    # (supplier 1 → 11 ta, supplier 2 → 3 ta material).
    #
    # Endi UCH qatlamda cheklanadi:
    #   1) ta'minotchining o'zi shu korxonaniki bo'lishi shart,
    #   2) xaridlar ham shu korxona materiallariga tegishli bo'lishi shart,
    #   3) qaytariladigan materiallar ham shu korxonadan.
    if company_id is not None:
        if not db.query(Supplier).filter(
                Supplier.id == supplier_id, Supplier.company_id == company_id).first():
            return []

    _pq = db.query(InventoryPurchase.inventory_id).filter(
        InventoryPurchase.supplier_id == supplier_id
    )
    if company_id is not None:
        _pq = _pq.join(Inventory, Inventory.id == InventoryPurchase.inventory_id).filter(
            Inventory.company_id == company_id)
    item_ids = [r[0] for r in _pq.distinct().all()]
    if not item_ids:
        return []
    _iq = db.query(Inventory).filter(Inventory.id.in_(item_ids))
    if company_id is not None:
        _iq = _iq.filter(Inventory.company_id == company_id)
    items = _iq.all()
    return [{"id": i.id, "item_name": i.item_name, "unit": i.unit, "category": i.category} for i in items]


def get_supplier_history(db: Session, supplier_id: int, start_date=None, end_date=None,
                          page: int = 1, page_size: int = 20, company_id: int = None) -> dict:
    """Yetkazib beruvchining xaridlar va to'lovlar tarixi.
    start_date/end_date berilsa — faqat shu oraliqdagi xaridlar qaytariladi
    (to'lovlar va umumiy qarz har doim to'liq hisoblanadi).
    page/page_size — XARIDLAR ro'yxati SAHIFALANGAN holda qaytariladi
    (tarix uzoq bo'lib ketsa ham, har doim tez yuklanishi uchun)."""
    # M6 — TENANT: ta'minotchi boshqa korxonaniki bo'lsa — bo'sh tarix.
    if company_id is not None:
        if not db.query(Supplier).filter(
                Supplier.id == supplier_id, Supplier.company_id == company_id).first():
            return {"total_credit": 0, "total_paid": 0, "debt": 0, "purchase_count": 0,
                    "purchases": [], "payments": [],
                    "pagination": {"page": 1, "page_size": page_size,
                                   "total_count": 0, "total_pages": 1}}

    q = db.query(InventoryPurchase).filter(InventoryPurchase.supplier_id == supplier_id)
    if start_date:
        q = q.filter(InventoryPurchase.purchased_at >= start_date)
    if end_date:
        from datetime import timedelta
        q = q.filter(InventoryPurchase.purchased_at < end_date + timedelta(days=1))

    total_count = q.count()
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    purchases = q.order_by(InventoryPurchase.purchased_at.desc()) \
                 .offset((page - 1) * page_size).limit(page_size).all()

    payments = db.query(SupplierPayment).filter(
        SupplierPayment.supplier_id == supplier_id
    ).order_by(SupplierPayment.paid_at.desc()).all()

    debt_info = get_supplier_debt(db, supplier_id, company_id=company_id)

    return {
        **debt_info,
        "purchases": [{
            "id": p.id,
            "item_name": p.item_name,
            "quantity": float(p.quantity),
            "unit": p.unit,
            "price_per_unit": float(p.price_per_unit),
            "total_amount": float(p.total_amount),
            "is_credit": p.is_credit,
            "category": p.category or "Boshqa",
            "purchased_at": p.purchased_at.isoformat() if p.purchased_at else None,
            "purchased_by": p.purchased_by,
            "notes": p.notes
        } for p in purchases],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages
        },
        "payments": [{
            "id": pay.id,
            "amount": float(pay.amount),
            "paid_at": pay.paid_at.isoformat() if pay.paid_at else None,
            "paid_by": pay.paid_by,
            "notes": pay.notes
        } for pay in payments]
    }


def delete_supplier_payment(db: Session, payment_id: int, company_id: int = None) -> bool:
    _q = db.query(SupplierPayment).filter(SupplierPayment.id == payment_id)
    if company_id is not None:      # M6: ota (ta'minotchi) orqali
        _q = _q.join(Supplier, Supplier.id == SupplierPayment.supplier_id).filter(
            Supplier.company_id == company_id)
    p = _q.first()
    if not p:
        return False
    db.delete(p)
    db.commit()
    return True
