"""
PenoDecorPro ERP — Biznes mantiqi (Services)
==============================================
Avtomatik hisob-kitob va ishlab chiqarish nazorati.

Asosiy funksiyalar: minimal qoldiq ogohlantirishi (`check_low_stock`), buyurtmani yakunlash (`complete_order`),
buyurtma foydasi (`calculate_order_profit`), oylik hisobot va usta KPI. (kech103, 55-band: eski "1–3" bo'limlar —
`check_admin_role`, `process_cutting`, `calculate_coating_materials`, `process_coating` — o'lik edi, olib tashlandi.)
"""

from typing import List, Optional, Dict
from sqlalchemy.orm import Session
# kech105 (9 + 50-band): Toshkent kalendari yordamchilari — `database.py` (hisobot kun / oy / yil chegarasi)
from database import tashkent_date as _tashkent_date, tashkent_oyida as _tashkent_oyida, tashkent_kun_oraligi as _tashkent_kun_oraligi, tashkent_oy_oraligi as _tashkent_oy_oraligi

from models import (
    Inventory, Recipe, Order, OrderItem,
    Master, OrderStatus
)


# ============================================================
# kech103 (5-bo'lim 55-band, 18-band o'lik kod auditi): bu yerdagi eski "1. ADMIN NAZORATI", "2. AVTOMATIK KESISH",
# "3. AVTOMATIK QOPLAMA" yordamchilari (`check_admin_role`, `process_cutting`, `calculate_coating_materials`,
# `process_coating`) OLIB TASHLANDI: loyiha bo'ylab chaqiruvchisi yo'q edi (grep — `.py` / `.html` / `.js`), materialni
# NOMI bo'yicha (`ilike`) korxona filtrisiz qidirib ombordan yechardi (tenant lint baseline 4 yozuvi). Kesish / qoplama
# xomashyosi buyurtma yaratish / «Tayyor» yo'llarida (`deduct_*`, `complete_order`) hisoblanadi.
# ============================================================


# ============================================================
# 4. MINIMAL QOLDIQ OGOHLANTIRISHI
# ============================================================

# kech118 (B — U-05 / U-06): foydalanuvchiga ko'rinadigan matndagi son — kasr VERGUL bilan («-156,4»; brauzerdagi `sonKor`
# bilan bir qoida); grafik oy nomlari — o'zbekcha qisqa (ilgari `strftime("%b")` — «Sep 2026», kirillda «Сеп» emas «Sep»).
_OY_QISQA = ("Yan", "Fev", "Mar", "Apr", "May", "Iyun", "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek")


def _son_uz(x) -> str:
    # `:g` ko'rinishi (ortiqcha nolsiz), kasr — vergul: -156.4 → «-156,4», 12.0 → «12»
    return f"{x:g}".replace(".", ",")


def son_korinish(qiymat, kasr=2) -> str:
    """kech119 (G2-15 — B bosqichi U-05 qoidasi serverdagi MATNLARDA): son KO'RINISHI — `main._son_filtri` (Jinja `|son`)
    va brauzerdagi `sonKor` bilan BIR qoida: ming ajratgich — bo'sh joy (NBSP), kasr — vergul, ortiqcha nolsiz, ko'pi
    bilan `kasr` xona («572 947», «0,02», «200», «1 234,5»). Ilgari foyda tafsilotida «572,947 so'm/m³» (vergul — ming
    ajratgich, aslida 572 947) va «0.02 m³» / «200.0 kg» (nuqtali kasr) edi. Qiymat yo'q / son emas — «—»."""
    try:
        x = float(qiymat)
    except (TypeError, ValueError):
        return "—"
    if x != x or x in (float("inf"), float("-inf")):
        return "—"
    s = f"{x:,.{max(int(kasr), 0)}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    s = s.replace(",", "\u00a0").replace(".", ",")
    return "0" if s in ("-0", "") else s


def get_top_products_report(db: Session, days: int = 90, limit: int = 15,
                            company_id: int = None) -> list:
    """Eng ko'p daromad keltirgan mahsulotlar — nomi bo'yicha guruhlangan,
    tayyor (READY/DELIVERED) buyurtmalardagi OrderItem'lardan. Faqat o'qish.

    ⚠ 2026-09-21: `company_id` YO'Q edi — B korxona admini `/api/reports/
    top-products` orqali A korxonaning mahsulot nomlari va daromadini
    ko'rardi (HTTP da o'lchangan). Yonidagi `get_top_materials_report`
    da filtr bor edi, bu yerda tushib qolgan."""
    from models import OrderItem, Order, OrderStatus
    from sqlalchemy import func
    from datetime import datetime, timedelta

    period_start = datetime.utcnow() - timedelta(days=days)
    _q = db.query(
        OrderItem.name,
        func.sum(OrderItem.total_price).label("revenue"),
        func.sum(OrderItem.quantity).label("qty"),
        func.count(OrderItem.id).label("times_ordered")
    ).join(Order, OrderItem.order_id == Order.id)
    if company_id is not None:
        _q = _q.filter(Order.company_id == company_id)
    rows = _q.filter(
        # kech76 (97-band, QAROR B — 91-band): hisobotga FAQAT hodim "Tayyor" bosgan (READY) buyurtma
        # kiradi — oylik hisobot / usta KPI bilan bir xil. Ilgari DELIVERED ham sanalardi: to'liq
        # yetkazilgan, lekin "Tayyor" bosilmagan buyurtma shu ro'yxatda bor, oylik hisobotda yo'q edi.
        Order.status == OrderStatus.READY,
        Order.completed_at >= period_start
    ).group_by(OrderItem.name).order_by(func.sum(OrderItem.total_price).desc()).limit(limit).all()

    return [{
        "name": r.name,
        "revenue": round(float(r.revenue or 0)),
        "quantity": round(float(r.qty or 0), 1),
        "times_ordered": r.times_ordered,
    } for r in rows]


def get_top_finished_products_sold(db: Session, days: int = 30, limit: int = 5,
                                   company_id: int = None) -> list:
    """Dashboard uchun — FAQAT 'Tayyor mahsulotlar' bo'limidan sotilgan
    tovarlar (OrderItem.finished_product_id to'ldirilgan, ya'ni buyurtma
    tayyor ombordan berilgan — maxsus buyurtma qilingan detal EMAS).
    Qaytarilgan miqdor (ReturnItem) — nomi va buyurtma ID'si bo'yicha
    moslashtirilib, sotilgan miqdordan AYRIB tashlanadi. Faqat o'qish.

    kech78 (98-band): `company_id` YO'Q edi — marshrut korxonasiz chaqirardi, `TENANT_FILTER`
    o'chiq bo'lsa B korxona admini A ning tayyor mahsulot sotuvlarini (nomi va summasi) ko'rardi
    (O'LCHANDI, work/probe98.py). Endi `get_top_products_report` dagi kabi: berilsa buyurtma VA
    qaytarish so'rovi shu korxona bilan cheklanadi (global filtrga tayanmasdan)."""
    from models import OrderItem, Order, OrderStatus, ReturnItem
    from sqlalchemy import func
    from datetime import datetime, timedelta

    period_start = datetime.utcnow() - timedelta(days=days)

    sold_rows = db.query(
        OrderItem.name,
        OrderItem.order_id,
        func.sum(OrderItem.total_price).label("revenue"),
        func.sum(OrderItem.quantity).label("qty")
    ).join(Order, OrderItem.order_id == Order.id).filter(
        OrderItem.finished_product_id.isnot(None),
        # kech76 (97-band, QAROR B — 91-band): hisobotga FAQAT hodim "Tayyor" bosgan (READY) buyurtma
        # kiradi — oylik hisobot / usta KPI bilan bir xil. Ilgari DELIVERED ham sanalardi: to'liq
        # yetkazilgan, lekin "Tayyor" bosilmagan buyurtma shu ro'yxatda bor, oylik hisobotda yo'q edi.
        Order.status == OrderStatus.READY,
        Order.completed_at >= period_start
    )
    if company_id is not None:
        sold_rows = sold_rows.filter(Order.company_id == company_id)
    sold_rows = sold_rows.group_by(OrderItem.name, OrderItem.order_id).all()

    # Qaytarishlarni (nomi + buyurtma bo'yicha) yig'amiz, keyin ayiramiz
    returns = db.query(
        ReturnItem.item_name, ReturnItem.order_id,
        func.sum(ReturnItem.quantity).label("ret_qty")
    ).filter(ReturnItem.returned_at >= period_start)
    if company_id is not None:
        returns = returns.filter(ReturnItem.company_id == company_id)
    returns = returns.group_by(ReturnItem.item_name, ReturnItem.order_id).all()
    returned_map = {(r.item_name, r.order_id): float(r.ret_qty or 0) for r in returns}

    totals = {}
    for r in sold_rows:
        qty = float(r.qty or 0)
        revenue = float(r.revenue or 0)
        ret_qty = returned_map.get((r.name, r.order_id), 0)
        if ret_qty > 0 and qty > 0:
            # Qaytgan ulushga mos ravishda, daromadni ham proportsional kamaytiramiz
            keep_ratio = max(0, (qty - ret_qty) / qty)
            qty = qty * keep_ratio
            revenue = revenue * keep_ratio

        if r.name not in totals:
            totals[r.name] = {"name": r.name, "revenue": 0.0, "quantity": 0.0, "times_ordered": 0}
        totals[r.name]["revenue"] += revenue
        totals[r.name]["quantity"] += qty
        totals[r.name]["times_ordered"] += 1

    result = sorted(totals.values(), key=lambda x: x["revenue"], reverse=True)[:limit]
    for r in result:
        r["revenue"] = round(r["revenue"])
        r["quantity"] = round(r["quantity"], 1)
    return result


def get_top_materials_report(db: Session, days: int = 90, limit: int = 15,
                             company_id: int = None) -> list:
    """Eng ko'p ishlatilgan (chiqim bo'lgan) xomashyolar — InventoryMovement
    jurnalidan, nomi bo'yicha guruhlangan. Faqat o'qish."""
    from models import InventoryMovement
    from sqlalchemy import func
    from datetime import datetime, timedelta

    period_start = datetime.utcnow() - timedelta(days=days)
    rows = db.query(
        InventoryMovement.item_name,
        InventoryMovement.unit,
        func.sum(InventoryMovement.quantity).label("total_qty"),
        func.count(InventoryMovement.id).label("movement_count")
    ).filter(
        *([InventoryMovement.company_id == company_id] if company_id is not None else []),
        InventoryMovement.movement_type == "out",
        InventoryMovement.created_at >= period_start
    ).group_by(InventoryMovement.item_name, InventoryMovement.unit).order_by(func.sum(InventoryMovement.quantity).desc()).limit(limit).all()

    return [{
        "item_name": r.item_name,
        "unit": r.unit,
        "total_qty": round(float(r.total_qty or 0), 2),
        "movement_count": r.movement_count,
    } for r in rows]


def get_top_customers_report(db: Session, days: int = 90, limit: int = 10, company_id: int = None) -> list:
    """Eng ko'p daromad keltirgan mijozlar (loyihalar) — tayyor buyurtmalar
    bo'yicha, mijoz nomi bo'yicha guruhlangan. Faqat o'qish."""
    from models import Order, Project, OrderStatus
    from sqlalchemy import func
    from datetime import datetime, timedelta

    period_start = datetime.utcnow() - timedelta(days=days)
    rows = db.query(
        Project.client_name,
        func.sum(func.coalesce(Order.agreed_amount, Order.total_amount, 0)).label("revenue"),
        func.count(Order.id).label("orders_count")
    ).join(Project, Order.project_id == Project.id).filter(
        # kech76 (97-band, QAROR B — 91-band): hisobotga FAQAT hodim "Tayyor" bosgan (READY) buyurtma
        # kiradi — oylik hisobot / usta KPI bilan bir xil. Ilgari DELIVERED ham sanalardi: to'liq
        # yetkazilgan, lekin "Tayyor" bosilmagan buyurtma shu ro'yxatda bor, oylik hisobotda yo'q edi.
        Order.status == OrderStatus.READY,
        Order.completed_at >= period_start,
        *( [Order.company_id == company_id] if company_id is not None else [] )   # M6
    ).group_by(Project.client_name).order_by(func.sum(func.coalesce(Order.agreed_amount, Order.total_amount, 0)).desc()).limit(limit).all()

    return [{
        "client_name": r.client_name,
        "revenue": round(float(r.revenue or 0)),
        "orders_count": r.orders_count,
    } for r in rows]


def get_top_suppliers_report(db: Session, days: int = 90, limit: int = 10, company_id: int = None) -> list:
    """Eng ko'p xarid qilingan yetkazib beruvchilar — xarid summasi bo'yicha.
    Faqat o'qish."""
    from models import InventoryPurchase, Supplier
    from sqlalchemy import func
    from datetime import datetime, timedelta

    period_start = datetime.utcnow() - timedelta(days=days)
    rows = db.query(
        Supplier.name,
        func.sum(InventoryPurchase.total_amount).label("total"),
        func.count(InventoryPurchase.id).label("purchase_count")
    ).join(Supplier, InventoryPurchase.supplier_id == Supplier.id).filter(
        InventoryPurchase.purchased_at >= period_start,
        *( [Supplier.company_id == company_id] if company_id is not None else [] )  # M6
    ).group_by(Supplier.name).order_by(func.sum(InventoryPurchase.total_amount).desc()).limit(limit).all()

    return [{
        "supplier_name": r.name,
        "total": round(float(r.total or 0)),
        "purchase_count": r.purchase_count,
    } for r in rows]


def get_monthly_comparison(db: Session, year: int, month: int, company_id: int = None) -> dict:
    """Joriy oyni o'tgan oy bilan solishtiradi — Daromad, Xarajat, Sof foyda,
    Rentabellik. Mavjud get_monthly_report()dan foydalanadi, hech qanday
    yangi hisob-kitob qoidasi kiritmaydi — faqat ikkita natijani solishtiradi.

    101-band (kech79, O'LCHANGAN): company_id berilmasa get_monthly_report
    HAMMA korxonalarning yig'indisini qaytaradi — marshrut uni DOIM uzatadi
    (None — faqat orqaga moslik / platforma darajasi)."""
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1

    # kech119 (egasi QARORI 2026-10-01 «Shu kunlar bilan», O'LCHANGAN — sinov sayti 01.10: oktabrning 1 kuni butun
    # sentabr bilan solishtirilib «Daromad 100% kamaydi» chiqardi): JORIY (Toshkent) oy hali tugamagan — o'tgan oyning
    # SHU KUNLARI (1–N) bilan solishtiriladi (`database.tashkent_oy_kesimi` — oylik hisobotning o'zi, faqat davr oxiri
    # N-kun oxirida). Joriy oy — oylik hisobotning o'zi (kartalardagi raqam bilan AYNAN). O'tgan oy N kundan qisqa
    # (31-mart ↔ fevral) yoki so'ralgan oy tugagan — to'liq oy bilan (avvalgidek).
    import calendar as _calendar_kesim
    from database import tashkent_oy_kesimi as _tashkent_oy_kesimi
    _bugun = _tashkent_date()
    _kesim_kun = None
    if (year, month) == (_bugun.year, _bugun.month) and _bugun.day < _calendar_kesim.monthrange(prev_year, prev_month)[1]:
        _kesim_kun = _bugun.day

    current = get_monthly_report(db, year, month, company_id=company_id)
    if _kesim_kun is None:
        previous = get_monthly_report(db, prev_year, prev_month, company_id=company_id)
    else:
        with _tashkent_oy_kesimi(prev_year, prev_month, _kesim_kun):
            previous = get_monthly_report(db, prev_year, prev_month, company_id=company_id)

    # kech115 (G1-01, O'LCHANGAN — audit bazasi: o'tgan oy 0 → change_pct DOIM 100.0 — zarar oyida ham «Sof foyda 100 %
    # oshdi»; ikkalasi 0 — «0 % oshdi»): o'tgan oy 0 bo'lsa foiz YO'Q (None), `holat` — «malumot_yoq» / «ozgarmadi» /
    # «oshdi» / «kamaydi» (sahifa matni shundan; ishora bo'yicha — foiz yaxlitlangani uchun emas).
    def pct_change(cur, prev):
        if not prev:
            return None
        return round((cur - prev) / abs(prev) * 100, 1)

    def holat(cur, prev):
        if not prev:
            return "ozgarmadi" if not cur else "malumot_yoq"
        if cur == prev:
            return "ozgarmadi"
        return "oshdi" if cur > prev else "kamaydi"

    metrics = ["daromad", "jami_xarajat", "sof_foyda", "foyda_foiz"]
    comparison = {}
    for m in metrics:
        cur_val = float(current.get(m, 0) or 0)
        prev_val = float(previous.get(m, 0) or 0)
        comparison[m] = {
            "current": cur_val,
            "previous": prev_val,
            "change_pct": pct_change(cur_val, prev_val),
            "holat": holat(cur_val, prev_val),
        }
    # kech119: solishtirish DAVRI — sahifa matni shundan («1–10-sentabrga nisbatan» / «o'tgan oyga nisbatan»).
    comparison["davr"] = taqqoslash_davri(year, month, prev_year, prev_month, _kesim_kun)
    return comparison


_OY_KICHIK = ("yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr",
              "dekabr")


def kesim_davr_nomi(yil: int, oy: int, kun) -> str:
    """kech119: davr nomi — «1-sentabr» (bir kun), «1–10-sentabr» (oyning shu kunlari); `kun` None — oy nomi
    («sentabr»). Yilsiz — solishtirish doim joriy va o'tgan oy («1–10-yanvar ↔ 1–10-dekabr»)."""
    if kun is None:
        return _OY_KICHIK[int(oy) - 1]
    return f"1-{_OY_KICHIK[int(oy) - 1]}" if int(kun) == 1 else f"1–{int(kun)}-{_OY_KICHIK[int(oy) - 1]}"


def taqqoslash_davri(yil: int, oy: int, oldingi_yil: int, oldingi_oy: int, kesim_kun) -> dict:
    """kech119 (egasi QARORI «Shu kunlar bilan»): solishtirish davri — `kesim_kun` (1–N, joriy oy tugamagan) yoki None
    (to'liq oy). `joriy_nom` / `oldingi_nom` — sahifa matni uchun («1–10-oktabr» ↔ «1–10-sentabr»)."""
    return {
        "yil": int(yil), "oy": int(oy), "oldingi_yil": int(oldingi_yil), "oldingi_oy": int(oldingi_oy),
        "kun_gacha": kesim_kun, "toliq_oy": kesim_kun is None,
        "joriy_nom": kesim_davr_nomi(yil, oy, kesim_kun),
        "oldingi_nom": kesim_davr_nomi(oldingi_yil, oldingi_oy, kesim_kun),
    }


# kech119 (K119-1): bashoratda BIR MARTA hisoblanadigan (oyiga bir to'lanadigan) «doimiy» xarajat turkumlari; «tushlik» —
# kunlik (kunlik o'rtacha bilan, boshqa xarajatlar kabi).
FORECAST_OYLIK_TOIFALAR = ("arenda", "elektr", "soliqlar")


def get_simple_forecast(db: Session, year: int, month: int, company_id: int = None) -> dict:
    """Oddiy statistik bashorat — shu oyning HOZIRGACHA bo'lgan kunlik
    o'rtachasi asosida, oy oxirigacha taxminiy natijani hisoblaydi.
    Bu — sun'iy intellekt emas, oddiy chiziqli ekstrapolyatsiya."""
    import calendar

    now = _tashkent_date()        # kech105 (9 + 50-band): joriy oy / kun — Toshkent kalendari
    days_in_month = calendar.monthrange(year, month)[1]

    if year == now.year and month == now.month:
        days_passed = now.day
    elif (year, month) < (now.year, now.month):
        days_passed = days_in_month  # O'tgan oy — to'liq
    else:
        days_passed = 0  # Kelajak oy — hali ma'lumot yo'q

    # 101-band (kech79): korxona get_monthly_report ga uzatiladi (get_monthly_comparison izohi).
    report = get_monthly_report(db, year, month, company_id=company_id)

    if days_passed <= 0:
        return {"available": False, "message": "Bu oy uchun hali ma'lumot yo'q"}

    # kech119 (K119-1, O'LCHANGAN — sinov sayti 01.10.2026: «Taxminiy sof foyda −573 500 000 so'm»): OYLIK (butun oy
    # uchun bir marta yoziladigan) xarajatlar — hodimlarning doimiy oyligi (18,5 mln, oyning 1-kunidan to'liq) — kunlik
    # o'rtachaga qo'shilib oy kunlariga KO'PAYTIRILARDI (1-kuni × 31). Endi: oylik xarajat BIR MARTA, qolgani (daromad,
    # tannarx, kunlik xarajatlar, foizli / birlikli to'lovlar) — kunlik o'rtacha × oy kunlari.
    # Oylik xarajat = oyiga bir marta to'lanadigan arenda, elektr, soliq (`xarajatlar` — shu oy yozilgani; tushlik —
    # KUNLIK, sinov saytida sentabr: 1 424 000 kunlik yozuvlardan — o'rtacha bilan) + hodimlarning ish hajmiga
    # bog'liq bo'lmagan to'lovi: `calculate_monthly_employee_pay` faoliyatsiz (sotuv / foyda / metr / dona / blok /
    # qoplama — 0) — doimiy oylik, qo'shimcha oylik, bonus va kamaytirish (`get_company_obligations_status` izohi —
    # o'sha chaqiruv faqat doimiy qismni beradi). O'tgan oy (to'liq) — natija AYNAN sof foyda.
    _sof = float(report.get("sof_foyda", 0) or 0)
    _x = report.get("xarajatlar") or {}
    _hodim_doimiy = calculate_monthly_employee_pay(db, year, month, 0.0, 0.0, 0.0, 0.0, 0.0,
                                                   jami_qoplama_birlik=0.0, company_id=company_id)
    doimiy_xarajat = (sum(float(_x.get(_k, 0) or 0) for _k in FORECAST_OYLIK_TOIFALAR)
                      + float(_hodim_doimiy.get("total", 0) or 0))

    daromad_kunlik = float(report.get("daromad", 0) or 0) / days_passed
    foyda_kunlik = (_sof + doimiy_xarajat) / days_passed

    return {
        "available": True,
        "days_passed": days_passed,
        "days_in_month": days_in_month,
        "forecast_daromad": round(daromad_kunlik * days_in_month),
        "forecast_foyda": round(foyda_kunlik * days_in_month - doimiy_xarajat),
        "current_daromad": round(float(report.get("daromad", 0) or 0)),
        "current_foyda": round(_sof),
        # kech119: bir marta hisoblangan oylik xarajat (sahifa izohi uchun)
        "doimiy_xarajat": round(doimiy_xarajat),
    }


def get_business_alerts(db: Session, company_id: int = None) -> list:
    """Muhim ogohlantirishlar ro'yxati — oddiy, aniq belgilangan
    chegaralar asosida. Faqat o'qish, hech narsani o'zgartirmaydi."""
    from models import Inventory, Order, OrderStatus
    from datetime import datetime
    from database import tashkent_date

    alerts = []

    # 1) Kam qolgan xomashyo (min_stock dan kam)
    # kech37 (21-band, foydalanuvchi qarori: "Ortgan loy uchun chegara shart
    # emas"): "Tayyor loy (...)" zaxirasi (`TAYYOR_LOY_PREFIKS` izohi) hech
    # qachon "kamaymoqda" deb chiqmaydi — hatto unga min > 0 qo'yilgan bo'lsa ham.
    # kech108 (K108-2, egasi qarori "Ha, ko'rinsin"): YAGONA shart `crud.kam_qoldiq_sharti` — minimal qoldig'i
    # belgilanmagan material TUGASA ham chiqadi (ilgari `min_stock > 0` SHART edi).
    import crud as _crud_kq
    _lsq = db.query(Inventory).filter(*_crud_kq.kam_qoldiq_sharti())
    if company_id is not None:      # M6
        _lsq = _lsq.filter(Inventory.company_id == company_id)
    low_stock = _lsq.all()
    for item in low_stock[:5]:
        _q = float(item.stock_quantity or 0)
        alerts.append({
            "level": "red",
            "text": (f"Omborda {item.item_name} tugadi ({_q:g} {item.unit})" if _q <= 0
                     else f"Omborda {item.item_name} kamaymoqda ({_q:g} {item.unit} qoldi)")
        })

    # 2) Muddati o'tgan qarzdorlar (30+ kun oldin yaratilgan, hali qarzi bor)
    from sqlalchemy.orm import selectinload as _sil_ba
    # kech100 (134-band, QAROR "A"): o'chirilgan, lekin hisobotda qolgan qarzdor HAM (Qarzdorlar bilan bir shart)
    import crud as _crud_qz134
    _odq = db.query(Order).filter(
        _crud_qz134.qarz_hisobidagi_buyurtma_sharti(),
        Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED, OrderStatus.IN_PROGRESS])
    )
    if company_id is not None:      # M6
        _odq = _odq.filter(Order.company_id == company_id)
    # kech97 (116-band): qarz (to'lovlar) buyurtma boshiga so'ralardi — endi bitta IN so'rovi.
    old_debt_orders = _odq.options(_sil_ba(Order.payments)).all()
    overdue_count = 0
    for o in old_debt_orders:
        if float(o.debt_amount or 0) > 0 and o.created_at and (datetime.utcnow() - o.created_at).days > 30:
            overdue_count += 1
    if overdue_count > 0:
        alerts.append({"level": "red", "text": f"{overdue_count} ta qarzdorning muddati 30 kundan oshgan"})

    # 3) Bugungi savdo rekord (oxirgi 30 kunning eng yuqorisi)
    today_summary = get_daily_finance_summary(db, tashkent_date(), company_id=company_id)
    if today_summary["sales"]["total"] > 0:
        alerts.append({"level": "green", "text": f"Bugun {today_summary['sales']['orders_count']} ta buyurtma yakunlandi"})

    priority = {"red": 0, "orange": 1, "green": 2}
    alerts.sort(key=lambda a: priority.get(a["level"], 3))
    return alerts


def get_business_health(db: Session, company_id: int = None) -> dict:
    """6 ta asosiy ko'rsatkich bo'yicha oddiy holat (yashil/sariq/qizil).
    Chegaralar oddiy, tushunarli qoidalarga asoslangan. Faqat o'qish."""
    from models import Order

    now = _tashkent_date()        # kech105 (9 + 50-band): joriy oy — Toshkent kalendari
    report = get_monthly_report(db, now.year, now.month, company_id=company_id)

    foyda_foiz = float(report.get("foyda_foiz", 0) or 0)
    rentabellik_status = "green" if foyda_foiz >= 15 else ("orange" if foyda_foiz >= 5 else "red")

    from sqlalchemy.orm import selectinload as _sil_bh
    # kech100 (134-band, QAROR "A"): qarz ulushi — Qarzdorlar bilan bir shart (o'chirilgan READY / DELIVERED HAM)
    import crud as _crud_qz134
    _bhq = db.query(Order).filter(_crud_qz134.qarz_hisobidagi_buyurtma_sharti())
    if company_id is not None:      # M6
        _bhq = _bhq.filter(Order.company_id == company_id)
    orders = _bhq.options(_sil_bh(Order.payments)).all()     # kech97 (116-band): to'lovlar bitta IN so'rovi
    total_debt = sum(float(o.debt_amount or 0) for o in orders)
    total_revenue = sum(o.kelishilgan_summa for o in orders) or 1
    debt_ratio = total_debt / total_revenue * 100
    debt_status = "green" if debt_ratio < 15 else ("orange" if debt_ratio < 30 else "red")

    # kech115 (G1-06, O'LCHANGAN — audit: «Ombor» va «Ishlab chiqarish» kodda DOIM "green" edi — Katta korxonada tepada
    # «Material 018 tugadi», pastda «Ombor — Yaxshi»; yangi (bo'sh) korxonaga birinchi kuniyoq qizil «Rentabellik —
    # Muammoli»). Endi: ombor — kam / tugagan materiallar soni (`crud.kam_qoldiq_sharti` — hamma joydagi YAGONA qoida);
    # ishlab chiqarish — muddati o'tgan (tugallanmagan) buyurtmalar soni; ma'lumot yo'q bo'lsa — "gray" («Ma'lumot
    # yetarli emas»); har bahoning sababi — `sabablar` (bir qator, sahifada ko'rinadi).
    from models import Inventory as _Inv_bh, OrderStatus as _OS_bh
    from database import tashkent_today_start_utc as _bugun_bh
    _iq = db.query(_Inv_bh).filter(_Inv_bh.is_deleted.isnot(True), ~_Inv_bh.item_name.like("Tayyor loy (%"))
    if company_id is not None:
        _iq = _iq.filter(_Inv_bh.company_id == company_id)
    _mat_soni = _iq.count()
    _kam = _iq.filter(*_crud_qz134.kam_qoldiq_sharti()).all()
    _tugagan = sum(1 for _m in _kam if float(_m.stock_quantity or 0) <= 0)
    _faqat_kam = len(_kam) - _tugagan
    if _mat_soni == 0:
        ombor_status, ombor_sabab = "gray", "Omborda material yo'q"
    elif _tugagan > 0:
        ombor_status = "red"
        ombor_sabab = f"{_tugagan} ta material tugagan" + (f", {_faqat_kam} tasi kam" if _faqat_kam else "")
    elif _faqat_kam > 0:
        ombor_status, ombor_sabab = "orange", f"{_faqat_kam} ta material kam qolgan"
    else:
        ombor_status, ombor_sabab = "green", f"Hammasi yetarli ({_mat_soni} ta material)"

    _faol = db.query(Order).filter(
        Order.is_deleted.isnot(True), Order.is_archived.isnot(True),
        Order.status.in_([_OS_bh.NEW, _OS_bh.IN_PROGRESS, _OS_bh.COATING]))
    if company_id is not None:
        _faol = _faol.filter(Order.company_id == company_id)
    _faol_soni = _faol.count()
    _kechikkan = _faol.filter(Order.deadline.isnot(None), Order.deadline < _bugun_bh()).count()
    if _faol_soni == 0:
        ishlab_status, ishlab_sabab = "gray", "Jarayondagi buyurtma yo'q"
    elif _kechikkan >= 3:
        ishlab_status, ishlab_sabab = "red", f"{_kechikkan} ta buyurtmaning muddati o'tgan ({_faol_soni} tadan)"
    elif _kechikkan > 0:
        ishlab_status, ishlab_sabab = "orange", f"{_kechikkan} ta buyurtmaning muddati o'tgan ({_faol_soni} tadan)"
    else:
        ishlab_status, ishlab_sabab = "green", f"{_faol_soni} ta buyurtma — muddati o'tgani yo'q"

    _daromad = float(report.get("daromad", 0) or 0)
    _jami_x = float(report.get("jami_xarajat", 0) or 0)
    _naqd_x = float(report.get("naqd_xarajat_jami", 0) or 0)
    _malumot = bool(_daromad or _jami_x or _naqd_x)
    # kech116 (G1-03 — egasi QARORI kech114 «Pul oqimi — haqiqiy pul»; audit: 13.4 mln tushgan kuni «Pul oqimi — Yaxshi,
    # 0 so'm» — baho sof foyda ishorasidan edi): baho — shu oyning HAQIQIY pul harakati (`get_pul_oqimi` — Hisobotlar,
    # Moliya, Dashboard bilan BITTA qoida). Kirim ≥ chiqim — yashil; chiqim ko'p, lekin kassada pul bor — sariq (masalan
    # katta xomashyo xaridi oyi); chiqim ko'p va kassa ham manfiy — qizil; harakat yo'q — kulrang.
    _po = get_pul_oqimi(db, now.year, now.month, company_id=company_id)
    _po_farq = f"{abs(float(_po['balans'])):,.0f}".replace(",", " ") + " so'm"
    if not _po.get("harakat_bor"):
        pul_status, pul_sabab = "gray", "Bu oy pul harakati hali yo'q"
    elif float(_po["balans"]) >= 0:
        pul_status, pul_sabab = "green", f"Bu oy kirim chiqimdan {_po_farq} ko'p"
    else:
        _kassa = float(get_cash_balance(db, company_id=company_id).get("balance") or 0)
        if _kassa >= 0:
            pul_status, pul_sabab = "orange", f"Bu oy chiqim kirimdan {_po_farq} ko'p (kassada pul bor)"
        else:
            pul_status, pul_sabab = "red", f"Bu oy chiqim kirimdan {_po_farq} ko'p, kassa ham manfiy"
    # kech116 (K115-2, JONLI topilgan — kech115: qizil kartada «Rentabellik -8.4 % (yaxshi — 15 % dan yuqori)»): sabab
    # matni HOLATGA qarab — chegara bilan birga; baho va matn BITTA (ko'rsatilgan, 1 xonagacha yaxlitlangan) sondan.
    if _daromad <= 0:
        rentabellik_status, rent_sabab = "gray", "Bu oy daromad yo'q — rentabellik hisoblanmaydi"
    else:
        rent_sabab = f"Rentabellik {_son_uz(foyda_foiz)} % — " + {
            "green": "yaxshi (15 % va undan yuqori)",
            "orange": "o'rtacha (5–15 %)",
            "red": "past (5 % dan kam)",
        }[rentabellik_status]
    if not orders:
        debt_status, qarz_sabab = "gray", "Qarz hisobidagi buyurtma yo'q"
    else:
        _qarz_foiz = round(debt_ratio, 1)
        debt_status = "green" if _qarz_foiz < 15 else ("orange" if _qarz_foiz < 30 else "red")
        qarz_sabab = f"Qarz — sotuvning {_son_uz(_qarz_foiz)} % — " + {
            "green": "yaxshi (15 % dan kam)",
            "orange": "o'rtacha (15–30 %)",
            "red": "yuqori (30 % va undan ko'p)",
        }[debt_status]
    if not _malumot:
        sarf_status, sarf_sabab = "gray", "Bu oy xarid va daromad hali yo'q"
    else:
        sarf_status = "orange" if _naqd_x > (_daromad or 1) * 0.5 else "green"
        sarf_sabab = "Xomashyo xaridi daromadning yarmidan " + ("ko'p" if sarf_status == "orange" else "kam")

    return {
        "pul_oqimi": pul_status,
        "ombor": ombor_status,
        "rentabellik": rentabellik_status,
        "qarzdorlik": debt_status,
        "ishlab_chiqarish": ishlab_status,
        "material_sarfi": sarf_status,
        # kech115 (G1-06): har bahoning sababi (sahifa kartada ko'rsatadi)
        "sabablar": {
            "pul_oqimi": pul_sabab, "ombor": ombor_sabab, "rentabellik": rent_sabab,
            "qarzdorlik": qarz_sabab, "ishlab_chiqarish": ishlab_sabab, "material_sarfi": sarf_sabab,
        },
    }


def get_recurring_obligations(db: Session, company_id: int = None) -> list:
    """Barcha sozlangan doimiy majburiyatlar (Arenda, Soliq, Transport va
    ISTALGAN boshqa kategoriya) ro'yxati — sozlash sahifasi uchun."""
    from models import RecurringObligation
    _rq = db.query(RecurringObligation)
    if company_id is not None:      # M6
        _rq = _rq.filter(RecurringObligation.company_id == company_id)
    rows = _rq.order_by(RecurringObligation.label).all()
    return [{
        "id": r.id, "category": r.category, "label": r.label, "icon": r.icon or "📦",
        "monthly_target": float(r.monthly_target or 0), "due_day": r.due_day or 5,
        "is_active": r.is_active
    } for r in rows]


def set_recurring_obligation(db: Session, category: str, label: str, monthly_target: float,
                              icon: str = "📦", due_day: int = 5, company_id: int = None) -> dict:
    """Doimiy majburiyat kategoriyasini yaratadi yoki yangilaydi. Admin
    ISTALGAN yangi kategoriya nomini kiritishi mumkin."""
    from models import RecurringObligation
    import crud as _crud_obl
    # 17d (2026-09-21): qiymatlar QAT'IY (`crud._clean_majburiyat`) — xato
    # bo'lsa `ValueError`, hech narsa yozilmaydi. O'LCHANGAN: `inf` summa
    # "Qarzdorlar" sahifasini buzardi (500), `nan` → NULL, manfiy / 1e20
    # qabul; kun 0 / −3 / 99999; PostgreSQL da 30 belgidan uzun kod → 500.
    _toza = _crud_obl._clean_majburiyat(category, label, monthly_target,
                                        icon=icon, due_day=due_day)
    category, label = _toza["category"], _toza["label"]
    monthly_target, icon, due_day = (_toza["monthly_target"], _toza["icon"],
                                     _toza["due_day"])
    # M6 — TENANT: qidiruv ham, yangi yozuv ham korxona bilan. Ilgari
    # faqat `category` bo'yicha qidirilardi — A B ning majburiyatini
    # qayta yozib yuborishi mumkin edi.
    _oq = db.query(RecurringObligation).filter(RecurringObligation.category == category)
    if company_id is not None:
        _oq = _oq.filter(RecurringObligation.company_id == company_id)
    obl = _oq.first()
    if obl:
        obl.label = label
        obl.monthly_target = monthly_target
        obl.icon = icon
        obl.due_day = due_day
    else:
        obl = RecurringObligation(company_id=company_id, category=category, label=label,
                                   monthly_target=monthly_target,
                                   icon=icon, due_day=due_day, is_active=True)
        db.add(obl)
    db.commit()
    db.refresh(obl)
    return {"id": obl.id, "category": obl.category, "label": obl.label, "monthly_target": float(obl.monthly_target)}


def delete_recurring_obligation(db: Session, obligation_id: int, company_id: int = None) -> bool:
    """Doimiy majburiyat kategoriyasini o'chiradi (xarajat tarixi saqlanib qoladi)."""
    from models import RecurringObligation
    _dq = db.query(RecurringObligation).filter(RecurringObligation.id == obligation_id)
    if company_id is not None:      # M6: faqat shu korxonadan
        _dq = _dq.filter(RecurringObligation.company_id == company_id)
    obl = _dq.first()
    if not obl:
        return False
    db.delete(obl)
    db.commit()
    return True


def _obligation_status(debt: float, due_day: int, today) -> str:
    """Holatni avtomatik aniqlaydi: to'liq/qisman/muddat yaqin/muddati o'tgan."""
    if debt <= 0.5:
        return "full"
    if today.day > due_day:
        return "overdue"
    if due_day - today.day <= 3:
        return "due_soon"
    return "partial"


def get_company_obligations_status(db: Session, year: int, month: int,
                                  company_id: int = None) -> dict:
    """Kompaniyaning O'ZI kimlarga qarzdorligini — bitta joyda yig'ib beradi:
    1) Hodimlarga (oylik hisob-kitobdagi 'qolgan')
    2) Doimiy majburiyatlar (Arenda, Soliq, Transport va h.k.)
    Ikkalasi ham — FAQAT o'qish, mavjud, sinalgan hisob-kitoblardan foydalanadi.

    MUHIM (2026-09): Hodimlar qarzi — FAQAT "hozirgi oy"ni emas, balki
    OXIRGI 3 OYni (hozirgi + oldingi 2 ta) tekshiradi. Sabab: agar oylik,
    masalan, 3-4 kun kechikib, yangi oyga o'tib to'lansa — eski (masalan
    o'tgan oy) qarzi, avvalgi versiyada, "hozirgi oy" bo'lib qolgani uchun,
    ko'rinishdan BUTUNLAY yo'qolib qolar edi (garchi hali to'lanmagan
    bo'lsa ham). Endi, har bir yozuv, aynan QAYSI oyga tegishli ekanini
    ("year"/"month" maydonlari orqali) aniq bildiradi — shu orqali,
    "To'landi" tugmasi bosilganda, to'lov TO'G'RI oyga yozilishi ta'minlanadi."""
    from models import RecurringObligation, ExpenseTransaction

    today = _tashkent_date()      # kech105 (9 + 50-band): muddat kuni — Toshkent kalendari
    OY_NOMLARI = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
                  "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]

    # Oxirgi 3 oyni (hozirgi + oldingi 2 ta) tekshiramiz
    months_to_check = []
    y, m = year, month
    for _ in range(3):
        months_to_check.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1

    employees_with_debt = []
    for (chk_year, chk_month) in months_to_check:
        # MUHIM: to'g'ridan-to'g'ri calculate_monthly_employee_pay(...,0,0,0,0,0)
        # chaqirilsa — "necha metr/blok ishlatilgan" kabi HAQIQIY miqdorlar
        # o'rniga "0" yuborilgan bo'lardi, va shu sabab "har birlik uchun"
        # turidagi (Blok, Metr) xodimlar SUMMASI har doim "0" chiqib qolar edi.
        # Shuning uchun, o'sha haqiqiy miqdorlarni ALLAQACHON to'g'ri hisoblab
        # bergan get_monthly_report()dan foydalanamiz.
        monthly = get_monthly_report(db, chk_year, chk_month, company_id=company_id)
        emp_result = {"breakdown": monthly.get("hodimlar_moslashuvchan_breakdown", [])}
        is_current = (chk_year, chk_month) == (year, month)
        for e in emp_result["breakdown"]:
            if e["qolgan"] <= 0.5:
                continue
            employees_with_debt.append({
                "employee_id": e["employee_id"], "name": e["name"], "detail": e["detail"],
                "amount": e["amount"], "avans": e["avans"], "qolgan": e["qolgan"],
                "year": chk_year, "month": chk_month,
                "month_label": OY_NOMLARI[chk_month] if not is_current else f"{OY_NOMLARI[chk_month]} (joriy)",
                "status": "overdue" if (not is_current or today.day > 5) else "partial",
            })
    # Eng eski oy, birinchi (eng "shoshilinch") bo'lib ko'rinsin
    employees_with_debt.sort(key=lambda e: (e["year"], e["month"]))
    total_employee_debt = sum(e["qolgan"] for e in employees_with_debt)

    recurring = []
    _obq = db.query(RecurringObligation).filter(RecurringObligation.is_active == True)
    if company_id is not None:      # M6
        _obq = _obq.filter(RecurringObligation.company_id == company_id)
    obligations = _obq.all()
    # kech97 (116-band, O'LCHANGAN `work/probe116.py`): xarajatlar majburiyat × oy boshiga ALOHIDA so'ralardi
    # (+10 majburiyat — +30). Endi oy boshiga BITTA so'rov (o'sha shartlar, kategoriyalar ro'yxati bilan),
    # kategoriya bo'yicha guruhlanadi; tartib `date DESC` (asl), teng sanada — `id DESC` (aniq tartib).
    _kat_ob = sorted({o.category for o in obligations if float(o.monthly_target or 0) > 0})
    _xarajat_ob = {}
    for (_y_ob, _m_ob) in months_to_check:
        _guruh = _xarajat_ob.setdefault((_y_ob, _m_ob), {})
        if not _kat_ob:
            continue
        _txq = db.query(ExpenseTransaction).filter(
            ExpenseTransaction.category.in_(_kat_ob),
            _tashkent_oyida(ExpenseTransaction.date, _y_ob, _m_ob)
        )
        if company_id is not None:      # M6
            _txq = _txq.filter(ExpenseTransaction.company_id == company_id)
        for _t in _txq.order_by(ExpenseTransaction.date.desc(), ExpenseTransaction.id.desc()).all():
            _guruh.setdefault(_t.category, []).append(_t)
    for obl in obligations:
        target = float(obl.monthly_target or 0)
        if target <= 0:
            continue
        # MUHIM (2026-09): xuddi hodimlar kabi — faqat "hozirgi oy"ni emas,
        # OXIRGI 3 OYni ham tekshiramiz. Aks holda, masalan Arenda,
        # o'tgan oyda to'lanmay, yangi oyga o'tib ketsa — bu yerdan
        # butunlay yo'qolib qolar edi (garchi hali to'lanmagan bo'lsa ham).
        for (chk_year, chk_month) in months_to_check:
            # Bu majburiyat, hali YARATILMAGAN oy uchun — tekshirmaymiz
            # (aynan hodim ishga kirish sanasi bilan bir xil mantiq).
            if obl.created_at:
                # kech105 (9 + 50-band): oy oxiri — TOSHKENT kalendari (ilgari UTC 23:59:59 — Toshkent 1-kun
                # 00:00–05:00 da yaratilgan majburiyat o'tgan oyga ham qarz yozardi)
                _chk_month_end = _tashkent_oy_oraligi(chk_year, chk_month)[1]
                if obl.created_at >= _chk_month_end:
                    continue
            is_current = (chk_year, chk_month) == (year, month)
            txs = _xarajat_ob[(chk_year, chk_month)].get(obl.category, [])
            paid = sum(float(t.amount or 0) for t in txs)
            debt = max(0, target - paid)
            if debt <= 0.5:
                continue
            last_payment = txs[0].date.isoformat() if txs else None
            recurring.append({
                "category": obl.category, "label": obl.label, "icon": obl.icon or "📦",
                "target": round(target), "paid": round(paid), "debt": round(debt),
                "due_day": obl.due_day or 5, "last_payment": last_payment,
                "year": chk_year, "month": chk_month,
                "month_label": OY_NOMLARI[chk_month] if not is_current else f"{OY_NOMLARI[chk_month]} (joriy)",
                "status": "overdue" if (not is_current or _obligation_status(debt, obl.due_day or 5, today) == "overdue") else _obligation_status(debt, obl.due_day or 5, today)
            })
    recurring_with_debt = sorted(recurring, key=lambda r: (r["year"], r["month"]))
    total_recurring_debt = sum(r["debt"] for r in recurring_with_debt)

    return {
        "employees": employees_with_debt,
        "total_employee_debt": round(total_employee_debt),
        "recurring": recurring_with_debt,
        "recurring_all": recurring,
        "total_recurring_debt": round(total_recurring_debt),
        "total_company_debt": round(total_employee_debt + total_recurring_debt),
    }


def get_full_debt_summary(db: Session, year: int, month: int,
                         company_id: int = None) -> dict:
    """"Moliya" sahifasi (va uning PDF hisoboti) uchun — TO'RTALA qarz
    yo'nalishini, BITTA joyga jamlab beradi:
    1) Bizga qarzdorlar — mijozlar (loyihalar)
    2) Yetkazib beruvchiga qarzimiz
    3) Hodimlarga qarzimiz (oxirgi 3 oy)
    4) Doimiy majburiyatlar (Arenda/Soliq/Kommunal)

    MUHIM: bu funksiya, hech qanday YANGI hisoblash qilmaydi — faqat,
    ALLAQACHON mavjud, boshqa joylarda (Qarzdorlar sahifasida) sinalgan
    funksiyalarni chaqirib, natijalarini bitta joyga yig'ib beradi."""
    from models import Order, OrderStatus

    # M6 (2026-09-18) — TENANT: mijoz qarzi, ta'minotchi qarzi va
    # kompaniyaning o'z majburiyatlari — hammasi joriy korxona bo'yicha.
    # kech100 (134-band, QAROR "A"): Qarzdorlar sahifasi bilan AYNAN bir shart (o'chirilgan READY / DELIVERED qarzi HAM)
    import crud as _crud_qz134
    _oq = db.query(Order).filter(
        _crud_qz134.qarz_hisobidagi_buyurtma_sharti(),
        Order.status != OrderStatus.DRAFT
    )
    if company_id is not None:
        _oq = _oq.filter(Order.company_id == company_id)
    from sqlalchemy.orm import selectinload as _sil_fd
    orders = _oq.options(_sil_fd(Order.payments)).all()     # kech97 (116-band): to'lovlar bitta IN so'rovi
    order_debts = [o for o in orders if float(o.debt_amount or 0) > 0.5]
    total_customer_debt = round(sum(float(o.debt_amount or 0) for o in order_debts))

    import crud as _crud_debt
    suppliers_all = _crud_debt.get_suppliers_with_debt(db, company_id=company_id)
    supplier_debts = [s for s in suppliers_all if s['debt'] > 0]
    total_supplier_debt = round(sum(s['debt'] for s in supplier_debts))

    company = get_company_obligations_status(db, year, month, company_id=company_id)

    return {
        "customer_debt": total_customer_debt,
        "customer_debt_count": len(order_debts),
        "supplier_debt": total_supplier_debt,
        "supplier_debt_count": len(supplier_debts),
        "employee_debt": company["total_employee_debt"],
        "employee_debt_count": len(company["employees"]),
        "recurring_debt": company["total_recurring_debt"],
        "recurring_debt_count": len(company["recurring"]),
        "net_position": total_customer_debt - total_supplier_debt - company["total_employee_debt"] - company["total_recurring_debt"],
    }


def get_obligation_timeline(db: Session, category: str, year: int, month: int,
                           company_id: int = None) -> list:
    """Bitta kategoriya uchun, shu oydagi barcha to'lovlar tarixi (timeline)."""
    from models import ExpenseTransaction
    _tq = db.query(ExpenseTransaction).filter(
        ExpenseTransaction.category == category,
        _tashkent_oyida(ExpenseTransaction.date, year, month)
    )
    if company_id is not None:      # M6
        _tq = _tq.filter(ExpenseTransaction.company_id == company_id)
    txs = _tq.order_by(ExpenseTransaction.date.desc()).all()
    return [{
        "date": t.date.isoformat(), "amount": float(t.amount or 0),
        "notes": t.notes, "created_by": t.created_by
    } for t in txs]


def get_employee_payment_timeline(db: Session, employee_id: int, year: int, month: int) -> list:
    """Bitta hodim uchun, shu oydagi barcha to'lovlar (avans+yakuniy) tarixi."""
    advances = get_employee_advances_list(db, employee_id, year, month)
    return [{"date": a["date"], "amount": a["amount"], "notes": a["notes"] or "Avans/to'lov",
              "created_by": a["given_by"]} for a in advances]


def close_employee_debt(db: Session, employee_id: int, year: int, month: int, amount: float, paid_by: str = None) -> dict:
    """Hodimning shu oydagi qolgan qarzini to'lash — mavjud, sinalgan
    EmployeeAdvance mexanizmining o'zidan foydalanadi (avans va yakuniy
    to'lov — matematik jihatdan bir xil narsa: ikkalasi ham hisoblangan
    oylikdan ayriladi)."""
    from datetime import datetime
    import crud as _crud
    _bugun_t = _tashkent_date()   # kech105 (9 + 50-band): joriy oy / kun — Toshkent kalendari
    adv_date = datetime(year, month, min(28, _bugun_t.day) if (year, month) == (_bugun_t.year, _bugun_t.month) else 28)
    adv = _crud.create_employee_advance(db, employee_id, amount, notes="Oy oxiri — qolgan oylik to'landi",
                                         given_by=paid_by, adv_date=adv_date)
    return {"success": adv is not None}


def get_production_period_stats(db: Session, company_id: int = None) -> dict:
    """Ishlab chiqarish — bugun/hafta/oy bo'yicha nechta mahsulot chiqqani.
    Faqat o'qish, FinishedProduct.created_at (source=produced) asosida.

    2026-09-18 — TENANT (M7 validatsiyasida topilgan TO'RTINCHI sizish):
    funksiyada `company_id` parametri UMUMAN yo'q edi va `FinishedProduct`
    butun tizim bo'yicha sanalardi — ya'ni har qanday korxonaning
    boshqaruv paneli boshqa korxonalarning ishlab chiqarish miqdorini
    ham ko'rsatardi.

    `company_id` FAQAT autentifikatsiya kontekstidan keladi
    (`main.py` → `auth.company_id_of(current_user)`); mijoz so'rovidan
    olinmaydi va hech qanday standart 1-korxonaga tushmaydi.
    Hisoblash formulasi (bugun/hafta/oy chegaralari, miqdorlar yig'indisi)
    O'ZGARTIRILMADI."""
    from models import FinishedProduct, StockSource
    from datetime import datetime, timedelta
    from database import tashkent_today_start_utc

    today_start = tashkent_today_start_utc()
    # kech105 (9 + 50-band, O'LCHANGAN): hafta / oy boshi TOSHKENT sanasidan. Ilgari UTC ko'rinishidagi
    # `today_start` (oldingi kun 19:00) ning `weekday()` / `replace(day=1)` idan olinardi — hafta SESHANBA 00:00 dan,
    # oy esa 2-kun 00:00 dan boshlanardi (Toshkent vaqti bilan).
    _bugun_t = _tashkent_date()
    week_start = today_start - timedelta(days=_bugun_t.weekday())
    month_start = _tashkent_oy_oraligi(_bugun_t.year, _bugun_t.month)[0]

    def _count_since(since):
        q = db.query(FinishedProduct).filter(
            FinishedProduct.source == StockSource.PRODUCED,
            FinishedProduct.created_at >= since
        )
        if company_id is not None:
            q = q.filter(FinishedProduct.company_id == company_id)
        items = q.all()
        return round(sum(float(i.quantity or 0) for i in items))

    return {
        "today": _count_since(today_start),
        "week": _count_since(week_start),
        "month": _count_since(month_start),
    }


# kech36 (K35-1): "Tayyor loy" zaxirasini TANIYDIGAN YAGONA qoida — nom
# `get_or_create_loy_stock` yasaydigan shakl (`f"Tayyor loy ({retsept})"`) bilan
# boshlanadi. Bunday pozitsiya sotib olinadigan xomashyo EMAS, balki
# buyurtmalardan ORTGAN loy; u odatda 0 / 0 turadi va bu me'yor — "kam qoldi" /
# "qolmadi" ogohlantirishlariga va Omborxona "Kam qolganlar" soniga kirmaydi.
# Ishlatiladi: `get_notifications` (qo'ng'iroqcha), `get_inventory_kpi`
# (Omborxona KPI); `crud.get_low_stock_items` (Telegram) — o'sha shakl
# (`'Tayyor loy (%'`); `inventory.html` — `startswith('Tayyor loy (')`.
# kech37 (21-band) — FOYDALANUVCHI QARORI: "Ortgan loy uchun chegara shart
# emas." Ya'ni Tayyor loy ga min > 0 qo'yilgan bo'lsa ham u HECH QAYERDA "kam"
# deb chiqmaydi: `check_low_stock` (bosh sahifa, dashboard, buyurtmalar sahifasi
# ogohlantirishi, bugungi vazifalar, grafik), `get_business_alerts` (hisobotlar),
# `main.api_full_stock_report` (Telegram "Ombor hisoboti"), `reports.html`
# `stockDot`; Omborxona qatorida chegara ustuni "—" (tahrirlash tugmasi yo'q).
# Ilgari qo'ng'iroqcha `'Tayyor loy%'` (qavssiz) ishlatardi: foydalanuvchi o'zi
# yaratgan "Tayyor loy" nomli oddiy material tugasa ham ogohlantirilmasdi,
# Telegram esa ogohlantirardi — endi ikkalasi bir xil.
TAYYOR_LOY_PREFIKS = "Tayyor loy ("


def get_notifications(db: Session, company_id: int = None) -> list:
    """Bosh sahifa va butun tizim uchun bildirishnomalar — faqat o'qish.

    Uch turi:
    - 🔴 Xomashyo butunlay tugagan
    - 🟠 Joriy sarf tezligiga qarab, N kun ichida tugashi kutilmoqda
      (InventoryMovement jurnalidagi oxirgi 14 kunlik 'chiqim' asosida)
    - 🟢 Bugun yetkazilgan/tayyor buyurtmalar soni
    """
    from models import Inventory, InventoryMovement, Order, OrderStatus
    from sqlalchemy import func
    from datetime import datetime, timedelta
    from database import tashkent_today_start_utc

    notifications = []
    now = datetime.utcnow()

    # ── 🔴 Butunlay tugagan ──────────────────────────────────
    # "Tayyor loy (...)" — bular oddiy xomashyo emas, balki ISHLAB
    # CHIQARISHDAN ORTIB QOLGAN qoldiq (keyingi buyurtmaga ishlatish
    # uchun). Ular ODATDA 0 bo'lib turadi — bu me'yor, muammo emas,
    # shuning uchun bu ogohlantirishlarga kiritilmaydi.
    # 20-band (2026-09-21): o'chirilgan (yashirilgan, `is_deleted`) materiallar
    # ogohlantirishga KIRMAYDI — ular ombor ro'yxatida (`crud.get_inventory`)
    # ko'rinmaydi, lekin ilgari bu yerda "qolmadi" deb chiqib turardi.
    empty_items = db.query(Inventory).filter(
        *( [Inventory.company_id == company_id] if company_id is not None else [] ),
        Inventory.is_deleted.isnot(True),
        Inventory.stock_quantity <= 0,
        ~Inventory.item_name.like(TAYYOR_LOY_PREFIKS + '%')
    ).all()
    for item in empty_items:
        notifications.append({
            "level": "red",
            "icon": "🔴",
            "text": f"{item.item_name} qolmadi",
            "category": "stock_empty",
            "created_at": now.isoformat(),
        })

    # ── 🟠 Sarf tezligiga qarab tugash bashorati ─────────────
    period_start = now - timedelta(days=14)
    items = db.query(Inventory).filter(
        *( [Inventory.company_id == company_id] if company_id is not None else [] ),
        Inventory.is_deleted.isnot(True),       # 20-band — yuqoridagi bilan bir xil
        Inventory.stock_quantity > 0,
        ~Inventory.item_name.like(TAYYOR_LOY_PREFIKS + '%')
    ).all()
    # kech98 (129-band, O'LCHANGAN `work/probe116.py`): 14 kunlik chiqim material boshiga ALOHIDA SUM edi — endi
    # bitta GROUP BY (shartlar AYNAN: korxona, material, "out", davr).
    _chiqim_14 = {}
    for _b in _hk_bolaklar([it.id for it in items]):
        for _iid, _sm in db.query(InventoryMovement.inventory_id, func.sum(InventoryMovement.quantity)).filter(
            *( [InventoryMovement.company_id == company_id] if company_id is not None else [] ),
            InventoryMovement.inventory_id.in_(_b),
            InventoryMovement.movement_type == "out",
            InventoryMovement.created_at >= period_start
        ).group_by(InventoryMovement.inventory_id).all():
            _chiqim_14[_iid] = _sm
    for item in items:
        total_out = _chiqim_14.get(item.id)
        total_out = float(total_out or 0)
        if total_out <= 0:
            continue  # Sarf tarixi yo'q — bashorat qilib bo'lmaydi
        daily_rate = total_out / 14
        days_left = float(item.stock_quantity) / daily_rate if daily_rate > 0 else None
        if days_left is not None and days_left <= 7:
            notifications.append({
                "level": "orange",
                "icon": "🟠",
                "text": f"{item.item_name} {max(1, round(days_left))} kundan keyin tugaydi",
                "category": "stock_predicted",
                "created_at": now.isoformat(),
            })

    # ── 🟢 Bugun yetkazilgan/tayyor buyurtmalar ──────────────
    today_start = tashkent_today_start_utc()
    today_end = today_start + timedelta(days=1)
    today_count = db.query(Order).filter(
        *( [Order.company_id == company_id] if company_id is not None else [] ),
        Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED]),
        Order.completed_at >= today_start, Order.completed_at < today_end,
        Order.is_deleted.isnot(True)
    ).count()
    if today_count > 0:
        notifications.append({
            "level": "green",
            "icon": "🟢",
            "text": f"Bugun {today_count} ta buyurtma topshirildi",
            "category": "orders_today",
            "created_at": now.isoformat(),
        })

    # Muhimlik bo'yicha: qizil > sariq > yashil
    order_map = {"red": 0, "orange": 1, "green": 2}
    notifications.sort(key=lambda n: order_map.get(n["level"], 9))
    return notifications


def check_low_stock(db: Session, company_id: int = None) -> List[Dict]:
    """Min qoldiqdan kam bo'lgan xomashyolar ro'yxati.

    Admin dashboardida ko'rsatish uchun.
    """
    # 2026-09-21: QAT'IY korxona filtri — None bo'lsa bo'sh (ilgari
    # filtr umuman yo'q edi: B dashboardida A ning xomashyo nomlari).
    # 2026-09-22 (kech34, K34-1 — jonli O'LCHANGAN): o'chirilgan (tarixi bor,
    # shuning uchun YASHIRILGAN — `crud.delete_item` soft) material Omborxona
    # ro'yxatida yo'q, lekin bosh sahifa "Kam qolgan xomashyo", dashboard,
    # buyurtmalar sahifasi ogohlantirishi va "Bugungi vazifalar" da ko'rinishda
    # davom etardi — foydalanuvchi uni ko'ra ham, to'ldira ham olmaydi.
    # `get_business_alerts` / `get_notifications` dagidek yashirinlar chiqariladi
    # (`isnot(True)` — eski NULL qatorlar ko'rinadigan bo'lib qoladi).
    # kech37 (21-band, foydalanuvchi qarori: "Ortgan loy uchun chegara shart
    # emas"): "Tayyor loy (...)" zaxirasiga min > 0 qo'yilgan bo'lsa ham u bosh
    # sahifa "Kam qolgan xomashyo", dashboard, buyurtmalar ogohlantirishi,
    # bugungi vazifalar va grafikka TUSHMAYDI (ilgari tushardi — Omborxona KPI,
    # qo'ng'iroqcha va Telegram esa uni chiqarib tashlardi). `TAYYOR_LOY_PREFIKS`.
    # kech108 (K108-2, 19-band — EGASI QARORI "Ha, ko'rinsin"): YAGONA shart `crud.kam_qoldiq_sharti` —
    # minimal qoldig'i belgilanmagan (0 / NULL) material TUGASA (qoldiq ≤ 0) ham chiqadi. Ilgari `min_stock > 0` SHART
    # edi: O'LCHANGAN (`main` ning haqiqiy ma'lumoti) — Penoplast 10P −0.06 / 0: qo'ng'iroqcha "qolmadi", Omborxona
    # "Kam qolganlar: 1 ta", bosh sahifa esa "Barcha xomashyo yetarli".
    import crud as _crud_kq
    low_items = db.query(Inventory).filter(
        Inventory.company_id == company_id,
        *_crud_kq.kam_qoldiq_sharti()
    ).all()

    result = []
    for item in low_items:
        _q = float(item.stock_quantity or 0)
        _m = float(item.min_stock or 0)
        result.append({
            "id": item.id,
            "item_name": item.item_name,
            "stock_quantity": _q,
            "min_stock": _m,
            "unit": item.unit,
            "deficit": _m - _q,
            "tugagan": _q <= 0,
            "alert": "⚠️ Xomashyo tugagan!" if _q <= 0 else "⚠️ Xomashyo yetishmayapti!"
        })

    return result


# kech120 (E bosqichi 2-qism, G1-11 — audit: «Katta Korxona» da bugungi buyurtmalar 14 qator bo'lib Bosh sahifa tepasini to'ldirardi,
# qatorlarni bosib bo'lmasdi, «119 ta buyurtma muddati o'tgan» — faqat son): har guruhdan ko'pi bilan shuncha qator, qolgani —
# «yana N ta →» havolasi (filtrlangan ro'yxatga).
BUGUNGI_VAZIFA_CHEGARA = 5


def get_today_tasks(db: Session, company_id: int = None) -> List[Dict]:
    """Bosh sahifa «Bugungi vazifalar» — bugun e'tibor talab qiladigan narsalar: bugun topshirilishi kerak bo'lgan buyurtmalar,
    muddati o'tgan buyurtmalar, kam qolgan xomashyo. Har biri {icon, text, href} — `href` qator bosilganda ochiladigan joy
    (buyurtma — `/orders?order=ID`; filtrlangan ro'yxat — `/orders?royxat=bugun|otgan`; kam qolganlar — `/inventory?kam=1`).
    kech120 (G1-11): har guruh `BUGUNGI_VAZIFA_CHEGARA` qatorgacha, qolgani bitta «yana N ta» qatori."""
    from models import Order, OrderStatus
    from datetime import datetime, timedelta
    from database import tashkent_today_start_utc

    tasks = []
    today_start = tashkent_today_start_utc()
    today_end = today_start + timedelta(days=1)
    _n = BUGUNGI_VAZIFA_CHEGARA

    # 1) Bugun topshirilishi kerak bo'lgan buyurtmalar
    # 2026-09-21: QAT'IY korxona filtri (ilgari yo'q edi — B "bugungi
    # vazifalar"da A ning buyurtma raqamlarini ko'rardi).
    # kech120 (G1-11): «Tayyor» (READY — yakunlangan, avto yuk xati bilan topshirilgan) ham chiqariladi — muddati o'tganlar
    # (pastda) va Buyurtmalar sahifasidagi «Bugun» filtri (`crud.get_deadline_urgency`) bilan BIR qoida.
    due_today = db.query(Order).filter(
        Order.company_id == company_id,
        Order.deadline >= today_start, Order.deadline < today_end,
        Order.status.notin_([OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.READY]),
        Order.is_deleted.isnot(True)
    ).order_by(Order.deadline, Order.id).all()
    for o in due_today[:_n]:
        tasks.append({"icon": "🚚", "text": f"{o.order_number} — bugun topshirilishi kerak", "href": f"/orders?order={o.id}"})
    if len(due_today) > _n:
        tasks.append({"icon": "🚚", "text": f"yana {len(due_today) - _n} ta buyurtma bugun topshirilishi kerak",
                      "href": "/orders?royxat=bugun"})

    # 2) Muddati o'tgan (kechikkan) buyurtmalar
    overdue = db.query(Order).filter(
        Order.company_id == company_id,
        Order.deadline < today_start,
        Order.status.notin_([OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.READY]),
        Order.is_deleted.isnot(True)
    ).count()
    if overdue > 0:
        tasks.append({"icon": "⏰", "text": f"{overdue} ta buyurtma muddati o'tgan", "href": "/orders?royxat=otgan"})

    # 3) Kam qolgan xomashyo
    low_stock = check_low_stock(db, company_id)
    for item in low_stock[:_n]:
        # kech108 (K108-2): qoldiq ≤ 0 — "tugagan"
        _hol = "tugagan" if item.get("tugagan") else "kam qolgan"
        tasks.append({"icon": "⚠️", "text": f"{item['item_name']} {_hol} ({item['stock_quantity']:g} {item['unit']})",
                      "href": "/inventory?kam=1"})
    if len(low_stock) > _n:
        tasks.append({"icon": "⚠️", "text": f"yana {len(low_stock) - _n} ta material kam qolgan", "href": "/inventory?kam=1"})

    if not tasks:
        tasks.append({"icon": "✅", "text": "Bugun uchun alohida vazifa yo'q"})

    return tasks


# kech90 (110-band): hisobot keshi bilan o'raladi — `_hisobot_keshi_bilan` pastda (kech89 bloki) aniqlangani
# uchun o'rash o'sha blokdan keyin: `get_today_stats = _hisobot_keshi_bilan(get_today_stats)`.
def get_today_stats(db: Session, company_id: int = None) -> Dict:
    """Dashboard yuqori qatori uchun 'bugungi kun' statistikasi.

    Barchasi bazadagi haqiqiy yozuvlardan hisoblanadi:
    - Bugungi tushum: bugun qabul qilingan to'lovlar summasi (Payment.paid_at)
    - Ishlab chiqarishda: status = in_progress yoki coating bo'lgan buyurtmalar
    - Bugun topshiriladi: deadline bugunga to'g'ri keladigan, hali yopilmagan buyurtmalar
    - Ishlayotgan ustalar: hozir faol buyurtmasi bor noyob ustalar soni
    - Sof foyda (bugun): bugun yakunlangan (completed_at) buyurtmalar bo'yicha calculate_order_profit yig'indisi
    """
    from models import Order, OrderStatus, Master, Payment, FinishedProductSale, FinishedProduct
    from sqlalchemy import func
    from datetime import datetime, timedelta
    from database import tashkent_today_start_utc

    today_start = tashkent_today_start_utc()
    today_end = today_start + timedelta(days=1)

    # M6 (2026-09-18) — TENANT: bugungi ko'rsatkichlar joriy korxona bo'yicha.
    from models import Order as _Ord_td
    _trq = db.query(func.sum(Payment.amount)).join(
        _Ord_td, _Ord_td.id == Payment.order_id) if company_id is not None else db.query(func.sum(Payment.amount))
    today_revenue = float(_trq.filter(
        *( [_Ord_td.company_id == company_id] if company_id is not None else [] ),
        Payment.paid_at >= today_start, Payment.paid_at < today_end
    ).scalar() or 0)

    active_orders = db.query(Order).filter(
        *( [Order.company_id == company_id] if company_id is not None else [] ),
        Order.status.notin_([OrderStatus.READY, OrderStatus.DELIVERED, OrderStatus.CANCELLED]),
        Order.is_deleted.isnot(True)
    ).count()

    in_production = db.query(Order).filter(
        *( [Order.company_id == company_id] if company_id is not None else [] ),
        Order.status.in_([OrderStatus.IN_PROGRESS, OrderStatus.COATING]),
        Order.is_deleted.isnot(True)
    ).count()

    due_today = db.query(Order).filter(
        *( [Order.company_id == company_id] if company_id is not None else [] ),
        Order.deadline >= today_start, Order.deadline < today_end,
        Order.status.notin_([OrderStatus.DELIVERED, OrderStatus.CANCELLED]),
        Order.is_deleted.isnot(True)
    ).count()

    active_masters = db.query(Order.master_id).filter(
        *( [Order.company_id == company_id] if company_id is not None else [] ),
        Order.master_id.isnot(None),
        Order.status.in_([OrderStatus.NEW, OrderStatus.IN_PROGRESS, OrderStatus.COATING]),
        Order.is_deleted.isnot(True)
    ).distinct().count()

    # MUHIM: o'chirilgan buyurtmalar ham hisobga olinadi — "bugungi foyda"
    # ko'rsatkichi ham, moliyaviy tarix sifatida, o'zgarmasligi kerak.
    completed_today = db.query(Order).filter(
        *( [Order.company_id == company_id] if company_id is not None else [] ),
        Order.completed_at >= today_start, Order.completed_at < today_end,
        Order.status == OrderStatus.READY
    ).all()
    _hk_tayyorla(db, completed_today)    # kech90 (110-band): N+1 o'rniga bir necha IN so'rovi
    today_profit = 0.0
    for o in completed_today:
        try:
            p = yakun_foydasi(db, o, company_id=company_id)      # kech102 (144-band): yakunlangan paytdagi
            if p.get("success"):
                today_profit += p.get("foyda", 0)
        except Exception:
            db.rollback()
    # kech102 (144-band, QAROR "Qaytarish oyida"): bugun bo'lgan qaytarishlar (yakunlangan buyurtmalardan keyin)
    _bugun_qaytarish = davr_qaytarishlari(db, today_start, today_end, company_id=company_id)
    for _h144 in _bugun_qaytarish:
        today_profit += _h144["foyda"]

    # ── Tayyor mahsulotlar bo'limidan to'g'ridan-to'g'ri (buyurtmasiz)
    # sotilganlar — avval bu "Bugungi" statistikada hisobga olinmasdi. ──
    # kech98 (129-band, O'LCHANGAN `work/probe116.py`): sotuv boshiga mahsulot (turkum uchun) ALOHIDA yuklanardi —
    # endi bitta IN so'rovi (o'sha munosabat, o'sha korxona sharti).
    from sqlalchemy.orm import selectinload as _sil_td
    fp_sales_today = db.query(FinishedProductSale).filter(
        *( [FinishedProductSale.company_id == company_id] if company_id is not None else [] )
    ).outerjoin(
        FinishedProduct, FinishedProductSale.finished_product_id == FinishedProduct.id
    ).filter(
        FinishedProductSale.sold_at >= today_start,
        FinishedProductSale.sold_at < today_end
    ).options(_sil_td(FinishedProductSale.finished_product)).all()
    for s in fp_sales_today:
        s_total = float(s.total_amount or 0)
        s_cost = float(s.cost_amount or 0)
        today_revenue += s_total
        today_profit += (s_total - s_cost)

    # kech117 (A2): bugungi daromad YO'NALISHLAR bo'yicha (ilgari «Gips / Penoplast») — YAGONA qoida
    # (`yonalish_daromadlari`, oylik hisobot bilan bir): yakunlangan buyurtmalar, bugungi qaytarishlar, TM sotuvi.
    _yx_t = _YonXarita(db, company_id)
    today_yonalishlar = yonalishlar_royxati_hisobot(_yx_t, yonalish_daromadlari(
        db, company_id, completed_today, lambda _o: yakun_daromadi(db, _o), qaytarishlar=_bugun_qaytarish,
        tm_sotuvlari=fp_sales_today, xarita=_yx_t))

    return {
        "today_revenue": float(today_revenue),
        "active_orders": active_orders,
        "in_production": in_production,
        "due_today": due_today,
        "active_masters": active_masters,
        "today_profit": today_profit,
        "today_yonalishlar": [dict(y, daromad=round(y["daromad"])) for y in today_yonalishlar],
    }


def get_dashboard_stats(db: Session, company_id: int = None) -> Dict:
    """Admin dashboard uchun umumiy statistika.

    M5 — TENANT: ustalar sanog'i joriy korxona bo'yicha. (Qolgan
    sanoqlar M2/M3/M6 doirasida alohida ko'riladi.)"""
    from models import Project, Master

    # 2026-09-21: sanoqlar QAT'IY korxona bo'yicha (ilgari butun baza).
    total_projects = db.query(Project).filter(Project.company_id == company_id, Project.is_deleted.isnot(True)).count()
    total_orders = db.query(Order).filter(Order.company_id == company_id, Order.is_deleted.isnot(True)).count()
    active_orders = db.query(Order).filter(Order.company_id == company_id, Order.status != OrderStatus.READY, Order.is_deleted.isnot(True)).count()
    ready_orders = db.query(Order).filter(Order.company_id == company_id, Order.status == OrderStatus.READY, Order.is_deleted.isnot(True)).count()
    _tmq = db.query(Master).filter(Master.is_active == True)
    if company_id is not None:      # M5
        _tmq = _tmq.filter(Master.company_id == company_id)
    total_masters = _tmq.count()
    # kech34 (K34-1): yashirilgan (o'chirilgan) materiallar sanalmaydi.
    total_inventory_items = db.query(Inventory).filter(
        Inventory.company_id == company_id,
        Inventory.is_deleted.isnot(True)).count()
    low_stock = check_low_stock(db, company_id)

    return {
        "total_projects": total_projects,
        "total_orders": total_orders,
        "active_orders": active_orders,
        "ready_orders": ready_orders,
        "total_masters": total_masters,
        "total_inventory_items": total_inventory_items,
        "low_stock_count": len(low_stock),
        "low_stock_items": low_stock
    }


# ============================================================
# 5. TO'LIQ BUYURTMA YAKUNLASH (Cutting + Coating + KPI)
# ============================================================

class _TayyorBekor(Exception):
    """kech101 (142-band): «Tayyor» o'rtasida bekor qilish — `complete_order` tranzaksiyasi `rollback` bo'ladi,
    chaqiruvchiga `natija` (`success: False`) qaytadi."""

    def __init__(self, natija: Dict):
        super().__init__(natija.get("message"))
        self.natija = natija


def complete_order(db: Session, order_id: int, loy_kg: Optional[float] = None) -> Dict:
    """Buyurtmani to'liq yakunlash — barcha avtomatika:

    1. AVVAL — xomashyo yetarliligini tekshirish
    2. Penoplast bloklarini ayirish (kesish)
    3. Retsept bo'yicha xomashyoni ayirish (qoplama)
    4. Usta KPI hisoblash (3% + 1000/m)
    5. Status -> READY
    """
    from datetime import datetime

    # 17d (2026-09-21): haqiqiy loy miqdori HECH NARSA o'zgarishidan oldin
    # tekshiriladi. O'LCHANGAN: `inf` → buyurtma "Tayyor" bo'lib, loy
    # xomashyosi qoldig'i −∞ saqlanardi va buyurtma kartasi, "Qarzdorlar",
    # biznes-salomatlik 500; `1e20` → qoldiq −5×10¹⁹; `nan` / manfiy JIMGINA
    # "kiritilmagan" deb qabul qilinardi. Bo'sh / `None` — "kiritilmagan"
    # (reja bo'yicha), bu SAQLANADI.
    import crud as _crud_loy
    try:
        loy_kg = _crud_loy._query_loy("loy_kg", loy_kg, bosh_mumkin=True)
    except ValueError as e:
        return {"success": False, "message": str(e)}

    # kech101 (142-band, O'LCHANGAN — `work/probe142.py`, SQLite = PG): quyidagi HAMMA ish BITTA tranzaksiyada —
    # chaqiruvchidan qat'i nazar. API (`main.api_mark_order_ready`) kech84 dan beri `crud.bitta_tranzaksiya` ichida
    # chaqiradi (A: 9 nosozlik nuqtasi — xatodan keyin holat AYNAN oldingi, qayta urinish = NAZORAT), lekin funksiyaning
    # O'ZI oraliq `commit` lar bilan yozilgan edi (kech41): tranzaksiyasiz chaqirilsa (B) qolgan qism xomashyosi /
    # tayyor mahsulot / "Loy sotish" / MRP bandi / miqdor yakunlash yoki avtomatik yuk xatosida buyurtma READY + loy
    # yechilgan holda SAQLANIB QOLARDI, qayta «Tayyor» esa "allaqachon tayyor" (400) — tuzatib bo'lmas yarim holat.
    # Endi ichki `commit` lar `flush` (`bitta_tranzaksiya` — API bilan ichma-ich: bitta tashqi tranzaksiya), qulf (101)
    # «Tayyor» OXIRIGACHA ushlanadi: parallel o'chirish / yuk / to'lov «Tayyor» ni yarim holatda ko'rmaydi.
    import crud as _crud_tr
    try:
        with _crud_tr.bitta_tranzaksiya(db):
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "message": "Buyurtma topilmadi"}

            # kech41 (5-bo'lim 14-band, K41-1) — QULF (101, buyurtma), yetkazish /
            # to'lov / detal tahriri bilan BIR fazo; qulf ostida bazadan QAYTA
            # o'qiladi. HAQIQIY PostgreSQL da O'LCHANGAN (asl kod, `work/probe41.py`,
            # 3 / 3): "Tayyor" bosilayotganda boshqa xodim 5 / 10 topshirsa, buyurtma
            # READY bo'lib qolardi — qolgan 5 topshirilmagan, summa yakunlanmagan
            # ("hech narsa topshirilmagan" deb eskirgan holatdan qaror qilinardi,
            # avtomatik yuk esa qulf ostida "Qoldiqdan ko'p" bilan jim rad etilardi).
            import crud as _crud_qulf
            _cid_q = order.company_id
            db.flush()
            _crud_qulf._pul_qulfi(db, 101, order.id)
            db.expire_all()
            order = db.query(Order).filter(Order.id == order_id, Order.company_id == _cid_q).first()
            if not order:
                return {"success": False, "message": "Buyurtma topilmadi"}

            if order.status == OrderStatus.READY:
                return {"success": False, "message": "Bu buyurtma allaqachon tayyor"}

            # kech101 (K101-1, O'LCHANGAN — `work/probe142.py` C1 / C2, SQLite = PG): kech100 dan OLDIN o'chirilgan
            # (IN_PROGRESS — qolgan qism xomashyosi o'chirishda qaytgan, `stock_returned`; DELIVERED) buyurtma «Tayyor»
            # qilinardi (200): qisman — penoplast IKKINCHI marta qaytdi (+0.06 blok), ikkalasi ham READY bo'lib oylik
            # hisobot / usta KPI ga kirdi (+1 buyurtma) — Savatdagi buyurtma uchun, 140-band BIZNES qarorini chetlab.
            # Yuk xati (`create_delivery`) kabi — avval tiklash.
            if order.is_deleted:
                return {"success": False, "message": _crud_tr.OCHIRILGAN_BUYURTMA_XABARI}

            # 17d (2026-09-21): QORALAMA buyurtma "Tayyor" qilinmaydi. Qoralamada
            # ombordan HECH NARSA yechilmagan (`deduct_inventory_for_order` faqat
            # "Jarayonga olish" da ishlaydi) — uni "Tayyor" qilish xomashyosiz
            # tayyor buyurtma, usta KPI va avtomatik yuk xati yaratardi (O'LCHANGAN:
            # `POST /ready` qoralamaga 200 "yakunlandi"). UI qoralamaga "Tayyor"
            # tugmasini ko'rsatmaydi (`orders.html`: `btn-ready` yashirin).
            if order.status == OrderStatus.DRAFT:
                return {"success": False,
                        "message": "Qoralama buyurtmani avval jarayonga oling — keyin \"Tayyor\" qilish mumkin"}

            # kech70 (FOYDALANUVCHI QARORI "Taqiqlansin"): hali hech narsa topshirilmagan buyurtmada
            # "Tayyor" butun qoldiqni AVTOMATIK yuk xati bilan topshiradi (pastda). MRP detali ishlab
            # chiqarilmagan / kam ishlab chiqarilgan bo'lsa u yuk xati rad etiladi — shuning uchun
            # "Tayyor" ham HECH NARSAGA tegmasdan OLDIN aniq sabab bilan rad etiladi (aks holda
            # buyurtma "tayyor" bo'lib, yuk xati jim yozilmay qolardi).
            if not order.deliveries:
                _mrp_kam = []
                for _it in order.items:
                    if _crud_qulf._mrp_yetkazish_detalimi(_it):
                        _kerak = float(_it.remaining_qty or 0)
                        if _kerak > 0.001:
                            _tayyor = _crud_qulf._mrp_tayyor_qoldiq(db, _it, order.company_id, lock=False)
                            # kech80 (88-band): shart YAGONA yordamchida — buyurtmadagi «MRP: tayyor» belgisi ham
                            # aynan shu shart bilan (`crud.mrp_topshirish_holati`).
                            if not _crud_qulf.mrp_tayyor_yetadimi(_kerak, _tayyor):
                                _mrp_kam.append(f"{_it.name}: kerak {_kerak:g}, tayyor {_tayyor:g}")
                if _mrp_kam:
                    return {"success": False,
                            "message": ("MRP mahsuloti hali to'liq ishlab chiqarilmagan — avval ishlab "
                                        "chiqarishni yakunlang: " + "; ".join(_mrp_kam))}

            # === HAMMA NARSA TAYYOR — BAJARAMIZ ===
            # kech41 (14-band): holat DARHOL READY — quyidagi oraliq `commit` lar
            # qulfni bo'shatadi; parallel ikkinchi "Tayyor" qulfdan keyin READY ni
            # ko'rib rad etiladi (O'LCHANGAN: asl kodda ikkalasi ham "yakunlandi" —
            # loy / qaytishlar ikki marta ishlanardi). Oxiridagi `order.status =
            # READY` o'z joyida qoladi (avtomatik yuk DELIVERED qo'yishi mumkin).
            # kech101 (142-band): endi `commit` = `flush` (yuqoridagi `bitta_tranzaksiya`) — qulf bo'shamaydi, ikkinchi
            # «Tayyor» qulfni KUTADI va birinchisi saqlangach READY ni ko'rib rad etiladi (natija o'sha).
            order.status = OrderStatus.READY
            result = {
                "success": True,
                "message": "✓ Buyurtma yakunlandi!",
                "inventory_changes": [],
                "master_kpi": None
            }

            # === LOY HISOB-KITOBI ===
            # Buyurtma yaratilganda rejalashtirilgan loy allaqachon ayirilgan.
            # Endi haqiqiy miqdor bilan solishtiramiz.
            import crud as _crud
            order_planned = _get_planned_loy(order)
            planned_loy = order_planned
            actual_loy = float(loy_kg or 0)

            # MUHIM FARQ:
            # - TO'LIQ yakunlashda (yoki hali hech narsa topshirilmagan holatda) —
            #   hodim REJA bo'yicha loy aralashtirgan, ortgani — HAQIQATAN aralashtirilgan,
            #   faqat ishlatilmagan tayyor loy. "Tayyor loy" ombor pozitsiyasiga qo'shiladi.
            # - QISMAN yakunlashda — hodim FAQAT bajargan ishiga yarasha loy tayyorlaydi,
            # rejadagi qolgan qismni umuman ARALASHTIRMAYDI HAM. Demak "ortgan" qism —
            # bu XOM XOMASHYO (Akril, Qum va h.k.), ular o'z joyiga qaytishi kerak,
            # "Tayyor loy" ga emas.
            is_partial_completion = bool(order.deliveries) and not order.is_fully_delivered

            if actual_loy > 0:
                recipe = _get_order_recipe(db, order)
                diff = actual_loy - planned_loy

                if diff > 0.01:
                    # Ko'proq ketdi — farq uchun xomashyo ayiramiz (ikkala holatda ham bir xil)
                    loy_log = deduct_loy_ingredients(db, order, diff)
                    result["inventory_changes"].extend(loy_log)
                    result["loy_info"] = {
                        "planned": planned_loy,
                        "actual": actual_loy,
                        "diff": round(diff, 1),
                        "action": "qoshimcha",
                        "message": f"Rejadan {diff:.1f} kg ko'p ketdi — xomashyo ayirildi"
                    }
                elif diff < -0.01:
                    extra = abs(diff)
                    if is_partial_completion:
                        # Aralashtirilmagan — xom xomashyo o'z joyiga qaytadi.
                        # kech82 (102-band): buyurtma loyining bir qismi tayyor loy ZAXIRASIDAN olingan bo'lsa — u birinchi
                        # ishlatilgan; ortgan qism xom qismdan ko'p bo'lsa, ortig'i zaxiraga qaytadi (olingan joyiga).
                        with loy_manba_rejimi(db, "ushla"):
                            ing_log = return_loy_ingredients(db, order, extra)
                        result["inventory_changes"].extend(ing_log)
                        result["loy_info"] = {
                            "planned": planned_loy,
                            "actual": actual_loy,
                            "diff": round(diff, 1),
                            "action": "ortdi",
                            "message": f"Qisman yakunlandi — {extra:.1f} kg uchun XOM XOMASHYO (aralashtirilmagan) o'z joyiga qaytdi"
                        }
                    else:
                        # To'liq yakunlangan — haqiqatan aralashtirilgan, tayyor loy sifatida saqlanadi
                        msg = add_loy_to_stock(db, recipe, extra)
                        if msg:
                            result["inventory_changes"].append(msg)
                        result["loy_info"] = {
                            "planned": planned_loy,
                            "actual": actual_loy,
                            "diff": round(diff, 1),
                            "action": "ortdi",
                            "message": f"{extra:.1f} kg loy ortdi — omborga (Tayyor loy) qo'shildi"
                        }
                else:
                    result["loy_info"] = {
                        "planned": planned_loy,
                        "actual": actual_loy,
                        "diff": 0,
                        "action": "teng",
                        "message": "Reja bo'yicha ketdi"
                    }

                # MUHIM: haqiqiy kiritilgan umumiy loy miqdorini (Termopanel VA
                # oddiy qismni QO'SHIB, ULUSHGA BO'LMASDAN) order.notes'ga yozamiz —
                # foyda hisoblashda BITTA umumiy "Qoplama" xarajati sifatida
                # ko'rsatiladi. Formula/taxmin EMAS — aynan hodim "Tayyor"
                # bosganda kiritgan haqiqiy son.
                if actual_loy > 0:
                    import re as _re_loy
                    base_notes = _re_loy.sub(r',?\s*loy_kg=[\d.]+', '', order.notes or '').strip().strip(',').strip()
                    order.notes = (base_notes + f", loy_kg={actual_loy:.4f}").strip(', ')
                    order.actual_loy_kg = actual_loy
                    db.commit()
            elif planned_loy > 0:
                # Haqiqiy miqdor kiritilmadi — reja bo'yicha deb hisoblaymiz
                result["loy_info"] = {
                    "planned": planned_loy,
                    "actual": planned_loy,
                    "diff": 0,
                    "action": "teng",
                    "message": "Reja bo'yicha hisoblandi"
                }
                # kech112 (K112-3, O'LCHANGAN — `work/k113/probe_qoplama.py`, SQLite = PG; jonli C zanjiri): "reja bo'yicha"
                # deyilardi, ombor ham rejani ishlatilgan deb qoldirardi, lekin haqiqiy loy YOZILMASDI — foyda
                # (`calculate_order_profit`, u faqat `actual_loy_kg` / izohdagi `loy_kg=` ni o'qiydi) qoplama xarajatini
                # 0 deb olardi: 20 kg loy (~30 000 so'm) tannarxdan tushib, buyurtma foydasi, oylik hisobot va usta KPI
                # shuncha ortiq chiqardi. Endi kiritilgan miqdor kabi — reja haqiqiy loy sifatida yoziladi.
                import re as _re_loy_reja
                _reja_izoh = _re_loy_reja.sub(r',?\s*loy_kg=[\d.]+', '', order.notes or '').strip().strip(',').strip()
                order.notes = (_reja_izoh + f", loy_kg={float(planned_loy)}").strip(', ')
                order.actual_loy_kg = planned_loy

            db.commit()

            # kech41 (14-band): `commit` qulfni bo'shatdi — qisman / to'liq qarori
            # oldidan qulf QAYTA olinadi va holat bazadan qayta o'qiladi (oraliqda
            # yozilgan yuk xati hisobga olinsin).
            _crud_qulf._pul_qulfi(db, 101, order.id)
            db.expire_all()
            order = db.query(Order).filter(Order.id == order_id, Order.company_id == _cid_q).first()
            is_partial_completion = bool(order.deliveries) and not order.is_fully_delivered

            # === QISMAN TOPSHIRILGAN HOLATDA YAKUNLASH ===
            # Agar buyurtma ALLAQACHON qisman topshirilgan bo'lsa-yu (masalan 64%),
            # shu holda "Tayyor" bosilsa — bu "qolgani kerak emas, shu bilan yakunlaymiz"
            # degani. Qolgan (topshirilmagan) qism uchun xomashyo omborga qaytadi.
            # (Hali hech narsa topshirilmagan — oddiy holat — bunga tegilmaydi.)
            if is_partial_completion:
                partial_log = return_inventory_for_order_partial(db, order)
                # kech100 (K100-1 / K100-2 / K100-3a — O'LCHANGAN `work/probe_k100_mrp.py`, asl SQLite = PG; 93-band oracle
                # testi `tools/test_ochirish_yopish.py` topdi): qolgan (topshirilmagan) qismning TAYYOR MAHSULOTI, "Loy sotish"
                # XOMASHYOSI va MRP BANDI qaytmasdi — "Loy sotish" 20 kg dan 4 kg topshirilib «Tayyor»: 16 kg qum na omborda,
                # na tannarxda; tayyor mahsulotdan 10 m dan 4 m: 6 m tayyor mahsulot yo'qoldi; MRP 10 dan 4: 6 tasi READY
                # buyurtmaga abadiy BAND. Endi o'chirishdagi (`main.api_delete_order`) bilan AYNAN: tayyor mahsulot
                # (`_return_finished_for_order` — `remaining_qty`), "Loy sotish" retsepti bo'yicha qolgan kg (buyurtma loyi
                # manbasi — "ushla", yuqoridagi ortgan loy kabi), MRP bandi ozod (`_auto_release_mrp_reservations`). Buyurtma
                # miqdori pastda topshirilganga tushiriladi — qaytgan qism tannarxga kirmaydi (ikki marta hisob yo'q).
                partial_log.extend(_crud._return_finished_for_order(db, order))
                with loy_manba_rejimi(db, "ushla"):
                    for _it100 in order.items:
                        if (_it100.category or '').lower() == 'loy_sotish' and _it100.recipe_id:
                            _qolgan100 = _it100.remaining_qty
                            if _qolgan100 > 0.001:
                                partial_log.extend(return_loy_ingredients(db, order, float(_qolgan100),
                                                                          recipe_id=_it100.recipe_id))
                _crud._auto_release_mrp_reservations(db, [_it100.id for _it100 in order.items],
                                                     "«Tayyor» (qisman yakunlash)")
                if partial_log:
                    result["inventory_changes"].extend(partial_log)
                    result["partial_return"] = {
                        "delivery_percent": order.delivery_percent,
                        "message": f"Qisman topshirilgan ({order.delivery_percent:.0f}%) — qolgan qism uchun xomashyo omborga qaytdi"
                    }

                # Buyurtma miqdori/summasi — HAQIQATDA berilgan miqdorga tushiriladi
                fin = _crud.finalize_partial_order_quantities(db, order)
                result["finalized"] = fin
                msg = f"Buyurtma summasi {fin['old_total']:.0f} → {fin['new_total']:.0f} so'mga tushirildi (haqiqatda berilgan miqdorga mos)."
                if fin["overpaid"]:
                    msg += f" ⚠️ Mijoz {fin['overpaid']:.0f} so'm ortiqcha to'lagan — QAYTARILISHI kerak!"
                elif fin["debt"] > 0:
                    msg += f" Qarz qoldi: {fin['debt']:.0f} so'm."
                else:
                    msg += " To'lov to'liq yopilgan."
                result["finalized"]["message"] = msg
            elif not order.deliveries:
                # Hali HECH NARSA topshirilmagan — bu odatiy holat.
                # "Tayyor" bosilishi bilan — mahsulot BIR YO'LA, TO'LIQ topshirilgan deb
                # avtomatik yozib qo'yamiz (alohida "Bir yo'la to'liq topshirish"
                # tugmasini bosish shart emas).
                from schemas import DeliveryCreate, DeliveryItemCreate
                delivery_items = []
                for item in order.items:
                    remaining = item.remaining_qty
                    if remaining > 0.001:
                        delivery_items.append(DeliveryItemCreate(order_item_id=item.id, quantity=remaining))

                if delivery_items:
                    dcreate = DeliveryCreate(order_id=order.id, items=delivery_items)
                    dres = _crud.create_delivery(db, dcreate, delivered_by="Avtomatik (Tayyor deb belgilashda)")
                    if dres.get("success"):
                        result["auto_delivery"] = {
                            "delivery_id": dres.get("delivery_id"),
                            "message": "✅ Barcha mahsulot avtomatik ravishda BIR YO'LA topshirilgan deb belgilandi."
                        }
                    else:
                        # kech101 (142-band, O'LCHANGAN — `work/probe142.py` A / B "JIM rad"): avtomatik yuk xati rad
                        # etilsa (`success: False` — istisnosiz) «Tayyor» 200 qaytarib buyurtmani yuksiz READY qilardi —
                        # oylik hisobot / usta KPI ga kirdi (+1, 500 000), mahsulot topshirilmagan, qayta «Tayyor» —
                        # "allaqachon tayyor". Endi BUTUN «Tayyor» bekor (tranzaksiya `rollback`), sabab xabarda.
                        _sabab101 = str(dres.get("message") or "yuk xati yozilmadi")
                        if dres.get("shortages"):
                            _sabab101 += ": " + "; ".join(str(x) for x in dres.get("shortages"))
                        raise _TayyorBekor({"success": False,
                                            "message": ("Avtomatik yuk xati yozilmadi — «Tayyor» bekor qilindi, hech narsa "
                                                        "saqlanmadi. Sabab: " + _sabab101)})

            # 3. USTA KPI — kech103 (5-bo'lim 45-band, O'LCHANGAN `work/probe103ui.py` T1): «Tayyor» oynasidagi "👷 Usta
            # KPI" ilgari eski formula edi (kelishilgan summaning 3 % + qoplamali metr × 1 000 so'm; profil metri
            # `length × quantity`) — hech qayerda hisobga tushmaydigan, ustaning haqiqiy KPI si (`/kpi`, oylik hisobot —
            # buyurtma foydasi × `kpi_percent`) bilan mos kelmaydigan raqam (500 000 lik buyurtma: 25 000 ↔ 43 000).
            # Endi shu buyurtmaning yakunlangan paytdagi foydasi (`yakun_foydasi`) × ustaning KPI foizi — pastda, holat
            # READY bo'lgach (oylik KPI bilan BITTA qoida; foyda manfiy bo'lsa — 0).
            _usta45 = None
            if order.master_id:
                _mq45 = db.query(Master).filter(Master.id == order.master_id)
                if getattr(order, 'company_id', None) is not None:
                    _mq45 = _mq45.filter(Master.company_id == order.company_id)
                _usta45 = _mq45.first()

            # 4. Status yangilash
            order.status = OrderStatus.READY
            order.completed_at = datetime.utcnow()
            # Loy miqdorini notes ga saqlaymiz (foyda hisoblash uchun)
            if loy_kg and loy_kg > 0:
                import re as _re_loykg_w
                existing_notes = order.notes or ''
                base_notes = _re_loykg_w.sub(r',?\s*loy_kg=[\d.]+', '', existing_notes).strip().strip(',').strip()
                order.notes = (base_notes + f", loy_kg={loy_kg}").strip(', ')
                order.actual_loy_kg = float(loy_kg)
            # kech103 (45-band): usta KPI — shu buyurtma foydasi × KPI foizi (oylik KPI bilan bir qoida).
            if _usta45 is not None and float(_usta45.kpi_percent or 0) > 0:
                try:
                    db.flush()
                    _foyda45 = float(yakun_foydasi(db, order, company_id=getattr(order, 'company_id', None))
                                     .get("foyda", 0) or 0)
                    _pct45 = float(_usta45.kpi_percent or 0)
                    result["master_kpi"] = {
                        "master": _usta45.name,
                        "kpi_percent": _pct45,
                        "foyda": round(_foyda45),
                        "total_kpi": round(max(_foyda45, 0.0) * _pct45 / 100),
                    }
                except Exception as _e45:
                    try:
                        import crud as _crud45
                        _crud45.log_error(db, str(_e45), endpoint=f"complete_order:master_kpi order#{order.id}")
                    except Exception:
                        pass
            db.commit()
            db.refresh(order)

            return result
    except _TayyorBekor as _rad101:
        return _rad101.natija


def get_inventory_kpi(db: Session, company_id: int = None) -> Dict:
    """Omborxona sahifasi uchun KPI ko'rsatkichlari — faqat o'qish, hech narsani o'zgartirmaydi."""
    from models import Inventory, InventoryMovement
    from sqlalchemy import func
    from datetime import datetime, timedelta
    from database import tashkent_today_start_utc

    _iq = db.query(Inventory).filter(Inventory.is_deleted.isnot(True))
    if company_id is not None:
        _iq = _iq.filter(Inventory.company_id == company_id)
    items = _iq.all()
    total_items = len(items)
    # kech36 (K35-1, jonli O'LCHANGAN kech35): "Tayyor loy (...)" zaxirasi
    # (`TAYYOR_LOY_PREFIKS` izohi) "Kam qolganlar" ga SANALMAYDI. Ilgari
    # Omborxona "Kam qolganlar 1 ta" deb `Tayyor loy (Oq marmar)` 0 / 0 ni
    # sanardi, holbuki qo'ng'iroqcha, bosh sahifa va Telegram uni ko'rsatmasdi.
    # Endi `low_count` == `len(crud.get_low_stock_items(...))` (Telegram
    # "kam qoldi" ro'yxati) — oddiy material 0 / 0 esa avvalgidek sanaladi.
    # kech108 (K108-2): AYNAN `crud.kam_qoldiq_sharti` qoidasi (Python nusxasi `crud.kam_qoldiqmi`)
    import crud as _crud_kq
    low_count = sum(1 for i in items if _crud_kq.kam_qoldiqmi(i))
    total_value = sum(float(i.stock_quantity or 0) * float(i.price_per_unit or 0) for i in items)

    today_start = tashkent_today_start_utc()
    today_end = today_start + timedelta(days=1)

    _mv_cid = ([InventoryMovement.company_id == company_id]
               if company_id is not None else [])
    today_in = db.query(func.count(InventoryMovement.id)).filter(
        *_mv_cid,
        InventoryMovement.movement_type == "in",
        InventoryMovement.created_at >= today_start, InventoryMovement.created_at < today_end
    ).scalar() or 0
    today_out = db.query(func.count(InventoryMovement.id)).filter(
        *_mv_cid,
        InventoryMovement.movement_type == "out",
        InventoryMovement.created_at >= today_start, InventoryMovement.created_at < today_end
    ).scalar() or 0

    return {
        "total_items": total_items,
        "low_count": low_count,
        "total_value": total_value,
        "today_in_count": today_in,
        "today_out_count": today_out,
    }


def get_low_stock_warnings(db: Session, company_id: int = None) -> List[Dict]:
    """check_low_stock ning alias — eski kodlarga moslik uchun."""
    return check_low_stock(db, company_id)


# ============================================================
# DASHBOARD UCHUN KENGAYTIRILGAN STATISTIKA
# ============================================================

def get_chart_data(db: Session, company_id: int = None) -> Dict:
    """Dashboard grafiklari uchun ma'lumotlar.

    2026-09-18 — TENANT (M7 validatsiyasida B sessiyasidan topilgan
    UCHINCHI haqiqiy sizish): bu funksiyadagi 9 ta so'rov korxona
    filtrisiz edi. Natijada B korxonaning boshqaruv panelida A ning
    moliyaviy ko'rsatkichlari ko'rinardi — `total_revenue 53 757 000`,
    `total_budget`/`total_debt 120 417 000`, oylik daromad 54 569 000 —
    holbuki B da buyurtma summasi ham, sotuv ham 0 edi.

    `company_id` FAQAT autentifikatsiya kontekstidan keladi
    (`main.py` → `auth.company_id_of(current_user)`); mijoz so'rovidan
    olinmaydi va hech qanday standart 1-korxonaga tushmaydi."""
    from models import Project, Master, Order, OrderItem, OrderStatus, FinishedProductSale, FinishedProduct
    from sqlalchemy import func
    from sqlalchemy.orm import selectinload as _sil_cd

    def _oc(q):
        """Order bo'yicha so'rovni joriy korxona bilan cheklaydi."""
        return q.filter(Order.company_id == company_id) if company_id is not None else q

    # --- 1. Oxirgi 6 oylik buyurtmalar soni ---
    months_data = []
    _yx_c = _YonXarita(db, company_id)     # kech117 (A2): yo'nalishlar (grafik bir marta o'qiydi)
    _yon_nomlari = {}
    # kech105 (9 + 50-band, QAROR "Toshkent vaqti bo'yicha"): oxirgi 6 oy — TOSHKENT kalendar oylari. Ilgari oy
    # boshi `now − i × 30 kun` dan olinardi (UTC; 31 kunlik oylar ketma-ket kelganda bir oy ikki marta / tushib
    # qolishi mumkin edi) va chegara Toshkent vaqti bilan 05:00 da edi.
    _bugun_t = _tashkent_date()
    for i in range(5, -1, -1):
        _oy_y, _oy_m = _bugun_t.year, _bugun_t.month - i
        while _oy_m <= 0:
            _oy_m += 12
            _oy_y -= 1
        month_start, month_end = _tashkent_oy_oraligi(_oy_y, _oy_m)

        count = _oc(db.query(Order).filter(
            Order.created_at >= month_start,
            Order.created_at < month_end,
            Order.is_deleted.isnot(True)
        )).count()

        # MUHIM: daromad (revenue) — moliyaviy tarix, o'chirilgan
        # buyurtmalar ham hisobga olinishi kerak (faqat "count" — necha ta
        # buyurtma yaratilgani — o'zgarishsiz qoladi, chunki bu shunchaki son).
        revenue = float(_oc(db.query(func.sum(func.coalesce(Order.agreed_amount, Order.total_amount, 0))).filter(
            Order.completed_at >= month_start,      # kech105 (K105-4): «Tayyor» oyi — oylik hisobot bilan bir qoida
            Order.completed_at < month_end,
            Order.status == OrderStatus.READY
        )).scalar() or 0)

        # Gips va Penoplast (va boshqa) — detal darajasida, ulush bo'yicha
        # ajratilgan holda (har bir detalning umumiy summadagi ulushi ×
        # kelishilgan summa — chegirma/qo'shimchani ham to'g'ri hisobga oladi)
        # kech97 (116-band): detallar "Tayyor" buyurtma boshiga so'ralardi — endi bitta IN so'rovi (order_by=id).
        month_orders = _oc(db.query(Order).filter(
            Order.completed_at >= month_start,      # kech105 (K105-4): «Tayyor» oyi
            Order.completed_at < month_end,
            Order.status == OrderStatus.READY
        )).options(_sil_cd(Order.items)).all()
        # kech117 (A2): yo'nalishlar bo'yicha — YAGONA qoida (`yonalish_daromadlari`); bu grafikda avvalgidek
        # joriy kelishilgan summa (qaytarish hodisalarisiz) — faqat taqsimot «Gips / Penoplast» o'rniga yo'nalishlar.

        # Tayyor mahsulotlar bo'limidan to'g'ridan-to'g'ri (buyurtmasiz)
        # sotilganlar — avval bu grafikda hisobga olinmasdi.
        _mfsq = db.query(FinishedProductSale).outerjoin(
            FinishedProduct, FinishedProductSale.finished_product_id == FinishedProduct.id
        ).filter(
            FinishedProductSale.sold_at >= month_start,
            FinishedProductSale.sold_at < month_end
        )
        if company_id is not None:
            # OUTER JOIN bo'lgani uchun cheklash SOTUVNING O'ZIDAGI
            # company_id ustuni bo'yicha qo'yiladi — mahsuloti o'chirilgan
            # (finished_product_id = NULL) sotuvlar ham to'g'ri qoladi.
            _mfsq = _mfsq.filter(FinishedProductSale.company_id == company_id)
        # kech98 (129-band, O'LCHANGAN `work/probe116.py`): sotuv boshiga mahsulot (turkum uchun) ALOHIDA yuklanardi —
        # endi bitta IN so'rovi (o'sha munosabat, o'sha korxona sharti).
        month_fp_sales = _mfsq.options(_sil_cd(FinishedProductSale.finished_product)).all()
        for s in month_fp_sales:
            s_total = float(s.total_amount or 0)
            revenue += s_total
        _oy_yon = yonalish_daromadlari(db, company_id, month_orders, lambda _o: _o.kelishilgan_summa,
                                       tm_sotuvlari=month_fp_sales, xarita=_yx_c)
        for _k in _oy_yon:
            _yon_nomlari[_k] = _yx_c.nom(_k)

        months_data.append({
            "label": f"{_OY_QISQA[_oy_m - 1]} {_oy_y}",    # kech118 (U-06): o'zbekcha (ilgari "%b" — «Sep 2026»)
            "yonalishlar": {_k: round(_v) for _k, _v in _oy_yon.items()},
            "orders": count,
            "revenue": float(revenue)
        })

    # --- 2. Buyurtma holatlari (donut chart) ---
    statuses = {}
    for status in OrderStatus:
        try:
            cnt = _oc(db.query(Order).filter(Order.status == status, Order.is_deleted.isnot(True))).count()
            statuses[status.value] = cnt
        except Exception:
            # Enum bazada hali yo'q bo'lsa
            db.rollback()
            statuses[status.value] = 0

    # --- 3. Ustalar KPI (top 5) ---
    _cmq = db.query(Master).filter(Master.is_active == True)
    if company_id is not None:      # M5
        _cmq = _cmq.filter(Master.company_id == company_id)
    masters = _cmq.all()
    # kech98 (129-band, O'LCHANGAN `work/probe116.py`): usta boshiga 2 so'rov (kelishilgan summa SUM, buyurtmalar soni)
    # edi — endi ikkita GROUP BY so'rovi, shartlar AYNAN (summa — "Tayyor", o'chirilganlar ham; soni — o'chirilmaganlar).
    _mids_cd = [m.id for m in masters]
    _jami_cd, _soni_cd = {}, {}
    for _b in _hk_bolaklar(_mids_cd):
        for _mid, _sm in _oc(db.query(Order.master_id, func.sum(func.coalesce(Order.agreed_amount, Order.total_amount, 0))).filter(
            Order.master_id.in_(_b),
            Order.status == OrderStatus.READY
        )).group_by(Order.master_id).all():
            _jami_cd[_mid] = _sm
        for _mid, _n in _oc(db.query(Order.master_id, func.count(Order.id)).filter(
            Order.master_id.in_(_b),
            Order.is_deleted.isnot(True)
        )).group_by(Order.master_id).all():
            _soni_cd[_mid] = _n
    master_kpi = []
    for m in masters:
        # MUHIM: bu ham daromad (moliyaviy) hisob-kitobi — o'chirilgan
        # buyurtmalar ham hisobga olinadi.
        total = _jami_cd.get(m.id) or 0
        order_count = _soni_cd.get(m.id, 0)
        master_kpi.append({
            "name": m.name,
            "total": float(total),
            "orders": order_count
        })
    # Eng ko'p ishlagani birinchi
    master_kpi.sort(key=lambda x: x["total"], reverse=True)
    master_kpi = master_kpi[:5]

    # --- 4. Umumiy moliyaviy ko'rsatkichlar ────────────────
    # MUHIM: barchasi BITTA manbadan — Order/Payment jadvallaridan —
    # hisoblanadi, xuddi Moliya va Hisobotlar sahifalari kabi. Avval
    # "To'langan"/"Jami byudjet" Project.total_paid/total_budget kabi
    # alohida (keshlangan) maydonlardan olinar edi — bu ular haqiqiy
    # to'lovlardan (Payment) sekin-asta uzoqlashib ketishiga sabab
    # bo'lishi mumkin edi. Endi hammasi bir xil, izchil manbadan.
    from models import Payment

    total_revenue = _oc(db.query(func.sum(func.coalesce(Order.agreed_amount, Order.total_amount, 0))).filter(
        Order.status == OrderStatus.READY
    )).scalar() or 0

    from sqlalchemy import or_
    total_budget = _oc(db.query(func.sum(func.coalesce(Order.agreed_amount, Order.total_amount, 0))).filter(
        Order.status != OrderStatus.DRAFT,
        or_(
            Order.is_deleted.isnot(True),  # faol buyurtmalar — doim hisoblanadi
            Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED])  # o'chirilgan, lekin YAKUNLANGAN edi — moliyaviy tarix sifatida saqlanadi
        )
    )).scalar() or 0

    # M6 — TENANT: to'lovlar ota (buyurtma) orqali cheklanadi.
    _tpq = db.query(func.sum(Payment.amount))
    if company_id is not None:
        from models import Order as _Ord_ch
        _tpq = _tpq.join(_Ord_ch, _Ord_ch.id == Payment.order_id).filter(
            _Ord_ch.company_id == company_id)
    total_paid = _tpq.scalar() or 0
    # kech100 (134-band / K100-4, O'LCHANGAN `work/probe134.py`): "Jami qarz" = byudjet − HAMMA to'lovlar edi — hisobga
    # kirmagan buyurtmalar (eski o'chirilgan IN_PROGRESS, qoralama zaklati) to'lovlari va ORTIQCHA to'lovlar boshqa
    # mijozlar qarzini "yopardi" (asl: 900 000, haqiqiy qarzlar yig'indisi 1 000 000). Endi — Qarzdorlar sahifasi bilan
    # AYNAN: shu buyurtmalar (`crud.qarz_hisobidagi_buyurtma_sharti`, qoralamasiz) qarzlari yig'indisi (tiyin, 0.5 bardosh).
    import crud as _crud_qz134
    from sqlalchemy.orm import selectinload as _sil_qz134
    from models import pul_tiyin_yigindi as _pty134
    _qz_buyurtmalar = _oc(db.query(Order).filter(
        _crud_qz134.qarz_hisobidagi_buyurtma_sharti(),
        Order.status != OrderStatus.DRAFT
    )).options(_sil_qz134(Order.payments)).all()
    total_debt = _pty134(o.debt_amount for o in _qz_buyurtmalar if float(o.debt_amount or 0) > 0.5)

    # --- 5. Omborxona holati (top yetishmayotganlar) ---
    low_stock = check_low_stock(db, company_id)

    # kech117 (A2): yo'nalishlar ro'yxati (grafik ustunlari) — ko'rinadiganlar + 6 oyda daromadi borlari
    for _k in _yx_c.korinadigan():
        _yon_nomlari.setdefault(_k, _yx_c.nom(_k))
    return {
        "months": months_data,
        "yonalishlar": [{"kalit": _k, "nom": _yon_nomlari[_k]} for _k in _yx_c.tartibla(_yon_nomlari)],
        "yonalishlar_soni": len(_yx_c.korinadigan()),
        "statuses": statuses,
        "master_kpi": master_kpi,
        "finance": {
            "total_revenue": float(total_revenue),
            "total_paid": float(total_paid),
            "total_budget": float(total_budget),
            "total_debt": total_debt
        },
        "low_stock": low_stock[:5]
    }


# ============================================================
# BUYURTMA FOYDA VA TAN NARXI HISOBLASH (faqat Admin uchun)
# ============================================================

# ============================================================
# kech89 (52-band) — HISOBOT KESHI: buyurtma sikli so'rovlari bir necha IN so'roviga
# ============================================================
# O'LCHANGAN (kech88 `work/probe52.py`; kech89 `work/dump52.py IZ=1`, murakkab fikstura, SQLite = PG):
# `GET /api/finance/report` SQL so'rovlari = 31 + 17 × N (N — shu oy "Tayyor" buyurtmalar; jonli 21 ta →
# ~388 so'rov, ~3.5 s: Railway bazasi bilan har so'rov bir necha ms). Sabab — `calculate_order_profit`
# (hisobotning o'zi, Ehson va usta KPI — har buyurtma uchun 2–3 marta) buyurtmani, standart penoplastni,
# harakatlarni, material narxini, detallarni, ichki detallarni, ishlab chiqarish buyurtmalarini, retseptni
# va ustani ALOHIDA so'raydi; hisobot ham har detal uchun materialni (`_inv_rep`) so'raydi.
#
# YECHIM (texnik — Claude): hisobot funksiyalari (`@_hisobot_keshi_bilan`) davomida sessiyada KESH turadi,
# buyurtmalar ro'yxati `_hk_tayyorla` bilan bir necha IN so'rovi orqali oldindan o'qiladi. Hisob-kitob
# mantig'i O'ZGARMAYDI: har o'qish joyida — kesh bo'lsa keshdan (asl so'rovning filtr qoidasi Python da,
# tartibi asl bilan bir xil), bo'lmasa ASL so'rov satri o'zgarishsiz (else-shoxida). Keshda yo'q narsa —
# asl so'rov bilan o'qiladi va eslab qolinadi, ya'ni natija hech qachon "taxmin" emas. Oldindan o'qish
# so'rovlari korxona bo'yicha cheklangan (buyurtmalarning O'Z korxonasi); begona korxona yozuvi (buzilgan
# holat) oldindan o'qilmaydi — unga asl so'rov o'zi javob beradi. Kesh faqat hisobot (O'QISH) davomida
# yashaydi va hisobot tugashi bilan o'chadi — yozuvchi yo'llar (buyurtma, «Tayyor», sovg'a davri
# yopilishi) va alohida `calculate_order_profit` chaqiruvi uni ko'rmaydi (asl yo'l).
# `HISOBOT_KESHI_YOQIQ = False` — kesh umuman yoqilmaydi (test: kesh bilan va keshsiz natija AYNAN).
import contextlib as _contextlib_hk
import functools as _functools_hk

HISOBOT_KESHI_YOQIQ = True
_HK_KALIT = "_hisobot_keshi"
_HK_YOQ = object()          # "keshda yo'q" belgisi (None — haqiqiy natija bo'lishi mumkin)


class _HisobotKeshi:
    """Bitta hisobot davomidagi o'qishlar: `d[bo'lim][kalit]`. Obyektlar KUCHLI havola bilan
    saqlanadi — sessiyaning identity map i kuchsiz havola tutadi, aks holda obyekt yo'qolib, uning
    ro'yxatlari (`items`, `sub_details`, `ingredients`) qayta so'ralardi.

    Bo'limlar: "buyurtma" (order_id -> Order), "inv" (id -> material qatori; korxona sharti O'QISHDA —
    kech99, 112-band: `_korxona_materiali`, `_inv_rep`, `_buyurtma_sarf_narxlari`), "inv_begona"
    ((id, company_id) -> True: shu korxonada yo'q material — qayta so'ralmaydi), "std" (company_id -> standart
    penoplast), "harakat" (order_id -> brak EMAS harakatlar, id tartibida), "po" (order_item_id -> tugagan PO
    lar, baza tartibida), "tm" ((fp_id, company_id) -> TM), "tm_birlik" (fp_id -> muzlagan birlik tannarx),
    "retsept_k" ((id, company_id) -> Recipe). "harakat" / "po" ro'yxatlarida bir necha korxona yozuvi bo'lishi
    mumkin — korxona sharti O'QISHDA qo'llanadi (asl so'rovdagidek)."""

    def __init__(self):
        self.d = {}


def _hk(db):
    """Faol hisobot keshi yoki None."""
    _info = getattr(db, "info", None)
    return _info.get(_HK_KALIT) if isinstance(_info, dict) else None


@_contextlib_hk.contextmanager
def hisobot_keshi(db):
    """Hisobot keshini yoqadi. Ichma-ich chaqiruvda TASHQI kesh ishlatiladi (tarix → 12 oylik hisobot)."""
    _info = getattr(db, "info", None)
    if (not HISOBOT_KESHI_YOQIQ) or (not isinstance(_info, dict)) or (_info.get(_HK_KALIT) is not None):
        yield _hk(db)
        return
    _k = _HisobotKeshi()
    _info[_HK_KALIT] = _k
    try:
        yield _k
    finally:
        _info.pop(_HK_KALIT, None)


def _hisobot_keshi_bilan(fn):
    """Dekorator: funksiya (birinchi argumenti — `db`) hisobot keshi ichida bajariladi."""
    @_functools_hk.wraps(fn)
    def _o(*args, **kwargs):
        _db = args[0] if args else kwargs.get("db")
        with hisobot_keshi(_db):
            return fn(*args, **kwargs)
    return _o


# ============================================================
# kech120 (E bosqichi, U-09) — HISOBOT XOTIRASI: oylik hisobot natijasi so'rovlar ORASIDA
# ============================================================
# O'LCHANGAN (`work/k127/tez.py`, 300 buyurtma, SQLite va HAQIQIY PG 16): «Hisobotlar» sahifasi bir ochilishda
# `get_monthly_report` ni 12 marta (oktabr, sentabr (1–N kun), sentabr, avgust — 4 xil kalit) hisoblaydi, har biri yuzlab
# buyurtma foydasi; «Dashboard» — 4, «Moliya» — 6, «Qarzdorlar» — 3. Sinov saytida (kam ma'lumot) har hisobot so'rovi 0,5–1,2 s.
#
# YECHIM (texnik — Claude): natija (`copy.deepcopy`) jarayon xotirasida eslab qolinadi va FAQAT quyidagilar bajarilsa
# qaytariladi — aks holda ASL hisob (o'zgarishsiz):
#   1) `database.yozuv_versiyasi()` saqlangandagi bilan AYNAN: shu jarayondagi har qanday yozuv (istalgan jadval, istalgan
#      korxona) va har yozuvli tranzaksiya yakuni versiyani oshiradi — natija darhol eskiradi;
#   2) hisob boshidan oxirigacha versiya o'zgarmagan (hisob paytidagi yozuv — saqlanmaydi);
#   3) sessiya toza: kutilayotgan o'zgarish (`new` / `dirty` / `deleted`) yo'q va ulanish shu tranzaksiyada yozmagan —
#      yozuvchi yo'l (o'z tranzaksiyasi ichida hisobot o'qisa) ASL hisobni oladi;
#   4) natija faqat oddiy ma'lumot (dict / list / matn / son / sana / Decimal) — ORM obyekti bo'lsa saqlanmaydi;
#   5) yoshi `HISOBOT_XOTIRASI_MUDDAT` dan kichik (boshqa jarayon / nusxa yozuvlarini bu jarayon ko'rmaydi — eskirish
#      chegarasi); bir nechta ishchi (`WEB_CONCURRENCY` > 1) bo'lsa xotira umuman ishlamaydi.
# Kalit: funksiya nomi, dvigatel, argumentlar (korxona, yil, oy …), oy kesimi (`tashkent_oy_kesimi` — «shu kunlar» bilan
# solishtirish), Toshkent sanasi. Bir kalit bir vaqtda bir marta hisoblanadi (parallel so'rovlar kutadi — kalit qulfi).
# `HISOBOT_XOTIRASI_YOQIQ = False` — xotira butunlay o'chadi (test: xotira bilan va xotirasiz natija AYNAN).
import copy as _copy_hx
import inspect as _inspect_hx
import os as _os_hx
import threading as _threading_hx
import time as _time_hx
import datetime as _dt_hx
from decimal import Decimal as _Decimal_hx

HISOBOT_XOTIRASI_YOQIQ = True
HISOBOT_XOTIRASI_MUDDAT = 60.0        # soniya
HISOBOT_XOTIRASI_HAJM = 256           # yozuvlar soni (eng eskisi chiqariladi)
_HX = {}                              # kalit -> (versiya, vaqt, nusxa)
_HX_QULF = _threading_hx.Lock()
_HX_KALIT_QULFI = {}
_HX_STAT = {"topildi": 0, "hisoblandi": 0, "saqlandi": 0, "rad": 0}


def hisobot_xotirasi_holati():
    """Xotira hisoblagichlari (testlar va o'lchov uchun): topildi / hisoblandi / saqlandi / rad / yozuvlar."""
    with _HX_QULF:
        _s = dict(_HX_STAT)
        _s["yozuvlar"] = len(_HX)
    return _s


def hisobot_xotirasini_tozala():
    """Xotirani va hisoblagichlarni tozalaydi."""
    with _HX_QULF:
        _HX.clear()
        _HX_KALIT_QULFI.clear()
        for _k in _HX_STAT:
            _HX_STAT[_k] = 0


def _hx_bitta_ishchi():
    _w = (_os_hx.environ.get("WEB_CONCURRENCY") or "").strip()
    if not _w:
        return True
    try:
        return int(_w) <= 1
    except ValueError:
        return False


_HX_ODDIY = (str, int, float, bool, _Decimal_hx, _dt_hx.date, _dt_hx.time, _dt_hx.timedelta)


def _hx_oddiymi(x, _ch=0):
    """Qiymat faqat oddiy ma'lumotdanmi (ORM obyekti, funksiya va h.k. — YO'Q)."""
    if _ch > 60:
        return False
    if x is None or isinstance(x, _HX_ODDIY):
        return True
    if isinstance(x, dict):
        return all((_k is None or isinstance(_k, _HX_ODDIY) or isinstance(_k, tuple)) and _hx_oddiymi(_v, _ch + 1)
                   for _k, _v in x.items())
    if isinstance(x, (list, tuple)):
        return all(_hx_oddiymi(_v, _ch + 1) for _v in x)
    return False


def _hx_sessiya_tozami(db):
    """Sessiyada kutilayotgan o'zgarish yo'q va ulanish joriy tranzaksiyada yozmagan."""
    try:
        if db.new or db.dirty or db.deleted:
            return False
        if db.in_transaction():
            from database import ulanish_yozganmi as _uy_hx
            return not _uy_hx(db.connection())
        return True
    except Exception:
        return False


def _hx_kalit_qulfi(kalit):
    with _HX_QULF:
        _q = _HX_KALIT_QULFI.get(kalit)
        if _q is None:
            if len(_HX_KALIT_QULFI) > 4 * HISOBOT_XOTIRASI_HAJM:
                # band bo'lmagan eski qulflar chiqariladi (kalitlarda sana bor — ro'yxat cheksiz o'smasin)
                for _k in [_k for _k, _l in _HX_KALIT_QULFI.items() if not _l.locked()]:
                    _HX_KALIT_QULFI.pop(_k, None)
            _q = _threading_hx.Lock()
            _HX_KALIT_QULFI[kalit] = _q
        return _q


def _hx_ol(kalit, versiya):
    """Yaroqli nusxa (yangi `deepcopy`) yoki `_HK_YOQ`."""
    with _HX_QULF:
        _y = _HX.get(kalit)
        if _y is None:
            return _HK_YOQ
        _v, _t, _n = _y
        if _v != versiya or (_time_hx.monotonic() - _t) >= HISOBOT_XOTIRASI_MUDDAT:
            _HX.pop(kalit, None)
            return _HK_YOQ
        _HX_STAT["topildi"] += 1
    return _copy_hx.deepcopy(_n)


def _hx_qoy(kalit, versiya, natija):
    _n = _copy_hx.deepcopy(natija)
    with _HX_QULF:
        _HX[kalit] = (versiya, _time_hx.monotonic(), _n)
        _HX_STAT["saqlandi"] += 1
        while len(_HX) > HISOBOT_XOTIRASI_HAJM:
            _HX.pop(next(iter(_HX)), None)


def _hisobot_xotirasi_bilan(fn):
    """Dekorator (kech120): `fn(db, …)` natijasi HISOBOT XOTIRASI qoidalari bilan so'rovlar orasida eslab qolinadi."""
    _sig = _inspect_hx.signature(fn)
    _nom = getattr(fn, "__name__", "hisobot")

    @_functools_hk.wraps(fn)
    def _o(*args, **kwargs):
        if not (HISOBOT_XOTIRASI_YOQIQ and _hx_bitta_ishchi()):
            return fn(*args, **kwargs)
        try:
            from database import yozuv_versiyasi as _yv_hx, _OY_KESIMI as _kesim_hx
            _ba = _sig.bind(*args, **kwargs)
            _ba.apply_defaults()
            _db = _ba.arguments.get("db")
            _arg = tuple((_k, _v) for _k, _v in _ba.arguments.items() if _k != "db")
            hash(_arg)
            _kalit = (_nom, id(_db.get_bind()), _arg, _kesim_hx.get(), _tashkent_date().isoformat())
        except Exception:
            return fn(*args, **kwargs)
        if not _hx_sessiya_tozami(_db):
            with _HX_QULF:
                _HX_STAT["rad"] += 1
            return fn(*args, **kwargs)
        _n = _hx_ol(_kalit, _yv_hx())
        if _n is not _HK_YOQ:
            return _n
        _q = _hx_kalit_qulfi(_kalit)
        _olindi = _q.acquire(timeout=30)
        try:
            if _olindi:
                _n = _hx_ol(_kalit, _yv_hx())
                if _n is not _HK_YOQ:
                    return _n
            _v0 = _yv_hx()
            with _HX_QULF:
                _HX_STAT["hisoblandi"] += 1
            natija = fn(*args, **kwargs)
            if _yv_hx() == _v0 and _hx_sessiya_tozami(_db) and _hx_oddiymi(natija):
                _hx_qoy(_kalit, _v0, natija)
            return natija
        finally:
            if _olindi:
                _q.release()
    _o.asl_funksiya = fn
    return _o



def _hk_ol(db, bolim, kalit):
    """Keshdagi qiymat yoki `_HK_YOQ` (kesh yo'q yoki kalit yo'q)."""
    _k = _hk(db)
    if _k is None:
        return _HK_YOQ
    return _k.d.get(bolim, {}).get(kalit, _HK_YOQ)


def _hk_qoy(db, bolim, kalit, qiymat):
    """Kesh bo'lsa — eslab qoladi. Qiymatni qaytaradi."""
    _k = _hk(db)
    if _k is not None:
        _k.d.setdefault(bolim, {})[kalit] = qiymat
    return qiymat


def _hk_std_peno(db, company_id):
    """`get_default_penoplast(db, company_id=company_id)` — hisobot davomida bir marta."""
    _x = _hk_ol(db, "std", company_id)
    if _x is not _HK_YOQ:
        return _x
    _p = get_default_penoplast(db, company_id=company_id)
    _hk_qoy(db, "std", company_id, _p)
    if _p is not None:
        _hk_qoy(db, "inv", _p.id, _p)
    return _p


def _korxona_materiali(db, pid, company_id):
    """kech99 (112-band): material (penoplast / blok) `id` bo'yicha — FAQAT shu korxonadan.

    O'LCHANGAN (`work/probe112.py`, SQLite = PG): foyda hisobi (`calculate_order_profit`) va hajm
    (`_item_volume_m3`) materialni korxonasiz (`Inventory.id == pid`) qidirardi — A detali B penoplastiga ishora
    qilsa (faqat Core bilan: eski / ko'chirilgan ma'lumot; ORM `_TENANT_REFS` yo'l qo'ymaydi) B narxi va hajmi
    olinardi (profil 0.05 m³ × 400 000 — A narxi 500 000; blok hajmi B ning 0.25 m³ i bilan). Ombordan yechish
    (`_peno_of`) va oylik hisobot (`_inv_rep`) esa begona pozitsiyani "topilmaydi" deb o'tkazib yuborardi — endi
    hammasi BIR qoida: begona material na hisobda, na omborda qatnashadi. `company_id` None — asl korxonasiz
    qidiruv.

    Hisobot keshi: "inv" (id -> qator) o'qilganda korxona tekshiriladi; keshda yo'q — korxonali so'rov, topilgan
    qator "inv" ga, topilmagani "inv_begona" ga ((id, korxona) — shu korxona uchun qayta so'ralmaydi)."""
    if not pid:
        return None
    _x = _hk_ol(db, "inv", pid)
    if _x is not _HK_YOQ:
        return _x if (_x is None or company_id is None or _x.company_id == company_id) else None
    if company_id is not None and _hk_ol(db, "inv_begona", (pid, company_id)) is True:
        return None
    _q = db.query(Inventory).filter(Inventory.id == pid)
    if company_id is not None:
        _q = _q.filter(Inventory.company_id == company_id)
    _p = _q.first()
    if _p is not None or company_id is None:
        _hk_qoy(db, "inv", pid, _p)
    else:
        _hk_qoy(db, "inv_begona", (pid, company_id), True)
    return _p


def _retsept_materiali(ing, recipe):
    """kech99 (112-band): retsept ingredientining materiali — FAQAT retseptning O'Z korxonasidan.

    `recipe.ingredients` → `ing.inventory` munosabati korxonasiz. 2026-09-21 (12-sizish) dan beri yangi ingredient
    faqat o'z materiali bilan yoziladi, lekin undan OLDINGI (yoki Core bilan yozilgan) ingredient begona materialga
    ishora qilishi mumkin. O'LCHANGAN (`work/probe112.py`): A retseptining ingredienti B materialiga — A ning
    yetishmovchilik xabarida B material nomi va qoldig'i, `get_loy_cost_per_kg` / foyda B narxi bilan; loy yechish /
    qaytarish B omboriga yozmoqchi bo'lib ORM qo'riqchisida 409 (A buyurtmasini yaratish, "Tayyor", loy rejasi,
    o'chirish — hammasi rad). Endi begona ingredient o'tkazib yuboriladi (penoplast `_peno_of` qoidasi)."""
    _inv = getattr(ing, "inventory", None)
    if _inv is None:
        return None
    _rcid = getattr(recipe, "company_id", None)
    if _rcid is not None and getattr(_inv, "company_id", None) != _rcid:
        return None
    return _inv


def _hk_bolaklar(qator, n=500):
    """IN ro'yxatini bo'laklarga bo'ladi (SQLite parametr chegarasi)."""
    qator = list(qator)
    for i in range(0, len(qator), n):
        yield qator[i:i + n]


def _hk_tayyorla(db, orders):
    """Buyurtmalar ro'yxati uchun keyingi o'qishlarni OLDINDAN yuklaydi (kesh yo'q bo'lsa — hech narsa):
    detallar + ichki detallar + usta (munosabatning O'Z yuklovchisi — lazy bilan bir xil shart va tartib:
    detallar ORDER BY siz, ichki detallar `id` bo'yicha), brak EMAS harakatlar (`id` tartibida), tugagan
    PO lar, materiallar (detal penoplasti, harakat materiali, standart penoplast), TM lar. Hammasi
    buyurtmalarning O'Z korxonasi bilan cheklangan; korxonasiz (eski) buyurtma — keshsiz (asl yo'l)."""
    _k = _hk(db)
    if _k is None:
        return
    _bu = _k.d.setdefault("buyurtma", {})
    yangi = []
    for o in orders or []:
        _oid = getattr(o, "id", None)
        if _oid is None or getattr(o, "company_id", None) is None or _oid in _bu:
            continue
        _bu[_oid] = o
        yangi.append(o)
    if not yangi:
        return
    from sqlalchemy import not_ as _not_hk
    from sqlalchemy.orm import selectinload as _sil_hk
    from models import InventoryMovement, FinishedProduct
    import crud as _crud_hk
    ids = [o.id for o in yangi]
    cids = sorted({o.company_id for o in yangi})
    # 1) detallar, ichki detallar, usta — identity map dagi O'SHA buyurtma obyektlariga yuklanadi.
    for _b in _hk_bolaklar(ids):
        db.query(Order).filter(Order.id.in_(_b), Order.company_id.in_(cids)).options(
            _sil_hk(Order.items).selectinload(OrderItem.sub_details),
            _sil_hk(Order.master),
            # kech102 (144-band): qaytarish hodisalari (`_qaytarish_hodisalari`) — buyurtma boshiga so'rov o'rniga
            _sil_hk(Order.returns)).all()
    items = [it for o in yangi for it in (o.items or [])]
    item_ids = [it.id for it in items]
    # 2) harakatlar — `_buyurtma_sarf_narxlari` sharti (brak EMAS), `id` tartibida.
    _har = _k.d.setdefault("harakat", {})
    _t = {oid: [] for oid in ids}
    for _b in _hk_bolaklar(ids):
        for h in db.query(InventoryMovement).filter(
                InventoryMovement.order_id.in_(_b),
                _not_hk(_crud_hk.brak_harakati_sharti(InventoryMovement)),
                InventoryMovement.company_id.in_(cids)).order_by(InventoryMovement.id).all():
            _t[h.order_id].append(h)
    _har.update(_t)
    # 3) tugagan ishlab chiqarish buyurtmalari (MRP detali tannarxi) — ORDER BY siz (asl so'rov kabi).
    try:
        from production_models import ProductionOrder
        _tp = {iid: [] for iid in item_ids}
        for _b in _hk_bolaklar(item_ids):
            for p in db.query(ProductionOrder).filter(
                    ProductionOrder.source_order_item_id.in_(_b),
                    ProductionOrder.status == "completed",
                    ProductionOrder.company_id.in_(cids)).all():
                _tp[p.source_order_item_id].append(p)
        _k.d.setdefault("po", {}).update(_tp)
    except Exception:
        pass    # asl kod ham PO xatosini yutadi — keshsiz qoladi (har detal asl so'rov bilan)
    # 4) materiallar
    for _c in cids:
        _hk_std_peno(db, _c)
    _inv = _k.d.setdefault("inv", {})
    _iids = {it.penoplast_id for it in items if getattr(it, "penoplast_id", None)}
    for oid in ids:
        _iids |= {h.inventory_id for h in _t[oid] if h.inventory_id}
    _iids = sorted(i for i in _iids if i not in _inv)
    for _b in _hk_bolaklar(_iids):
        for inv in db.query(Inventory).filter(Inventory.id.in_(_b), Inventory.company_id.in_(cids)).all():
            _inv[inv.id] = inv
    # 5) tayyor mahsulotlar (TM detal) — kalit (id, korxona): asl so'rov buyurtma korxonasi bilan.
    _fids = sorted({it.finished_product_id for it in items if getattr(it, "finished_product_id", None)})
    _tm = _k.d.setdefault("tm", {})
    for _b in _hk_bolaklar(_fids):
        for fp in db.query(FinishedProduct).filter(FinishedProduct.id.in_(_b),
                                                   FinishedProduct.company_id.in_(cids)).all():
            _tm[(fp.id, fp.company_id)] = fp


def _hk_loyihalar(db, projects):
    """kech90 (110-band): loyihalar ro'yxatidagi "Tayyor" buyurtmalarni `_hk_tayyorla` bilan oldindan o'qiydi
    (kesh yo'q bo'lsa — hech narsa, asl yo'l).

    kech97 (114 / 116-band): `Project.orders` ro'yxatlarini chaqiruvchi oldindan (selectinload, bitta IN so'rovi)
    yuklaydi. kech90 da ular ATAYLAB lazy qoldirilgan edi — PG da `project_id = ?` va `project_id IN (...)`
    so'rovlari ORDER BY siz TURLI tartib qaytarardi (kech90 `probe90_tartib`: 6 dan 2 loyihada), tartib esa foyda
    yig'indisi tartibini belgilaydi. Endi munosabatda `order_by=Order.id` — ikkala yo'l ham AYNAN id tartibida."""
    if _hk(db) is None or not projects:
        return
    from models import OrderStatus as _OS_hk
    _hk_tayyorla(db, [o for p in projects for o in (p.orders or []) if o.status == _OS_hk.READY])


# kech90 (110-band): bosh sahifa "bugun" (`/api/dashboard/today`) — hisobot keshi ichida (yuqorida aniqlangan).
get_today_stats = _hisobot_keshi_bilan(get_today_stats)
# kech97 (116-band): majburiyatlar holati (Qarzdorlar sahifasi, Moliya qarz xulosasi, PDF) 3 oylik hisobotni chaqiradi —
# endi ular BITTA kesh bilan (tarix kabi; ichma-ich chaqiruvda tashqi kesh ishlatiladi), natija AYNAN.
get_company_obligations_status = _hisobot_keshi_bilan(get_company_obligations_status)


def _buyurtma_sarf_narxlari(db: Session, order) -> Dict:
    """{inventory_id: shu buyurtmada 1 birlik narxi} — `_buyurtma_sarf_hisobi` dan (qoidalar o'sha yerda).
    kech107 (36-band): hisob (sof miqdor ham) alohida funksiyaga ajratildi — qoplamaning tayyor loy zaxirasidan olingan
    qismi uchun miqdor ham kerak; narxlar AYNAN avvalgidek."""
    return {_iid: _narx for _iid, (_miqdor, _narx) in _buyurtma_sarf_hisobi(db, order).items()}


def _buyurtma_sarf_hisobi(db: Session, order) -> Dict:
    """kech48 (K47-1, 5-bo'lim 32-band) — FOYDALANUVCHI QARORI (kech47, tugma):
    "Ishlatilgan paytdagi narxda muzlatilsin".

    Buyurtma tan narxi (`calculate_order_profit`) xomashyoni JORIY narx bilan
    baholardi: penoplast yoki kley narxi o'zgarsa, O'TGAN buyurtmalar foydasi
    va o'tgan oylarning sof foydasi orqaga qarab o'zgarardi (JONLI O'LCHANGAN,
    kech47: penoplast 276 narxi x2 bo'lganda 2026-09 sof foydasi −11.38 mln
    so'mga siljidi; lokal `work/probe47.py`: narxlar x3 → tan narx x3).

    Qaytaradi: {inventory_id: (sof miqdor, shu buyurtmada 1 birlik narxi)} — faqat
    shu buyurtmaning ombor harakatlarida uchragan materiallar uchun (kech107: miqdor
    ham — hammasi qaytgan bo'lsa 0, narx — oxirgi ma'lum).

    Manba — shu buyurtmaning (`order_id`, korxona) harakatlari, `id` (vaqt)
    tartibida, O'RTACHA TANNARX usulida:
      * chiqim ("out") — miqdor × `unit_cost` (chiqim paytidagi narx, zip 47
        dan beri `crud.log_movement` yozadi); `unit_cost` i yo'q ESKI harakat —
        joriy narx (brak hisobotidagi `_harakat_narxi` qoidasi bilan bir xil);
      * kirim ("in" — tahrirda kamaytirish, loy xomashyosining qaytishi) —
        o'sha paytdagi o'rtacha narxda ayiriladi (qolgan qism narxi o'zgarmaydi);
        chiqimdan oldingi kirim (jurnal yozilmagan eski chiqim) — e'tiborsiz.
    BRAK harakatlari (kech52: `crud.brak_harakati_sharti` — `is_brak` belgisi,
    belgisiz eski harakat — `return_item_id` bor YOKI sabab "Brak%"; brak
    xarajati `crud.get_brak_material_summary` da AYNAN shu shart bilan alohida
    hisoblanadi) kirmaydi — aks holda brak narxi buyurtma narxiga aralashardi.
    Harakati yo'q material (jurnal yozilmagan eski buyurtma, to'liq tayyor loy
    zaxirasidan olingan qoplama) lug'atda YO'Q — chaqiruvchi JORIY narxni
    oladi (avvalgi xulq, eski narx noma'lum — taxmin qilinmaydi).
    """
    from models import InventoryMovement as _IMv
    from sqlalchemy import not_ as _not_sn
    import crud as _crud_sn
    _oid_sn = getattr(order, "id", None)
    if _oid_sn is None:
        return {}
    _cid_sn = getattr(order, "company_id", None)
    _x_h = _hk_ol(db, "harakat", _oid_sn)
    if _x_h is not _HK_YOQ:
        # kech89 (52-band): hisobot keshidan — asl sharti (brak EMAS, `id` tartibi) bilan oldindan
        # o'qilgan; korxona sharti shu yerda (asl so'rovdagidek).
        harakatlar = [h for h in _x_h if _cid_sn is None or h.company_id == _cid_sn]
    else:
        _hq = db.query(_IMv).filter(
            _IMv.order_id == _oid_sn,
            _not_sn(_crud_sn.brak_harakati_sharti(_IMv)),
        )
        if _cid_sn is not None:
            _hq = _hq.filter(_IMv.company_id == _cid_sn)
        harakatlar = _hq.order_by(_IMv.id).all()
    if not harakatlar:
        return {}
    _inv_ids = {h.inventory_id for h in harakatlar if h.inventory_id}
    joriy = {}
    if _inv_ids:
        # kech99 (112-band): shu korxonada yo'qligi keshda ma'lum ("inv_begona") id — "topilmadi" (qayta so'ralmaydi)
        _x_j = [(None if (_cid_sn is not None and _hk_ol(db, "inv_begona", (_i, _cid_sn)) is True)
                 else _hk_ol(db, "inv", _i)) for _i in _inv_ids]
        if all(_x is not _HK_YOQ for _x in _x_j):
            # kech89 (52-band): hammasi keshda (id bo'yicha) — korxona sharti asl so'rovdagidek
            for _inv_sn in _x_j:
                if _inv_sn is not None and (_cid_sn is None or _inv_sn.company_id == _cid_sn):
                    joriy[_inv_sn.id] = float(_inv_sn.price_per_unit or 0)
        else:
            _jq = db.query(Inventory).filter(Inventory.id.in_(_inv_ids))
            if _cid_sn is not None:
                _jq = _jq.filter(Inventory.company_id == _cid_sn)
            for _inv_sn in _jq.all():
                joriy[_inv_sn.id] = float(_inv_sn.price_per_unit or 0)
                _hk_qoy(db, "inv", _inv_sn.id, _inv_sn)
            if _cid_sn is not None:
                for _i in _inv_ids:
                    if _i not in joriy:
                        _hk_qoy(db, "inv_begona", (_i, _cid_sn), True)
    hisob = {}   # inventory_id -> [miqdor, qiymat, oxirgi o'rtacha narx]
    for h in harakatlar:
        if not h.inventory_id:
            continue
        miqdor = float(h.quantity or 0)
        if miqdor <= 0:
            continue
        x = hisob.setdefault(h.inventory_id, [0.0, 0.0, None])
        if h.movement_type == "out":
            narx = float(h.unit_cost) if h.unit_cost is not None else joriy.get(h.inventory_id, 0.0)
            x[0] += miqdor
            x[1] += miqdor * narx
            x[2] = x[1] / x[0]
        elif h.movement_type == "in":
            if x[0] <= 1e-12:
                continue
            ortacha = x[1] / x[0]
            olindi = min(miqdor, x[0])
            x[0] -= olindi
            x[1] -= olindi * ortacha
            if x[0] <= 1e-12:
                x[0], x[1] = 0.0, 0.0
    natija = {}
    for _iid_sn, (m, v, oxirgi) in hisob.items():
        if m > 1e-12:
            natija[_iid_sn] = (m, v / m)
        elif oxirgi is not None:
            # Hammasi qaytgan (jurnal bo'yicha) — oxirgi ma'lum narx.
            natija[_iid_sn] = (0.0, oxirgi)
    return natija


def _buyurtma_zaxira_loyi(db: Session, order, recipe, sarf_hisobi: Dict) -> tuple:
    """kech107 (36-band) — shu buyurtma qoplama loyining TAYYOR LOY ZAXIRASIDAN olingan qismi: (sof kg, 1 kg narxi).

    Manba — buyurtmaning o'sha retsept tayyor loy pozitsiyasi harakatlari (`_buyurtma_sarf_hisobi` — o'rtacha tannarx
    usuli, brak harakatlarisiz), narx — zaxiradan OLINGAN paytdagi retsept tannarxi (`take_loy_from_stock`). Pozitsiya
    topilmasa, harakati yo'q yoki narxi noma'lum (tuzatishdan oldingi harakat — 0 / NULL) — (0.0, None): chaqiruvchi
    butun loyni avvalgi qoidada baholaydi. Pozitsiya YARATILMAYDI (faqat o'qiladi)."""
    from models import Inventory as _InvZ
    if recipe is None or not sarf_hisobi:
        return 0.0, None
    _nom = recipe.name.value if hasattr(recipe.name, 'value') else str(recipe.name)
    _cid = getattr(order, "company_id", None)
    _kalit = (f"Tayyor loy ({_nom})", _cid)
    _x_z = _hk_ol(db, "zaxira_loy", _kalit)
    if _x_z is _HK_YOQ:
        _zq = db.query(_InvZ.id).filter(_InvZ.item_name == _kalit[0])
        if _cid is not None:
            _zq = _zq.filter(_InvZ.company_id == _cid)
        _zr = _zq.order_by(_InvZ.id).first()
        _x_z = _zr[0] if _zr else None
        _hk_qoy(db, "zaxira_loy", _kalit, _x_z)
    if _x_z is None or _x_z not in sarf_hisobi:
        return 0.0, None
    _kg, _narx = sarf_hisobi[_x_z]
    if not _narx or _narx <= 0 or _kg <= 1e-12:
        return 0.0, None
    return float(_kg), float(_narx)


def _mrp_detal_tannarxi(db: Session, order, item, po_royxat) -> float:
    """kech101 (138-band) — MRP detalining buyurtma tannarxidagi ulushi.

    O'LCHANGAN (asl kod = zip 94, `work/probe138.py`, SQLite = PG): tannarx — detalga bog'langan YAKUNLANGAN ishlab chiqarish
    buyurtmalarining BUTUN `total_cost` i edi. 10 dona ishlab chiqarilib 4 tasi topshirilgach buyurtma yakunlansa (qisman
    «Tayyor» yoki o'chirish — kech100 K100-3a: qolgan 6 dona band dan ERKIN omborga o'tadi) buyurtma tannarxi 30 000 (10 dona)
    qolardi, erkin 6 dona sotilganda yana 18 000 — oylik hisobotda 30 000 lik ishlab chiqarish uchun 48 000 xarajat (M1 / M2);
    ikki ishlab chiqarish (4 × 3 000 + 6 × 6 000) — 84 000 (to'g'risi 48 000, M6). Boshqa turlar (profil, tayyor mahsulotdan
    olingan) yakunlashda miqdor topshirilganga tushib, qolgan qism omborga qaytgani uchun tannarx O'ZI kamayadi — MRP esa
    miqdorga qaramasdi.

    Qoida: har ishlab chiqarish buyurtmasi (Q dona, T so'm) uchun SHU buyurtma ISHLATGAN dona — yuk xatlarida o'sha tayyor
    mahsulotdan olingani (`DeliveryItem.mrp_olingan`) + hali shu detalga BAND qolgani; tannarx = T × ishlatilgan / Q (hammasi
    ishlatilgan bo'lsa — AYNAN T, yaxlitlash siljishi yo'q). Detal miqdori ishlab chiqarilganidan kam bo'lmasa (odatiy holat —
    hech narsa bo'shamagan, jarayondagi buyurtma ham, kech59 J: topshirish tannarxni kamaytirmaydi) — AYNAN asl qoida (T yig'indisi,
    qo'shimcha so'rov yo'q). Manbasi yozilmagan (kech71 dan oldingi) yuk xati bo'lsa — asl qoida (taxmin qilinmaydi)."""
    jami = 0.0
    miqdor = 0.0
    for _p in po_royxat:
        jami += float(_p.total_cost or 0)
        miqdor += float(_p.quantity or 0)
    # kech102 (K102-1, 138-band qoldig'i — O'LCHANGAN `work/probe144.py` mrp-A-O, SQLite = PG): "Ortiqcha" qaytarilgan
    # (topshirilmagan — band → erkin omborga) dona detal miqdorida qoladi (yakunlashda miqdor = topshirilgan + ortiqcha);
    # miqdor ishlab chiqarilganga teng bo'lgani uchun asl qoida BUTUN T ni olardi — 10 dan 4 tasi omborga qaytib, keyin
    # sotilsa ular IKKI marta (30 000 o'rniga 42 000). Shart endi ortiqchasiz miqdor bilan (ortiqcha yo'q — AYNAN asl).
    if miqdor <= 0 or float(item.quantity or 0) - float(getattr(item, "ortiqcha_qty", 0) or 0) >= miqdor - 1e-6:
        return jami
    import crud as _crud138
    from models import Delivery as _D138, DeliveryItem as _DI138, FinishedProduct as _FP138
    olingan = {}
    _dq = db.query(_DI138).join(_D138, _D138.id == _DI138.delivery_id).filter(
        _D138.order_id == order.id, _DI138.order_item_id == item.id)
    if getattr(order, 'company_id', None) is not None:
        _dq = _dq.join(Order, Order.id == _D138.order_id).filter(Order.company_id == order.company_id)
    for _di in _dq.order_by(_DI138.id).all():
        _o = _crud138._mrp_olingan_oqi(_di)
        if _o is None:
            if float(_di.quantity or 0) > 1e-9:
                return jami
            continue
        for _tm, _q in _o:
            olingan[_tm] = olingan.get(_tm, 0.0) + float(_q)
    _fp_idlar = [_p.finished_product_id for _p in po_royxat if _p.finished_product_id]
    tmlar = {}
    if _fp_idlar:
        _fq = db.query(_FP138).filter(_FP138.id.in_(_fp_idlar))
        if getattr(order, 'company_id', None) is not None:
            _fq = _fq.filter(_FP138.company_id == order.company_id)
        tmlar = {_f.id: _f for _f in _fq.all()}
    natija = 0.0
    for _p in po_royxat:
        _Q = float(_p.quantity or 0)
        _T = float(_p.total_cost or 0)
        if _Q <= 0:
            continue
        _ishlatilgan = olingan.get(_p.finished_product_id, 0.0)
        _f = tmlar.get(_p.finished_product_id)
        if _f is not None and _f.reserved_for_order_item_id == item.id:
            _ishlatilgan += float(_f.reserved_quantity or 0)
        natija += _T if _ishlatilgan >= _Q - 1e-6 else _T * _ishlatilgan / _Q
    return natija


# ── 144-band (kech102): QAYTARISH — daromad va tannarx QAYSI davrga tushadi ──────────────────────────────────
# FOYDALANUVCHI QARORI (kech102, 2026-09-27): "Qaytarish oyida" — o'tgan oylar O'ZGARMAYDI, qaytarish bo'lgan oyda
# alohida qator (daromad: mijozga qaytarilgan pul, tannarx: omborga qaytgan mahsulot tannarxi); usta KPI — "Ha,
# yo'qotilgan foydaga" (qaytarilgan pul − omborga qaytgan tannarx).
# O'LCHANGAN (asl kod `c89a22e`, SQLite = PG, `work/probe144.py`, 10 birlikdan 3 tasi qaytgan): omborga qaytgan
# mahsulot tannarxi IKKI marta hisoblanardi — buyurtma tannarxida (o'zgarmasdi) va qayta sotilganda (qaytgan TM
# tannarxi): profil +21 000, panel +41 100, tayyor mahsulotdan +18 000, MRP +9 000; "Pul qaytdi" esa buyurtmaning
# kelishilgan summasini kamaytirib, daromadni BUYURTMA yakunlangan (o'tgan) oyda o'zgartirardi (−150 000, joriy oy 0).
# Qoida (bitta manba): buyurtmaning qaytarish HODISALARI — "pul" (`refunded_at`; `refund_agreed_delta` — kelishilgan
# summa AYNAN qanchaga kamaygani) va "ombor" (`returned_at`; `stock_cost` — omborga qo'yilgan TM tannarxi).
# `calculate_order_profit(..., holat_vaqti=t)` — t dan OLDINGI hodisalar qo'llangan holat (None — hammasi, hozirgi
# holat). Davr hisobotlarida buyurtma — yakunlangan paytdagi holatda (`yakun_foydasi`, `yakun_daromadi`);
# yakunlanishdan KEYINGI hodisa — o'zi bo'lgan davrda (`davr_qaytarishlari`: holat(t + 1 mks) − holat(t)).
# Brak — hodisa EMAS (pul qaytarilmaydi, omborga tushmaydi, xomashyosi — alohida brak xarajati). Eski yozuvlar
# (`refunded_at` / `stock_cost` bo'sh — kech40 dan oldin) — qancha ekani yozilmagan, taxmin qilinmaydi (avvalgidek).
def _qaytarish_hodisalari(db: Session, order) -> list:
    """Buyurtmaning qaytarish hodisalari: [(tur, vaqt, summa, qaytarish)] — tur "pul" (kelishilgan summa `summa` ga
    kamaygan) yoki "ombor" (omborga `summa` tannarxli mahsulot qaytgan). Faqat buyurtma korxonasining brakdan boshqa
    yozuvlari (`crud.pul_qaytarish_kamaytirgan` bilan bir shart). Manba — `Order.returns` (hisobot keshida oldindan
    yuklangan — `_hk_tayyorla`)."""
    from models import ReturnReason as _RR144
    if order is None or getattr(order, "id", None) is None:
        return []
    _cid = getattr(order, "company_id", None)
    natija = []
    for r in (order.returns or []):
        if _cid is not None and r.company_id != _cid:
            continue
        if r.reason == _RR144.DEFECT:
            continue
        _d = float(r.refund_agreed_delta or 0)
        if r.is_refunded and r.refunded_at is not None and _d > 0:
            natija.append(("pul", r.refunded_at, _d, r))
        _s = float(r.stock_cost or 0)
        if r.finished_product_id is not None and r.returned_at is not None and _s > 0:
            natija.append(("ombor", r.returned_at, _s, r))
    return natija


def _yakun_vaqti(order):
    """Buyurtma yakunlangan payt («Tayyor» — READY va `completed_at` bor) yoki None."""
    if order is None:
        return None
    if getattr(order, "status", None) == OrderStatus.READY and getattr(order, "completed_at", None) is not None:
        return order.completed_at
    return None


def yakun_daromadi(db: Session, order) -> float:
    """Buyurtma YAKUNLANGAN paytdagi daromad: joriy kelishilgan summa + yakunlanishdan keyin "Pul qaytdi" bilan
    kamaygan qism (u qaytarish bo'lgan davrda hisoblanadi — `davr_qaytarishlari`)."""
    _s = float(order.kelishilgan_summa)
    _t = _yakun_vaqti(order)
    if _t is None:
        return _s
    return _s + sum(summa for tur, vaqt, summa, _r in _qaytarish_hodisalari(db, order)
                    if tur == "pul" and vaqt >= _t)


def yakun_foydasi(db: Session, order, company_id: int = None) -> Dict:
    """`calculate_order_profit` — buyurtma yakunlangan paytdagi holatda (davr hisobotlari uchun)."""
    return calculate_order_profit(db, order.id, company_id=company_id, holat_vaqti=_yakun_vaqti(order))


def davr_qaytarishlari(db: Session, boshi, oxiri, company_id: int = None, master_id: int = None,
                       oraliq: str = "[)") -> list:
    """`boshi` … `oxiri` oralig'ida (standart [boshi, oxiri); `oraliq` — "(]" va h.k.) bo'lgan, buyurtma
    YAKUNLANGANDAN keyingi qaytarish hodisalari — har bir paytga alohida:
    {"order", "order_id", "master_id", "vaqt", "tur", "daromad", "tannarx", "foyda", "gips"}. Qiymat — hodisadan
    keyingi va oldingi holat farqi (`calculate_order_profit(holat_vaqti=vaqt + 1 mks) − (holat_vaqti=vaqt)`) —
    usta haqi (foydadan %) ham shu farqqa kiradi; odatda daromad −(qaytarilgan pul), tannarx −(omborga qaytgan).
    Hisobot keshida natija eslab qolinadi (bir hisobotda oylik hisobot, KPI, ehson — bitta so'rov)."""
    from datetime import timedelta as _td144
    from sqlalchemy import or_ as _or144, and_ as _and144
    from models import ReturnItem as _RI144, ReturnReason as _RR144
    if boshi is None or oxiri is None:
        return []
    _eps = _td144(microseconds=1)
    a = boshi if oraliq[0] == "[" else boshi + _eps
    b = oxiri if oraliq[1] == ")" else oxiri + _eps
    _kalit = (a, b, company_id, master_id)
    _x = _hk_ol(db, "qaytarish_davr", _kalit)
    if _x is not _HK_YOQ:
        return _x
    _q = db.query(_RI144.order_id).join(Order, Order.id == _RI144.order_id).filter(
        _RI144.reason != _RR144.DEFECT,
        _RI144.company_id == Order.company_id,
        Order.status == OrderStatus.READY,
        Order.completed_at.isnot(None),
        Order.completed_at < b,
        _or144(
            _and144(_RI144.is_refunded.is_(True), _RI144.refunded_at >= a, _RI144.refunded_at < b),
            _and144(_RI144.finished_product_id.isnot(None), _RI144.returned_at >= a, _RI144.returned_at < b)))
    if company_id is not None:
        _q = _q.filter(Order.company_id == company_id, _RI144.company_id == company_id)
    if master_id is not None:
        _q = _q.filter(Order.master_id == master_id)
    _oids = sorted({_r[0] for _r in _q.distinct().all() if _r[0] is not None})
    natija = []
    if _oids:
        _oq = db.query(Order).filter(Order.id.in_(_oids))
        if company_id is not None:
            _oq = _oq.filter(Order.company_id == company_id)
        _orders = _oq.order_by(Order.id).all()
        _hk_tayyorla(db, _orders)
        for o in _orders:
            _c = o.completed_at
            _hod = _qaytarish_hodisalari(db, o)
            _vaqtlar = sorted({vaqt for _t, vaqt, _s, _r in _hod if a <= vaqt < b and vaqt >= _c})
            for _v in _vaqtlar:
                _p0 = calculate_order_profit(db, o.id, company_id=company_id, holat_vaqti=_v)
                _p1 = calculate_order_profit(db, o.id, company_id=company_id, holat_vaqti=_v + _eps)
                if not (_p0.get("success") and _p1.get("success")):
                    continue
                _shu = [(t, r, _s) for t, vaqt, _s, r in _hod if vaqt == _v]
                natija.append({
                    "order": o, "order_id": o.id, "master_id": o.master_id, "vaqt": _v,
                    "tur": "+".join(sorted({t for t, _r, _s in _shu})),
                    "daromad": float(_p1["sotuv_narxi"]) - float(_p0["sotuv_narxi"]),
                    "tannarx": float(_p1["tan_narxi"]) - float(_p0["tan_narxi"]),
                    "foyda": float(_p1["foyda"]) - float(_p0["foyda"]),
                    # kech117 (A2): hodisadagi qaytarishlar — (detal id, vazn: qaytarilgan pul / omborga qaytgan
                    # tannarx); yo'nalishlar hisoboti hodisani shu detallar yo'nalishiga taqsimlaydi (ilgari "gips" belgisi)
                    "detallar": [(getattr(r, "order_item_id", None), float(_s or 0)) for _t, r, _s in _shu],
                })
    _hk_qoy(db, "qaytarish_davr", _kalit, natija)
    return natija


def calculate_order_profit(db: Session, order_id: int, company_id: int = None, holat_vaqti=None) -> Dict:
    """
    Buyurtma uchun tan narxi va foyda hisoblaydi.

    Tan narxi = Penoplast xarajati + Qoplama xomashyosi xarajati
    Foyda = Sotuv narxi - Tan narxi

    M6 — TENANT: company_id berilsa, buyurtma FAQAT shu korxonadan olinadi.

    kech48 (K47-1, 5-bo'lim 32-band): xomashyo (penoplast, qoplama va loy
    sotish ingredientlari) shu buyurtmada ISHLATILGAN paytdagi narxda
    baholanadi (`_buyurtma_sarf_narxlari`) — keyingi narx o'zgarishi o'tgan
    buyurtma foydasini o'zgartirmaydi. Hajm / miqdor mantig'i O'ZGARMAGAN.

    kech102 (144-band): omborga qaytgan mahsulot tannarxi (`stock_cost`) buyurtma tannarxidan AYRILADI (qayta
    sotilganda TM sotuvi tannarxida — ikki marta emas). `holat_vaqti` — shu paytdan OLDINGI qaytarish hodisalari
    qo'llangan holat (keyingi "Pul qaytdi" qaytarib qo'shiladi, keyingi omborga qaytish ayrilmaydi); None — hozirgi
    holat (hammasi). Davr hisobotlari — `yakun_foydasi` (yakunlangan payt) + `davr_qaytarishlari`.
    """
    _x_o = _hk_ol(db, "buyurtma", order_id)
    if _x_o is not _HK_YOQ:
        # kech89 (52-band): hisobot keshi (`_hk_tayyorla`) — o'sha sessiya obyekti; korxona sharti
        # asl so'rovdagidek.
        order = _x_o if (company_id is None or _x_o.company_id == company_id) else None
    else:
        _oq = db.query(Order).filter(Order.id == order_id)
        if company_id is not None:
            _oq = _oq.filter(Order.company_id == company_id)
        order = _oq.first()
    if not order:
        return {"success": False, "message": "Buyurtma topilmadi"}

    # Kelishilgan (chegirmadan keyingi, haqiqatan mijoz to'laydigan) summadan
    # hisoblanadi — shunda har qanday chegirma (boshidagi ham, keyin
    # "kechirilgan" ham) foyda hisobotida to'g'ri, avtomatik hisobga olinadi.
    sotuv_narxi = order.kelishilgan_summa
    breakdown = []
    tan_narxi_jami = 0.0
    # kech117 (A2 — yo'nalishlar bo'yicha moliya): tannarxning QISMLARI (yig'indisi AYNAN `tan_narxi`) — qaysi detalga
    # tegishli (`detal_id`; None — buyurtma darajasidagi: penoplast hajmi, qoplama loyi, usta haqi). Yo'nalishlar
    # hisoboti (`calculate_split_profit_report`) tannarxni shu bo'yicha yo'nalishlarga taqsimlaydi. Hisob O'ZGARMAGAN.
    _tannarx_qismlari = []

    # ── 1. PENOPLAST XARAJATI ────────────────────────────────
    # MUHIM: har bir detal O'ZINING penoplast_id'siga (ya'ni aynan tanlangan
    # plotnost/narxga) qarab hisoblanadi — "birinchi topilgan Penoplast"
    # emas, chunki turli detallar turli plotnostdan bo'lishi mumkin
    # (buni biz alohida "1 m³ narxi" maydoni orqali qo'llab-quvvatlaymiz).
    default_penoplast = _hk_std_peno(db, getattr(order, "company_id", None))   # kech89: hisobotda bir marta

    # kech48 (K47-1): shu buyurtmada ishlatilgan paytdagi narxlar.
    # kech107 (36-band): hisob (sof miqdor + narx) bir marta — qoplamaning zaxira qismi uchun ham.
    _sarf_hisob = _buyurtma_sarf_hisobi(db, order)
    _sarf_narx = {_iid: _nx for _iid, (_mq, _nx) in _sarf_hisob.items()}

    def _narx(inv):
        """1 birlik narxi: shu buyurtmada muzlatilgan, bo'lmasa — joriy."""
        if inv is None:
            return 0.0
        if inv.id in _sarf_narx:
            return float(_sarf_narx[inv.id])
        return float(inv.price_per_unit or 0)

    penoplast_xarajat = 0.0
    penoplast_breakdown_by_item = {}  # penoplast_id -> {"vol": ..., "narx_per_m3": ...}
    _cid112 = getattr(order, "company_id", None)   # kech99 (112-band): materiallar FAQAT buyurtma korxonasidan
    for item in order.items:
        # MUHIM: "Tayyor mahsulotdan" tanlangan detallar — xomashyosi
        # ALLAQACHON, mahsulot birinchi marta ishlab chiqarilganda
        # ayirilgan. Bu hisobotda ularni QAYTA qo'shib hisoblasak — real
        # ombordan ayirilgandan KO'PROQ ko'rsatib yuboramiz.
        if getattr(item, 'finished_product_id', None):
            continue
        cat = (item.category or '').lower()
        qty = float(item.quantity or 1)
        vol = 0.0

        if cat == 'profil':
            if item.width and item.thickness and item.length:
                vol = (item.width/100) * (item.thickness/100) / 2 * float(item.length)
            # MUHIM (2026-09 audit): ichki qo'shimcha detallar (sub_details)
            # — asosiy detal bilan BIR XIL xomashyodan hisoblanadi, shuning
            # uchun ombordan chiqim/hajm hisobida (_item_volume_m3) ham
            # qo'shiladi. Bu yerda (foyda/tan narxi hisobi) shu vaqtgacha
            # QO'SHILMAGAN edi — natijada ichki detalli buyurtmalarning
            # tan narxi kamroq, foydasi esa haqiqatdan ko'proq ko'rsatilib
            # kelingan. Endi xuddi shu formula bilan qo'shiladi.
            vol += _sub_details_volume_m3(item)
        elif cat == 'panel':
            if item.width and item.thickness:
                vol = (item.width/100) * (item.thickness/100) * qty
        elif cat == 'dona':
            # TUZATILDI 2026-09-20. Bu yerda avval ALOHIDA, qo'lda yozilgan
            # nusxa turardi va u ombordan HAQIQATDA yechiladigan hajmdan
            # ikki jihatdan farq qilardi:
            #   1) 1 m³ ning TAN narxiga bo'lardi, detalning O'Z 1 m³ SOTUV
            #      narxiga (price_per_m3) emas — natijada hajm sotuv/tan
            #      nisbatiga (odatda ~1.9 barobar) shishib ketardi va
            #      tan narx = sotuv narx bo'lib, foyda har doim AYNAN 0
            #      chiqardi (matematik jihatdan boshqacha bo'lishi mumkin
            #      emas edi);
            #   2) 2026-08-16 da qo'shilgan o'lchamli ("1 metrdan necha
            #      dona") usulni umuman bilmasdi.
            # Endi hajm manbasi BITTA: _item_volume_m3 — ya'ni ombordan
            # qancha yechilsa, foyda hisobida ham aynan shuncha.
            _pid_dona = item.penoplast_id or (default_penoplast.id if default_penoplast else None)
            vol = _item_volume_m3(db, item, default_penoplast,
                                  penoplast_narxi=_sarf_narx.get(_pid_dona))

        elif cat == 'blok':
            # Blokdan chiqadigan mahsulot uchun — "length" maydonida
            # ISHLATILGAN BLOK SONI saqlanadi (metr emas). Hajm = blok soni
            # × 1 blokning hajmi (m³) — xuddi ombordan yechishda ishlatilgan
            # xuddi shu mantiq (deduct_inventory_for_order bilan bir xil).
            blok_soni = float(item.length or 0)
            pid_for_blok = item.penoplast_id or (default_penoplast.id if default_penoplast else None)
            p_blok = _korxona_materiali(db, pid_for_blok, _cid112)   # kech99 (112-band)
            if p_blok and p_blok.volume_per_unit and blok_soni > 0:
                vol = blok_soni * float(p_blok.volume_per_unit)

        if vol <= 0:
            continue

        # Shu detal o'zining penoplast_id'si (yoki standart) bo'yicha narxlanadi
        pid = item.penoplast_id or (default_penoplast.id if default_penoplast else None)
        if not pid:
            continue
        key = pid
        if key not in penoplast_breakdown_by_item:
            inv_item = _korxona_materiali(db, pid, _cid112)   # kech99 (112-band)
            # kech48 (K47-1): blok narxi — shu buyurtmada ishlatilgan paytdagi.
            # Narx 0 / yo'q bo'lsa — avvalgidek o'tkaziladi.
            _blok_narxi = _narx(inv_item)
            if not inv_item or not _blok_narxi or not inv_item.volume_per_unit:
                continue
            narx_per_m3 = _blok_narxi / float(inv_item.volume_per_unit)
            penoplast_breakdown_by_item[key] = {"vol": 0.0, "narx_per_m3": narx_per_m3, "nomi": inv_item.item_name}
        penoplast_breakdown_by_item[key]["vol"] += vol

    for pid, data in penoplast_breakdown_by_item.items():
        summa = data["vol"] * data["narx_per_m3"]
        if summa <= 0:
            continue
        breakdown.append({
            "nomi": f"{data['nomi']} ({son_korinish(data['vol'], 2)} m³ × {son_korinish(data['narx_per_m3'], 0)} so'm/m³)",   # kech119 (G2-15): «572 947», «0,02»
            "summa": summa
        })
        _tannarx_qismlari.append({"tur": "penoplast", "summa": summa, "detal_id": None})
        penoplast_xarajat += summa
    tan_narxi_jami += penoplast_xarajat

    # ── 1A. TAYYOR MAHSULOTDAN OLINGAN DETALLAR TAN NARXI ────
    # MUHIM: bu detallar uchun XOMASHYO (yuqoridagi Penoplast/Loy) ALOHIDA
    # HISOBLANMAYDI (chunki u — mahsulot birinchi marta ishlab
    # chiqarilganda, allaqachon ayirilgan). Lekin bu mahsulotning O'ZI —
    # BEPUL emas, uni ishlab chiqarish uchun xarajat ketgan. Shu xarajatni
    # shu yerda, alohida qatorda hisobga olamiz — aks holda "Sof foyda"
    # sun'iy oshirib ko'rsatilgan bo'lardi.
    from models import FinishedProduct as _FP_cost
    tayyor_mahsulot_xarajat = 0.0
    _tm_qismlari = []       # kech117 (A2): har detal ulushi
    for item in order.items:
        fpid = getattr(item, 'finished_product_id', None)
        if not fpid:
            # QO'SHILDI 2026-09-20 — MRP ORQALI ishlab chiqarilgan mahsulot.
            #
            # Muammo: MRP tayyor mahsulotni buyurtma detaliga
            # `order_item.finished_product_id` orqali BOG'LAMAYDI (mahsulot
            # buyurtmadan keyin ishlab chiqariladi), shuning uchun quyidagi
            # tsikl uni ko'rmasdi va butun ishlab chiqarish xarajati
            # buyurtma foydasidan tushib qolardi — jonli sinovda 100 m²
            # travertin 8 144 736.86 so'm xarajat bilan 0 tan narx va
            # 100% marja ko'rsatdi.
            #
            # Manba sifatida ISHLAB CHIQARISH BUYURTMASI olinadi
            # (`production_orders.total_cost`), tayyor mahsulot emas.
            # Sabab: tayyor mahsulotning `cost_price` va `reserved_quantity`
            # qiymatlari mijozga topshirilgan sari KAMAYADI, ishlab
            # chiqarishga ketgan xarajat esa O'ZGARMAYDI. Buyurtmaning tan
            # narxi ham o'zgarmasligi kerak.
            #
            # Faqat YAKUNLANGAN ishlab chiqarish olinadi — bekor qilingani
            # yoki hali tugallanmagani xarajat hisoblanmaydi.
            try:
                from production_models import ProductionOrder as _PO_cost
                _ord_cid0 = getattr(order, 'company_id', None)
                _x_po = _hk_ol(db, "po", item.id)
                if _x_po is not _HK_YOQ:
                    # kech89 (52-band): keshdan (tugagan, baza tartibida) — korxona sharti asl kabi
                    _po_royxat = [_p for _p in _x_po if _ord_cid0 is None or _p.company_id == _ord_cid0]
                else:
                    _pq = db.query(_PO_cost).filter(
                        _PO_cost.source_order_item_id == item.id,
                        _PO_cost.status == "completed",
                    )
                    if _ord_cid0 is not None:
                        _pq = _pq.filter(_PO_cost.company_id == _ord_cid0)
                    _po_royxat = _pq.all()
                # kech101 (138-band): bo'shagan dona tannarxi buyurtmaga KIRMAYDI — `_mrp_detal_tannarxi` (izohi o'sha yerda).
                _mrp_t117 = _mrp_detal_tannarxi(db, order, item, _po_royxat)
                tayyor_mahsulot_xarajat += _mrp_t117
                _tm_qismlari.append({"tur": "tayyor", "summa": _mrp_t117, "detal_id": item.id})
            except Exception:
                pass
            continue
        # M4 (2026-09-18) — TENANT: mahsulot buyurtmaning O'Z korxonasidan
        # bo'lishi shart. Chaqiruvchi allaqachon tenant-safe bo'lsa ham,
        # funksiyaning o'zi endi mustaqil himoyalangan.
        _ord_cid = getattr(order, 'company_id', None)
        _x_tm = _hk_ol(db, "tm", (fpid, _ord_cid))
        if _x_tm is _HK_YOQ:
            _fpq = db.query(_FP_cost).filter(_FP_cost.id == fpid)
            if _ord_cid is not None:
                _fpq = _fpq.filter(_FP_cost.company_id == _ord_cid)
            fp_c = _fpq.first()
            _hk_qoy(db, "tm", (fpid, _ord_cid), fp_c)
        else:
            fp_c = _x_tm
        if not fp_c:
            continue
        base_qty = float(fp_c.produced_quantity if fp_c.produced_quantity is not None else (fp_c.quantity or 0))
        # kech59 (47-band, K59-1): `cost_price` buyurtmaga olingan / sotilgan sari KAMAYADI,
        # `produced_quantity` esa o'zgarmaydi — nisbat siljirdi (O'LCHANGAN: 10 m x 7 600 = 76 000
        # o'rniga 68 400, boshqa buyurtma olgach 53 200; TM butunlay olinsa — 0). Muzlagan birlik
        # tannarx — olish / qaytarish / sotuv bilan BITTA manba (`crud._fp_stable_unit_cost`);
        # bo'lmasa — eski formula.
        import crud as _crud_fp59
        _x_mz = _hk_ol(db, "tm_birlik", fp_c.id)
        if _x_mz is _HK_YOQ:
            _muz59 = _crud_fp59._fp_stable_unit_cost(db, fp_c)
            _hk_qoy(db, "tm_birlik", fp_c.id, _muz59)
        else:
            _muz59 = _x_mz
        # kech103 (56-band, O'LCHANGAN `work/probe56tm.py`, SQLite = PG): detal OLINGAN paytdagi birlik
        # (`order_items.fp_unit_cost`) — TM ga keyin boshqa narxda partiya ("+") yoki qaytgan mahsulot qo'shilsa
        # o'rtacha o'zgaradi, avval olingan detal tannarxi (va o'tgan oy hisoboti) O'ZGARMAYDI (ilgari 76 000 →
        # 89 818). Yozilmagan (eski / tannarxsiz TM) — avvalgi qoida.
        _c56 = _crud_fp59._tm_detal_birligi(item)
        if _c56 is not None:
            unit_cost = _c56
        elif _muz59 > 0:
            unit_cost = _muz59
        else:
            if base_qty <= 0 or not fp_c.cost_price:
                continue
            unit_cost = float(fp_c.cost_price) / base_qty
        used_qty = float(item.length if (item.category or '').lower() == 'profil' else item.quantity or 0)
        tayyor_mahsulot_xarajat += unit_cost * used_qty
        _tm_qismlari.append({"tur": "tayyor", "summa": unit_cost * used_qty, "detal_id": item.id})
    if tayyor_mahsulot_xarajat > 0:
        breakdown.append({
            "nomi": f"Tayyor mahsulotdan olingan detallar (tan narxi)",
            "summa": tayyor_mahsulot_xarajat
        })
        tan_narxi_jami += tayyor_mahsulot_xarajat
        _tannarx_qismlari.extend(_tm_qismlari)


    # ── 1C. LOY SOTISH XARAJATI ──────────────────────────────
    # Har bir "Loy sotish" detali uchun — o'sha detalning O'ZIGA tegishli
    # retsept bo'yicha, sotilgan necha kg uchun tan narx hisoblanadi.
    for item in order.items:
        if (item.category or '').lower() != 'loy_sotish' or not item.recipe_id:
            continue
        qty_kg = float(item.quantity or 0)
        if qty_kg <= 0:
            continue
        # kech99 (112-band): retsept FAQAT buyurtma korxonasidan (qoplama retsepti kabi — "retsept_k").
        _lcid = company_id if company_id is not None else getattr(order, 'company_id', None)
        _x_r = _hk_ol(db, "retsept_k", (item.recipe_id, _lcid))
        if _x_r is _HK_YOQ:
            _lrq = db.query(Recipe).filter(Recipe.id == item.recipe_id)
            if _lcid is not None:
                _lrq = _lrq.filter(Recipe.company_id == _lcid)
            recipe = _lrq.first()
            _hk_qoy(db, "retsept_k", (item.recipe_id, _lcid), recipe)
        else:
            recipe = _x_r
        if not recipe:
            continue
        batch = float(recipe.batch_size_kg or 100)
        narx_per_kg = 0.0
        for ing in recipe.ingredients:
            mat_kg = float(ing.quantity_kg or 0)
            _ing_inv = _retsept_materiali(ing, recipe)   # kech99 (112-band)
            _ing_narx = _narx(_ing_inv)   # kech48 (K47-1)
            if mat_kg <= 0 or not _ing_inv or not _ing_narx:
                continue
            narx_per_kg += (mat_kg / batch) * _ing_narx
        loy_sotish_xarajat = qty_kg * narx_per_kg
        if loy_sotish_xarajat > 0:
            breakdown.append({
                "nomi": f"{item.name} — Loy sotish ({son_korinish(qty_kg, 1)} kg × {son_korinish(narx_per_kg, 0)} so'm/kg)",   # kech119 (G2-15)
                "summa": loy_sotish_xarajat
            })
            tan_narxi_jami += loy_sotish_xarajat
            _tannarx_qismlari.append({"tur": "loy_sotish", "summa": loy_sotish_xarajat, "detal_id": item.id})

    # ── 2. QOPLAMA XOMASHYOSI XARAJATI ──────────────────────
    # MUHIM: loy_kg — hech qanday formula/taxmin bilan hisoblanmaydi,
    # faqat buyurtma "Tayyor" qilinganda hodim kiritgan HAQIQIY miqdor
    # ishlatiladi (order.notes'dagi loy_kg= belgisi, complete_order
    # tomonidan yoziladi). Agar buyurtma hali yakunlanmagan bo'lsa —
    # bu xarajat hali "0" ko'rinadi, bu — to'g'ri (hali ishlatilmagan).
    # MUHIM: loy_kg — endi ALOHIDA, ISHONCHLI ustundan (order.actual_loy_kg)
    # o'qiladi — matn ichidan qidirish (notes) endi FAQAT eski, shu tuzatishdan
    # OLDIN yakunlangan buyurtmalar uchun zaxira (fallback) sifatida qoladi.
    loy_kg = float(order.actual_loy_kg) if order.actual_loy_kg is not None else 0.0
    if loy_kg <= 0 and order.notes:
        try:
            import re as _re_loykg
            m = _re_loykg.search(r'loy_kg=([\d.]+)', order.notes)
            if m:
                loy_kg = float(m.group(1))
        except Exception as e:
            try:
                import crud as _crud_log
                _crud_log.log_error(db, str(e), endpoint="calculate_order_profit:loy_kg_parse")
            except Exception:
                pass

    if loy_kg > 0:

        # Retsept bo'yicha 1 kg loy narxi
        # kech58 (K58-1 / K58-2): YAGONA manba. Yangi buyurtma — `qoplama_retsept_id` (retsept
        # tanlanmagan bo'lsa ham — loy yechilgan retsept); eski (NULL) — avvalgi qoida AYNAN
        # (birinchi `recipe_id` li detal, zaxirasiz) — foydalanuvchi qarori "faqat yangi".
        recipe = None
        _qcid = company_id if company_id is not None else getattr(order, 'company_id', None)
        for _qrid in buyurtma_qoplama_retsept_nomzodlari(order):
            _x_q = _hk_ol(db, "retsept_k", (_qrid, _qcid))
            if _x_q is _HK_YOQ:
                _rq = db.query(Recipe).filter(Recipe.id == _qrid)
                if _qcid is not None:
                    _rq = _rq.filter(Recipe.company_id == _qcid)
                recipe = _rq.first()
                _hk_qoy(db, "retsept_k", (_qrid, _qcid), recipe)
            else:
                recipe = _x_q
            break

        if recipe and loy_kg > 0:
            batch = float(recipe.batch_size_kg or 100)
            narx_per_kg = 0.0
            for ing in recipe.ingredients:
                mat_kg = float(ing.quantity_kg or 0)
                _ing_inv = _retsept_materiali(ing, recipe)   # kech99 (112-band)
                _ing_narx = _narx(_ing_inv)   # kech48 (K47-1)
                if mat_kg <= 0 or not _ing_inv or not _ing_narx:
                    continue
                narx_per_kg += (mat_kg / batch) * _ing_narx

            # kech107 (36-band, O'LCHANGAN `work/probe107c.py`): tayyor loy ZAXIRASIDAN olingan qism — olingan paytdagi
            # retsept tannarxida (ilgari butun loy ingredientlar narxida — to'liq zaxiradan qoplanganda JORIY narxda:
            # narxlar x3 → tan narx 760 000 → 1 280 000). Qolgan qism — avvalgidek. Ishlatilgan loydan ko'p emas.
            _zx_kg, _zx_narx = _buyurtma_zaxira_loyi(db, order, recipe, _sarf_hisob)
            _zx = min(_zx_kg, loy_kg) if _zx_narx is not None else 0.0
            qoplama_xarajat = _zx * (_zx_narx or 0.0) + (loy_kg - _zx) * narx_per_kg
            if qoplama_xarajat > 0:
                if _zx > 1e-9:
                    _qn = (f"Qoplama ({son_korinish(loy_kg, 1)} kg loy: {son_korinish(_zx, 1)} kg tayyor loy zaxirasidan × {son_korinish(_zx_narx, 0)}"
                           + (f" + {son_korinish(loy_kg - _zx, 1)} kg × {son_korinish(narx_per_kg, 0)}" if loy_kg - _zx > 1e-9 else "")
                           + " so'm/kg)")
                else:
                    _qn = f"Qoplama ({son_korinish(loy_kg, 1)} kg loy × {son_korinish(narx_per_kg, 0)} so'm/kg)"   # kech119 (G2-15)
                breakdown.append({
                    "nomi": _qn,
                    "summa": qoplama_xarajat
                })
                tan_narxi_jami += qoplama_xarajat
                _tannarx_qismlari.append({"tur": "qoplama", "summa": qoplama_xarajat, "detal_id": None})

    # ── 2b. QAYTARISHLAR (144-band, kech102) ─────────────────
    # Omborga qaytgan mahsulot buyurtmadan CHIQDI — uning tannarxi (`stock_cost`; qayta sotilganda TM sotuvi tannarxida
    # hisoblanadi) shu yerda ayriladi. "Pul qaytdi" joriy kelishilgan summada allaqachon bor; `holat_vaqti` berilsa —
    # undan KEYINGI pul qaytarish qaytarib qo'shiladi, keyingi omborga qaytish esa ayrilmaydi (ular o'z davrida).
    _omborga_qaytgan = 0.0
    _qaytgan_qismlari = []      # kech117 (A2): qaysi detal qaytgani bo'yicha
    for _tur144, _vaqt144, _summa144, _r144 in _qaytarish_hodisalari(db, order):
        if _tur144 == "ombor":
            if holat_vaqti is None or _vaqt144 < holat_vaqti:
                _omborga_qaytgan += _summa144
                _qaytgan_qismlari.append({"tur": "qaytgan", "summa": -_summa144,
                                          "detal_id": getattr(_r144, "order_item_id", None)})
        elif holat_vaqti is not None and _vaqt144 >= holat_vaqti:
            sotuv_narxi += _summa144
    if _omborga_qaytgan > 0:
        breakdown.append({
            "nomi": "↩️ Omborga qaytgan mahsulot (tannarxdan ayrildi)",
            "summa": -_omborga_qaytgan
        })
        tan_narxi_jami -= _omborga_qaytgan
        _tannarx_qismlari.extend(_qaytgan_qismlari)

    # ── 3. USTA HAQI (cashback% — foydadan) ─────────────────
    usta_haqi = 0.0
    if order.master and order.master.cashback_percent > 0:
        # Avval foydani hisoblaymiz (tan narxisiz)
        foyda_before_usta = sotuv_narxi - tan_narxi_jami
        usta_haqi = max(0, foyda_before_usta * order.master.cashback_percent / 100)
        breakdown.append({
            "nomi": f"Usta haqi ({order.master.name}, {son_korinish(order.master.cashback_percent, 1)}% foydadan)",   # kech119 (G2-15): «10%», «7,5%»
            "summa": usta_haqi
        })
        tan_narxi_jami += usta_haqi
        _tannarx_qismlari.append({"tur": "usta", "summa": usta_haqi, "detal_id": None})

    # ── 4. NATIJA ────────────────────────────────────────────
    foyda = sotuv_narxi - tan_narxi_jami
    foyda_foiz = (foyda / sotuv_narxi * 100) if sotuv_narxi > 0 else 0

    return {
        "success": True,
        "order_number": order.order_number,
        "sotuv_narxi": sotuv_narxi,
        "tan_narxi": tan_narxi_jami,
        "foyda": foyda,
        "foyda_foiz": round(foyda_foiz, 1),
        "breakdown": breakdown,
        "volume_m3": round(sum(d["vol"] for d in penoplast_breakdown_by_item.values()), 3),
        "tannarx_qismlari": _tannarx_qismlari,     # kech117 (A2): yig'indisi = tan_narxi
    }


# ============================================================
# OYLIK HISOBOT
# ============================================================

@_hisobot_keshi_bilan
def get_daily_finance_summary(db: Session, target_date, company_id: int = None) -> Dict:
    """Bitta kun uchun to'liq moliyaviy ko'rinish:
    - Savdo (shu kun 'Tayyor' bo'lgan buyurtmalar): sotuv, tan narx, foyda
    - Xarajat: xomashyo xaridi (nimaga qancha) + boshqa xarajatlar (nimaga qancha)
    """
    from models import InventoryPurchase, ExpenseTransaction, FinishedProductSale

    # kech105 (9 + 50-band, QAROR "Toshkent vaqti bo'yicha"): kun — TOSHKENT kalendar kuni (ilgari UTC yarim tunidan —
    # Toshkent 00:00–05:00 dagi «Tayyor» / sotuv / xarajat oldingi kunda chiqardi).
    start, end = _tashkent_kun_oraligi(target_date)

    # ── 1) SAVDO — shu kun yakunlangan buyurtmalar ──
    # MUHIM: o'chirilgan buyurtmalar ham hisobga olinadi — moliyaviy
    # tarix (shu kunning haqiqiy savdosi) o'zgarmasligi kerak.
    # M6 (2026-09-18) — TENANT: kunlik moliyaviy ko'rinishning HAR BIR
    # qismi joriy korxona bo'yicha.
    from models import Inventory as _Inv_day, Order as _Ord_day
    _otq = db.query(Order).filter(
        Order.completed_at >= start,
        Order.completed_at < end,
        # kech76 (97-band, QAROR B — 91-band): hisobotga FAQAT hodim "Tayyor" bosgan (READY) buyurtma
        # kiradi — oylik hisobot / usta KPI bilan bir xil. Ilgari DELIVERED ham sanalardi: to'liq
        # yetkazilgan, lekin "Tayyor" bosilmagan buyurtma shu ro'yxatda bor, oylik hisobotda yo'q edi.
        Order.status == OrderStatus.READY
    )
    if company_id is not None:
        _otq = _otq.filter(Order.company_id == company_id)
    orders_today = _otq.all()
    _hk_tayyorla(db, orders_today)       # kech89 (52-band): N+1 o'rniga bir necha IN so'rovi

    total_sales = 0.0
    total_cost = 0.0
    for o in orders_today:
        p = yakun_foydasi(db, o, company_id=company_id)        # kech102 (144-band): yakunlangan paytdagi
        if p.get("success"):
            total_sales += p["sotuv_narxi"]
            total_cost += p["tan_narxi"]
    # kech102 (144-band, QAROR "Qaytarish oyida"): shu kuni bo'lgan qaytarishlar (yakunlangan buyurtmalardan keyin)
    _qaytarishlar_kun = davr_qaytarishlari(db, start, end, company_id=company_id)
    for _h144 in _qaytarishlar_kun:
        total_sales += _h144["daromad"]
        total_cost += _h144["tannarx"]

    # ── 1b) SAVDO — shu kun to'g'ridan-to'g'ri sotilgan tayyor mahsulotlar ──
    # (Tayyor mahsulotlar bo'limidan, buyurtmasiz sotilganlar — avval bu
    # "Bugungi holat"da hisobga olinmasdi, garchi oylik hisobotda bor edi.)
    _fsq_day = db.query(FinishedProductSale).filter(
        FinishedProductSale.sold_at >= start,
        FinishedProductSale.sold_at < end
    )
    if company_id is not None:
        _fsq_day = _fsq_day.filter(FinishedProductSale.company_id == company_id)
    fp_sales_today = _fsq_day.all()
    for s in fp_sales_today:
        total_sales += float(s.total_amount or 0)
        total_cost += float(s.cost_amount or 0)

    total_profit = total_sales - total_cost

    # ── 2) XARAJAT — xomashyo xaridi (nimaga qancha) ──
    # MUHIM: "boshlang'ich ombor" kirimlar bu yerga kirmaydi (yuqoridagi
    # get_purchase_stats_for_period bilan bir xil sabab).
    _ptq = db.query(InventoryPurchase).filter(
        InventoryPurchase.purchased_at >= start,
        InventoryPurchase.purchased_at < end,
        InventoryPurchase.is_opening_stock.isnot(True)
    )
    if company_id is not None:      # ota (material) orqali
        _ptq = _ptq.join(_Inv_day, _Inv_day.id == InventoryPurchase.inventory_id).filter(
            _Inv_day.company_id == company_id)
    purchases_today = _ptq.all()
    material_total = sum(float(p.total_amount or 0) for p in purchases_today)
    material_breakdown = {}
    for p in purchases_today:
        material_breakdown[p.item_name] = material_breakdown.get(p.item_name, 0.0) + float(p.total_amount or 0)

    # ── 3) XARAJAT — boshqa (arenda, elektr va h.k.) ──
    _oeq = db.query(ExpenseTransaction).filter(
        ExpenseTransaction.date >= start,
        ExpenseTransaction.date < end
    )
    if company_id is not None:
        _oeq = _oeq.filter(ExpenseTransaction.company_id == company_id)
    other_today = _oeq.all()
    other_total = sum(float(e.amount or 0) for e in other_today)
    other_breakdown = {}
    for e in other_today:
        other_breakdown[e.category] = other_breakdown.get(e.category, 0.0) + float(e.amount or 0)

    # ── 4) XARAJAT — transport (kompaniya o'z zimmasiga olgan yetkazish xarajati) ──
    from models import Delivery
    _dtq = db.query(Delivery).filter(
        Delivery.delivered_at >= start,
        Delivery.delivered_at < end,
        Delivery.transport_cost > 0
    )
    if company_id is not None:      # ota (buyurtma) orqali
        _dtq = _dtq.join(_Ord_day, _Ord_day.id == Delivery.order_id).filter(
            _Ord_day.company_id == company_id)
    deliveries_today = _dtq.all()
    transport_total = sum(d.company_transport_cost for d in deliveries_today)
    # kech87 (104-band, QAROR): kirish transporti (xarid oynasidagi "o'z hisobimdan" va alohida "Kirish
    # transporti") ham shu kunning transport xarajati — ilgari kunlikda YO'Q edi (O'LCHANGAN, probe104 K1 / K2).
    from models import TransportExpense as _TE_day
    from sqlalchemy import func as _func_td
    _teq_day = db.query(_func_td.sum(_TE_day.amount)).filter(
        _TE_day.expense_date >= start,
        _TE_day.expense_date < end
    )
    if company_id is not None:      # M6
        _teq_day = _teq_day.filter(_TE_day.company_id == company_id)
    transport_total += float(_teq_day.scalar() or 0)

    total_expense = material_total + other_total + transport_total

    return {
        "date": target_date.isoformat(),
        "sales": {
            "orders_count": len(orders_today),
            "total": round(total_sales),
            "cost": round(total_cost),
            "profit": round(total_profit),
            # kech102 (144-band): shu kungi qaytarishlar (yuqoridagi summalar ICHIDA)
            "qaytarish_soni": len(_qaytarishlar_kun),
            "qaytarish_daromad": round(sum(h["daromad"] for h in _qaytarishlar_kun)),
            "qaytarish_tannarx": round(sum(h["tannarx"] for h in _qaytarishlar_kun)),
        },
        "expenses": {
            "total": round(total_expense),
            "material": {
                "total": round(material_total),
                "breakdown": [{"nomi": k, "summa": round(v)} for k, v in sorted(material_breakdown.items(), key=lambda x: -x[1])]
            },
            "transport": {
                "total": round(transport_total)
            },
            "other": {
                "total": round(other_total),
                "breakdown": [{"nomi": k, "summa": round(v)} for k, v in sorted(other_breakdown.items(), key=lambda x: -x[1])]
            }
        }
    }


@_hisobot_keshi_bilan
def get_finance_history(db: Session, months_count: int = 12, company_id: int = None) -> list:
    """Oxirgi N oy uchun moliyaviy tarix — grafik va 'Xarajatlar tarixi' jadvali uchun.
    MUHIM: hech qanday yangi hisob-kitob yo'q — faqat mavjud get_monthly_report()
    funksiyasini har oy uchun alohida chaqiradi va natijalarni ro'yxatga yig'adi."""

    today = _tashkent_date()      # kech105 (9 + 50-band): joriy oy — Toshkent kalendari
    y, m = today.year, today.month
    history = []
    for i in range(months_count):
        yy, mm = y, m - i
        while mm <= 0:
            mm += 12
            yy -= 1
        try:
            rep = get_monthly_report(db, yy, mm, company_id=company_id)
            rep["year"] = yy
            rep["month"] = mm
            history.append(rep)
        except Exception:
            continue
    return list(reversed(history))  # eskisidan yangisiga


# ============================================================
# kech56 (13-band, 7-qadam) — BRAK TAHLILI
# ============================================================
# Foydalanuvchi qarorlari (kech56, tugma bilan): me'yor "5 %" (`crud.BRAK_MEYORI_FOIZ`),
# sabab ro'yxati (`crud.BRAK_SABABLARI`), javobgar hodim — ixtiyoriy.
# Texnik qaror (Claude): brak ULUSHI = oylik brak xarajati ÷ ishlab chiqarish tan
# narxi × 100 — ikkala son `get_monthly_report` dan (Moliya bilan BIR manba, narxlar
# muzlatilgan). Taqsimot (bosqich / sabab / javobgar / detal) — shu oyning brak
# YOZUVLARI qiymati bo'yicha (buyurtma detali braki `refund_amount`, tayyor mahsulot
# yo'qotishi `cost_amount`). Faqat O'QIYDI — hech narsa yozmaydi.

def _brak_oylari(year: int, month: int, oylar: int) -> list:
    """(yil, oy) juftlari — eskisidan yangisiga, oxirgisi (year, month)."""
    natija = []
    y, m = int(year), int(month)
    for _ in range(max(1, int(oylar))):
        natija.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(natija))


def _brak_foizi(brak: float, ishlab: float):
    """Brak ulushi foizda (2 xona). Ishlab chiqarish tan narxi 0 bo'lsa — None:
    bo'lib bo'lmaydi, taxmin qilinmaydi (UI "hisoblab bo'lmaydi" deydi)."""
    if ishlab is None or float(ishlab) <= 0:
        return None
    return round(float(brak or 0) / float(ishlab) * 100.0, 2)


@_hisobot_keshi_bilan
def get_brak_tahlil(db: Session, year: int, month: int, company_id: int = None,
                    oylar: int = 6) -> dict:
    """Oylik brak tahlili: ulush va me'yor (ogohlantirish), bosqich / sabab /
    javobgar hodim / detal bo'yicha taqsimot, tayyor mahsulot yo'qotishlari
    ro'yxati va oxirgi `oylar` oy bo'yicha ulush."""
    import crud as _cr
    from models import ReturnItem, ReturnReason, FinishedProductLoss, Employee

    meyor = float(_cr.BRAK_MEYORI_FOIZ)

    # 1) Ulush — Moliya bilan BIR manba.
    trend = []
    for (yy, mm) in _brak_oylari(year, month, oylar):
        rep = get_monthly_report(db, yy, mm, company_id=company_id)
        brak = float(rep.get("brak_xarajat") or 0)
        ishlab = float(rep.get("ishlab_chiqarish_xarajat") or 0)
        foiz = _brak_foizi(brak, ishlab)
        trend.append({
            "yil": yy, "oy": mm,
            "brak_xarajat": round(brak),
            "ishlab_chiqarish_xarajat": round(ishlab),
            "brak_foizi": foiz,
            "meyordan_oshdi": bool(foiz is not None and foiz > meyor),
        })
    joriy = trend[-1]

    # 2) Shu oyning yozuvlari (korxona filtri bilan).
    _rq = db.query(ReturnItem).filter(
        ReturnItem.reason == ReturnReason.DEFECT,
        _tashkent_oyida(ReturnItem.returned_at, year, month),
    )
    if company_id is not None:
        _rq = _rq.filter(ReturnItem.company_id == company_id)
    braklar = _rq.order_by(ReturnItem.id).all()

    _lq = db.query(FinishedProductLoss).filter(
        _tashkent_oyida(FinishedProductLoss.lost_at, year, month),
    )
    if company_id is not None:
        _lq = _lq.filter(FinishedProductLoss.company_id == company_id)
    yoqotishlar = _lq.order_by(FinishedProductLoss.id).all()

    _hodim_idlari = {r.brak_javobgar_id for r in braklar if r.brak_javobgar_id} | \
                    {l.brak_javobgar_id for l in yoqotishlar if l.brak_javobgar_id}
    ismlar = {}
    if _hodim_idlari:
        _eq = db.query(Employee.id, Employee.name).filter(Employee.id.in_(sorted(_hodim_idlari)))
        if company_id is not None:
            _eq = _eq.filter(Employee.company_id == company_id)
        ismlar = {i: n for i, n in _eq.all()}

    def _javobgar_ismi(hid):
        if not hid:
            return None
        return ismlar.get(hid) or "O'chirilgan hodim"

    # kech107 (49-band, egasi qarori "Bitta raqam"; O'LCHANGAN `work/probe107b.py`): taqsimot — shu oyning BRAK
    # yozuvlari, qiymati HAQIQIY xomashyo narxi: buyurtma braki — unga bog'langan brak harakatlari
    # (`crud.brak_yozuv_qiymatlari`, Moliya "Brak" qatori bilan bir qoida; ilgari yozuvdagi saqlangan, eski yozuvlarda
    # taxminiy summa), ishlab chiqarish braki — `cost_amount` (uning harakatlari qiymati). Omborda tayyor turgan
    # mahsulot yo'qotishi — brak EMAS: taqsimot va ulushga KIRMAYDI (ilgari kirardi — tahlil jami Moliyadan katta
    # chiqardi), ro'yxatda (`yoqotishlar`) qoladi, jami — `tayyor_yoqotish_qiymati`.
    _yozuv_qiymati = _cr.brak_yozuv_qiymatlari(db, [r.id for r in braklar], company_id=company_id)
    yozuvlar = []
    for r in braklar:
        yozuvlar.append({
            "nomi": r.item_name or "", "birlik": r.unit or "",
            "miqdor": float(r.quantity or 0), "qiymat": float(_yozuv_qiymati.get(r.id, 0.0)),
            "bosqich": r.brak_bosqich, "sabab": r.brak_sabab, "javobgar_id": r.brak_javobgar_id,
        })
    yoqotish_royxati = []
    tayyor_yoqotish_qiymati = 0.0
    for l in yoqotishlar:
        ish_braki = (l.reason or "").startswith(_cr._ISH_BRAK_BELGI)
        if ish_braki:
            yozuvlar.append({
                "nomi": l.product_name or "", "birlik": l.unit or "",
                "miqdor": float(l.quantity or 0), "qiymat": float(l.cost_amount or 0),
                "bosqich": l.brak_bosqich, "sabab": l.brak_sabab, "javobgar_id": l.brak_javobgar_id,
            })
        else:
            tayyor_yoqotish_qiymati += float(l.cost_amount or 0)
        yoqotish_royxati.append({
            "id": l.id,
            "sana": l.lost_at.isoformat() if l.lost_at else None,
            "nomi": l.product_name or "",
            "miqdor": float(l.quantity or 0),
            "birlik": l.unit or "",
            "qiymat": round(float(l.cost_amount or 0), 2),
            "turi": "Ishlab chiqarish braki" if ish_braki else "Yo'qotish (tayyor turgan)",
            "bosqich": _cr.BRAK_BOSQICHLARI.get(l.brak_bosqich, l.brak_bosqich) if l.brak_bosqich else None,
            "sabab": _cr.BRAK_SABABLARI.get(l.brak_sabab, l.brak_sabab) if l.brak_sabab else None,
            "javobgar": _javobgar_ismi(l.brak_javobgar_id),
            "izoh": l.reason or "",
            "yozgan": l.created_by or "",
        })

    jami_qiymat = sum(y["qiymat"] for y in yozuvlar)
    # kech107 (49-band): Moliya "Brak" qatori (yaxlitlanmagan — o'sha funksiya, o'sha Toshkent oyi) − yozuvlar jami =
    # yozuvga bog'lanmagan (bog'lamdan oldingi eski) brak harakatlari. Yangi ma'lumotda 0.
    _b_boshi, _b_oxiri = _tashkent_oy_oraligi(year, month)
    _moliya_brak = float(_cr.get_brak_material_summary(db, start_date=_b_boshi, end_date=_b_oxiri,
                                                       company_id=company_id).get("total_value") or 0)
    boglanmagan_qiymat = round(_moliya_brak - jami_qiymat, 2)
    if abs(boglanmagan_qiymat) < 0.01:
        boglanmagan_qiymat = 0.0

    def _ulush(q):
        return round(q / jami_qiymat * 100.0, 1) if jami_qiymat > 0 else 0.0

    def _taqsimot(maydon, yorliq_fn):
        """Kod bo'yicha guruh — qiymat kamayishi tartibida, tanlanmaganlar OXIRIDA."""
        hisob = {}
        for y in yozuvlar:
            h = hisob.setdefault(y[maydon], {"soni": 0, "qiymat": 0.0})
            h["soni"] += 1
            h["qiymat"] += y["qiymat"]
        bor = sorted((k for k in hisob if k is not None),
                     key=lambda k: (-hisob[k]["qiymat"], str(k)))
        natija = []
        for k in bor + ([None] if None in hisob else []):
            natija.append({
                "kod": k,
                "nomi": yorliq_fn(k) if k is not None else "Belgilanmagan",
                "soni": hisob[k]["soni"],
                "qiymat": round(hisob[k]["qiymat"], 2),
                "ulush": _ulush(hisob[k]["qiymat"]),
            })
        return natija

    detal = {}
    for y in yozuvlar:
        d = detal.setdefault((y["nomi"], y["birlik"]), {"soni": 0, "miqdor": 0.0, "qiymat": 0.0})
        d["soni"] += 1
        d["miqdor"] += y["miqdor"]
        d["qiymat"] += y["qiymat"]
    top = sorted(detal.items(), key=lambda kv: (-kv[1]["qiymat"], kv[0][0], kv[0][1]))[:5]

    foiz = joriy["brak_foizi"]
    oshdi = joriy["meyordan_oshdi"]
    return {
        "yil": int(year), "oy": int(month),
        "meyor_foiz": meyor,
        "brak_xarajat": joriy["brak_xarajat"],
        "ishlab_chiqarish_xarajat": joriy["ishlab_chiqarish_xarajat"],
        "brak_foizi": foiz,
        "meyordan_oshdi": oshdi,
        # kech118 (U-05): kasr — vergul («5,01 %»); ekranga shu matn chiqadi
        "ogohlantirish": (f"Brak me'yordan oshdi: {_son_uz(foiz)} % (me'yor {_son_uz(meyor)} %)" if oshdi else None),
        "yozuvlar_soni": len(yozuvlar),
        "yozuvlar_qiymati": round(jami_qiymat, 2),
        "boglanmagan_qiymat": boglanmagan_qiymat,
        "tayyor_yoqotish_qiymati": round(tayyor_yoqotish_qiymati, 2),
        "bosqichlar": _taqsimot("bosqich", lambda k: _cr.BRAK_BOSQICHLARI.get(k, k)),
        "sabablar": _taqsimot("sabab", lambda k: _cr.BRAK_SABABLARI.get(k, k)),
        "javobgarlar": _taqsimot("javobgar_id", _javobgar_ismi),
        "top_detallar": [
            {"nomi": k[0], "birlik": k[1], "soni": v["soni"],
             "miqdor": round(v["miqdor"], 3), "qiymat": round(v["qiymat"], 2),
             "ulush": _ulush(v["qiymat"])}
            for k, v in top
        ],
        "yoqotishlar": yoqotish_royxati,
        "trend": trend,
    }


def _monthly_category_amount(db: Session, year: int, month: int, category: str, fallback: float,
                            company_id: int = None) -> float:
    """Berilgan oy/kategoriya uchun ExpenseTransaction yig'indisini qaytaradi.

    Agar shu oy/kategoriya uchun BIRON-BIR tranzaksiya bo'lsa — ularning yig'indisi qaytadi
    (bu — SaaS uchun yangi, tranzaksiya-asosidagi hisoblash).
    Agar tranzaksiya UMUMAN topilmasa (masalan, bu funksiya qo'shilishidan oldingi eski oy) —
    eski `fallback` qiymati (MonthlyExpense'dan) qaytadi. Shu tariqa hech qanday eski
    hisobot o'zgarmaydi, faqat yangi tranzaksiyalar mavjud bo'lgan oylar aniqroq hisoblanadi.
    """
    from models import ExpenseTransaction
    from sqlalchemy import func
    try:
        _eq = db.query(ExpenseTransaction.id).filter(
            _tashkent_oyida(ExpenseTransaction.date, year, month),
            ExpenseTransaction.category == category
        )
        if company_id is not None:      # M6
            _eq = _eq.filter(ExpenseTransaction.company_id == company_id)
        exists = _eq.first()
        if not exists:
            return float(fallback or 0)
        _sq = db.query(func.sum(ExpenseTransaction.amount)).filter(
            _tashkent_oyida(ExpenseTransaction.date, year, month),
            ExpenseTransaction.category == category
        )
        if company_id is not None:
            _sq = _sq.filter(ExpenseTransaction.company_id == company_id)
        total = _sq.scalar()
        return float(total or 0)
    except Exception:
        return float(fallback or 0)


@_hisobot_xotirasi_bilan      # kech120 (E, U-09): so'rovlar orasida — yozuv bo'lsa darhol eskiradi
@_hisobot_keshi_bilan
def get_monthly_report(db: Session, year: int, month: int, company_id: int = None) -> Dict:
    """
    Berilgan oy uchun to'liq moliyaviy hisobot:
    Daromad - Xarajatlar = Sof foyda
    """
    from models import Order, OrderStatus, MonthlyExpense, OrderItem
    from sqlalchemy import func

    def _inv_rep(inv_id):
        """M6 — TENANT: hisobot ichidagi material qidiruvlari joriy korxonadan."""
        # kech89 (52-band): hisobot keshi; kech99 (112-band): foyda / hajm bilan BITTA qoida va kesh
        # (`_korxona_materiali` — korxona sharti, "inv" / "inv_begona")
        return _korxona_materiali(db, inv_id, company_id)

    # ── 1. DAROMAD va SOF FOYDA (tayyor buyurtmalar) ────────
    # MUHIM: bu yerda Order.is_deleted ATAYLAB tekshirilmaydi — o'chirilgan
    # (lekin avval haqiqatan yakunlangan, daromad keltirgan) buyurtmalar ham,
    # moliyaviy hisobotda (tarixiy haqiqat sifatida) hisobga olinishi kerak.
    # "O'chirish" — faqat ro'yxatlardan (Buyurtmalar, KPI) yashirish uchun,
    # moliyaviy tarixni o'chirmasligi kerak.
    # M6 (2026-09-18) — TENANT: hisobotning BARCHA qismlari joriy korxona
    # bo'yicha (ilgari faqat tayyor mahsulot qismi filtrlangan edi).
    _roq = db.query(Order).filter(
        Order.status == OrderStatus.READY,
        _tashkent_oyida(Order.completed_at, year, month)
    )
    if company_id is not None:
        _roq = _roq.filter(Order.company_id == company_id)
    ready_orders = _roq.all()
    _hk_tayyorla(db, ready_orders)       # kech89 (52-band): N+1 o'rniga bir necha IN so'rovi

    # MUHIM: "Kelishilgan summa" (agreed_amount) bo'lsa — shuni, aks holda
    # "Umumiy jami"ni olamiz. Bu — Buyurtmalar ro'yxati va har bir
    # buyurtmaning foyda hisobi (calculate_order_profit) bilan BIR XIL
    # manba — aks holda "Jami daromad" bu ikkisidan farq qilib qolar edi.
    # kech102 (144-band, QAROR "Qaytarish oyida"): buyurtma YAKUNLANGAN paytdagi daromad — keyingi "Pul qaytdi"
    # qaytarish bo'lgan oyda (pastda, "1b"), o'tgan oy hisoboti o'zgarmaydi.
    daromad = sum(yakun_daromadi(db, o) for o in ready_orders)
    buyurtmalar_soni = len(ready_orders)

    # ── TAYYOR MAHSULOT TO'G'RIDAN-TO'G'RI SOTUVI ──
    # Bu — buyurtmasiz sotuv, alohida daromad manbai. MUHIM: bu summa
    # Usta KPI, Ehson, hodim foiz-asosidagi to'lovlariga TA'SIR QILMAYDI
    # (ular faqat haqiqiy ISHLAB CHIQARISH buyurtmalariga tegishli) —
    # faqat umumiy "Jami daromad" va "Sof foyda"ga qo'shiladi.
    from models import FinishedProductSale as _FPS
    # 2026-09-18 — TENANT (M7 validatsiyasida B sessiyasidan topilgan
    # HAQIQIY sizish): bu so'rov korxona filtrisiz edi. B ning oylik
    # hisobotida A ning tayyor mahsulot sotuvi (812 000 so'm) daromad
    # sifatida ko'rinardi, holbuki B da birorta sotuv yo'q.
    _fpsq = db.query(_FPS).filter(
        _tashkent_oyida(_FPS.sold_at, year, month)
    )
    if company_id is not None:
        _fpsq = _fpsq.filter(_FPS.company_id == company_id)
    fp_sales = _fpsq.all()
    fp_sales_daromad = sum(float(s.total_amount or 0) for s in fp_sales)
    fp_sales_tannarx = sum(float(s.cost_amount or 0) for s in fp_sales)
    fp_sales_foyda = fp_sales_daromad - fp_sales_tannarx

    # Har buyurtma uchun foyda hisoblaymiz
    ishlab_chiqarish_xarajat = 0.0
    for order in ready_orders:
        try:
            profit_data = yakun_foydasi(db, order, company_id=company_id)    # kech102 (144-band)
            ishlab_chiqarish_xarajat += float(profit_data.get("tan_narxi", 0))
        except Exception as e:
            try:
                import crud as _crud_log
                _crud_log.log_error(db, str(e), endpoint=f"get_monthly_report:calculate_order_profit order#{order.id}")
            except Exception:
                pass

    # ── 1b. QAYTARISHLAR (144-band, kech102 — FOYDALANUVCHI QARORI "Qaytarish oyida") ──
    # Shu oyda bo'lgan (buyurtma yakunlangandan KEYINGI) qaytarishlar: mijozga qaytarilgan pul — daromaddan,
    # omborga qaytgan mahsulot tannarxi — ishlab chiqarish xarajatidan ayriladi (alohida qator — `qaytarish_*`).
    _q144_boshi, _q144_oxiri = _tashkent_oy_oraligi(year, month)
    _qaytarishlar = davr_qaytarishlari(db, _q144_boshi, _q144_oxiri, company_id=company_id)
    qaytarish_daromad = sum(h["daromad"] for h in _qaytarishlar)
    qaytarish_tannarx = sum(h["tannarx"] for h in _qaytarishlar)
    daromad += qaytarish_daromad
    ishlab_chiqarish_xarajat += qaytarish_tannarx

    sof_daromad = daromad - ishlab_chiqarish_xarajat

    # ── 2. QOPLAMACHI BONUS hisoblash ───────────────────────
    # Profil/karniz → uzunlik (metr) × miqdor × 1000 so'm
    # Panel/boshqa  → miqdor × 1000 so'm
    # Xuddi yuqoridagidek — o'chirilgan buyurtmalar ham hisobga olinadi
    # (moliyaviy tarix saqlanishi uchun, "O'chirilganlar" xodim bonusini
    # ham noto'g'ri kamaytirib yubormasligi kerak).
    _otmq = db.query(Order).filter(
        Order.status == OrderStatus.READY,
        _tashkent_oyida(Order.completed_at, year, month)
    )
    if company_id is not None:      # M6
        _otmq = _otmq.filter(Order.company_id == company_id)
    orders_this_month = _otmq.all()

    jami_metr = 0.0   # Profil uchun (metr)
    jami_panel_metr = 0.0  # Panel uchun (metr)
    jami_dona = 0.0   # Donali uchun (dona)

    for order in orders_this_month:
        for item in order.items:
            if (item.category or "").lower() == "gips":
                # MUHIM: Gips — bu yerga MUTLAQO kira olmaydi (is_coated
                # holatidan qat'iy nazar). Gips o'z, alohida bo'limida
                # (pastda) hisoblanadi.
                continue
            if item.finished_product_id:
                # MUHIM: bu detal "Tayyor mahsulotdan" tanlangan (ombordagi
                # mavjud zaxiradan olingan) — uning ishlab chiqarilishi
                # ALLAQACHON, o'sha mahsulot birinchi marta ishlab
                # chiqarilib "Sotuvga tayyor" bo'lganda hisoblangan edi.
                # Shu buyurtmada YANA hisoblasak — IKKI MARTA to'lagan
                # bo'lardik, shuning uchun BU YERDA o'tkazib yuboriladi.
                continue

            # MUHIM: Ichki qo'shimcha detallar (sub_details) — bularning
            # qoplama holati ASOSIY detalning is_coated'idan TO'LIQ
            # MUSTAQIL (xodim har bir ichki detalni alohida belgilaydi).
            # Shuning uchun bu tekshiruv "if not item.is_coated: continue"
            # dan OLDIN, alohida turadi — aks holda: (a) asosiy qoplamasiz
            # bo'lgan holatda uning qoplamali ichki detali umuman
            # hisoblanmay qolardi, (b) asosiy qoplamali bo'lgan holatda esa
            # ichki detal HAM qoplamali bo'lsa, o'sha ichki ishning o'zi
            # hech qachon qo'shilmas edi (qoplamachi kam to'lov olardi).
            # Aksincha — ichki detal qoplamasiz bo'lsa, asosiy qoplamali
            # bo'lishidan qat'iy nazar, HECH QACHON qo'shilmaydi (mijozdan
            # olinmagan pul uchun xodimga ortiqcha to'lanmasligi kerak).
            for sub in (item.sub_details or []):
                if not getattr(sub, 'is_coated', False):
                    continue
                sub_cat = (getattr(sub, 'category', None) or '').lower()
                if sub_cat == 'panel':
                    jami_panel_metr += float(getattr(sub, 'quantity', 0) or 0)
                else:  # 'profil' (standart)
                    _sub_len = float(getattr(sub, 'length', 0) or 0)
                    _sub_qty = float(getattr(sub, 'quantity', 1) or 1)
                    jami_metr += _sub_len * _sub_qty

            if not item.is_coated:
                continue

            category = (item.category or "").lower()
            if category in ["profil", "karniz"]:
                # Profil: uzunlik (m) × miqdor
                uzunlik_m = float(item.length or 0)
                jami_metr += uzunlik_m * float(item.quantity or 1)

            elif category == "blok":
                # Blok — "necha metr kerak" item.quantity'da saqlanadi
                # (Profilga o'xshab, lekin uzunlik emas, to'g'ridan-to'g'ri
                # miqdor maydonida)
                jami_metr += float(item.quantity or 0)

            elif category == "panel":
                # MUHIM: Panelda "Miqdor" maydonining o'zi — METR ma'nosini
                # bildiradi (masalan "100 metr panel"), "Uzunlik" maydoni esa
                # panel uchun ATAYLAB ishlatilmaydi (frontendda har doim 0
                # qilib qo'yiladi). Shuning uchun panel metri —
                # item.quantity'dan olinadi, item.length'dan EMAS.
                jami_panel_metr += float(item.quantity or 0)

            elif category == "dona":
                jami_dona += float(item.quantity or 1)

            # MUHIM: "loy_sotish", "gips" — bu yerga UMUMAN qo'shilmaydi.
            # Gips — butunlay alohida, pastdagi bo'limda hisoblanadi.

    # TAYYOR MAHSULOTLAR sahifasidan ISHLAB CHIQARILIB, "SOTUVGA TAYYOR"
    # deb belgilangan mahsulotlar (buyurtmasiz) — hodim shu ishni ham
    # qilgani uchun, bu ham hodim oyligiga qo'shiladi.
    # 11.2b (2026-09-20): avval bu yerda "G'isht" nomli mahsulot YAGONA
    # istisno sifatida chiqarib tashlanardi (BYPRODUCT deb). G'isht
    # butunlay olib tashlangani uchun istisno ham olib tashlandi — endi
    # ishlab chiqarilgan BARCHA mahsulot hodim oyligiga kiradi.
    from models import FinishedProduct, StockSource, ProductionStatus
    _dp_start, _dp_end = _tashkent_oy_oraligi(year, month)
    # 2026-09-18 — TENANT (o'sha validatsiyada topilgan ikkinchi so'rov):
    # ishlab chiqarilgan miqdorlar ham korxona filtrisiz o'qilardi.
    #
    # 22-band (2026-09-21, FOYDALANUVCHI QARORI "2") — O'LCHANGAN
    # (`work/probe22.py`). Ilgari bu so'rov mahsulot holatini UMUMAN
    # ko'rmasdi va oyni `created_at` (ishlab chiqarishga QO'YILGAN sana)
    # bo'yicha ajratardi. Natijada ikki xato bor edi:
    #   (a) hali JARAYONDAGI (IN_PROGRESS), ya'ni qoplanmagan mahsulot ham
    #       darhol qoplamachi bonusiga kirardi (10 metr → +10 000 so'm,
    #       "Tayyor" bosilganda esa bonus BOSHQA o'zgarmasdi — demak haq
    #       ish bitgani uchun emas, ish BOSHLANGANI uchun to'lanardi);
    #   (b) avgustda boshlanib sentyabrda tayyor bo'lgan mahsulot
    #       AVGUST oyiga tushardi (o'lchandi: avgust bonusi 7 000) —
    #       ya'ni yopilgan oyning hisoboti keyin o'zgarib ketardi.
    # Endi: FAQAT "Sotuvga tayyor" (READY) mahsulot hisoblanadi va u
    # TAYYOR BO'LGAN oyga tushadi (`finished_production_at`). Eski
    # yozuvlarda bu ustun bo'sh bo'lishi mumkin (u 2026-09 da qo'shilgan)
    # — o'shalar uchun `created_at` ga qaytiladi, shunda tarix buzilmaydi.
    #
    # Bu — buyurtmalar bilan ham SIMMETRIK: yuqoridagi tsikl buyurtma
    # detallarini faqat buyurtma "Tayyor" (READY) bo'lgan va shu oyda
    # yakunlangan (`completed_at`) holatda qo'shadi.
    _tayyor_sana = func.coalesce(FinishedProduct.finished_production_at,
                                 FinishedProduct.created_at)
    _dpq = db.query(FinishedProduct).filter(
        FinishedProduct.source == StockSource.PRODUCED,
        FinishedProduct.production_status == ProductionStatus.READY,
        _tayyor_sana >= _dp_start,
        _tayyor_sana < _dp_end
    )
    if company_id is not None:
        _dpq = _dpq.filter(FinishedProduct.company_id == company_id)
    direct_produced = _dpq.all()
    for fp in direct_produced:
        cat = (fp.category or "").lower()
        # MUHIM: `quantity` — SOTISH/BRAK orqali KAMAYADI (joriy qoldiq).
        # Hodim oyligi esa — mahsulot ASLIDA qancha ishlab chiqarilgani
        # bo'yicha hisoblanishi kerak, keyinchalik sotilgan-sotilmaganidan
        # QAT'IY NAZAR. Shuning uchun `produced_quantity` (muzlatilgan,
        # "Sotuvga tayyor" bo'lgan paytdagi son) ishlatiladi. Eski
        # yozuvlarda bu maydon bo'sh bo'lishi mumkin — fallback sifatida
        # joriy `quantity` ishlatiladi.
        qty = float(fp.produced_quantity if fp.produced_quantity is not None else (fp.quantity or 0))
        if cat == "gips":
            # 11.2b (5-qadam): gipsga bog'liq hodim to'lovining OXIRGISI
            # (qoliplik gul / gul_rate) ham olib tashlandi. Eski
            # ma'lumotda category='gips' mahsulot uchrashi mumkin —
            # u hodim oyligiga HECH QANDAY yo'l bilan kirmasligi SHART,
            # shuning uchun bu yerda ATAYLAB o'tkazib yuboriladi.
            # (Pastdagi qoplamachi bonusiga ham tushmaydi — gipsda
            # "qoplama" tushunchasi yo'q, u o'zi tayyor mahsulot.)
            continue
        # MUHIM: Gipsdan boshqa barchasi uchun — faqat HAQIQATAN qoplamali
        # (is_coated=True) bo'lsa, Qoplamachi bonusiga qo'shiladi. Qoplamasiz
        # ishlab chiqarilgan mahsulot — bu bonusga aloqasi yo'q.
        if not fp.is_coated:
            continue
        if cat in ["profil", "karniz"]:
            jami_metr += qty
        elif cat == "panel":
            jami_panel_metr += qty
        else:
            jami_dona += qty

    # MUHIM: Tayyor mahsulotlar bo'limida ("Ishlab chiqarish" tugmasi
    # orqali, mijoz buyurtmasiga bog'lanmasdan) tayyorlangan qoplamali
    # mahsulotlar — YUQORIDA, "direct_produced" tsiklida ALLAQACHON
    # hisoblangan (is_coated tekshiruvi bilan birga). Bu yerda AVVAL
    # yana bir marta hisoblovchi, DUBLIKAT tsikl bor edi — u xuddi shu
    # mahsulotlarni IKKI MARTA qo'shib yuborardi (masalan 200 dona o'rniga
    # 400 dona bo'lib chiqishi kabi). Endi bu yerda hech narsa qilinmaydi.

    qoplamachi_bonus_avtomatik = (jami_metr + jami_panel_metr + jami_dona) * 1000
    jami_m2 = jami_metr + jami_panel_metr

    # Jami ishlatilgan blok (hodim to'lovi "per_unit: blok" uchun)
    jami_blok = 0.0
    default_p = _hk_std_peno(db, company_id)   # kech89: hisobotda bir marta
    for order in orders_this_month:
        for item in order.items:
            if getattr(item, 'finished_product_id', None):
                continue
            vol = _item_volume_m3(db, item, default_p)
            pid = item.penoplast_id or (default_p.id if default_p else None)
            p = _inv_rep(pid)
            if p and p.volume_per_unit:
                jami_blok += vol / float(p.volume_per_unit)

    from models import FinishedProduct, StockSource
    fp_start, fp_end = _tashkent_oy_oraligi(year, month)
    # M4 (2026-09-18) — TENANT: hisobotning TAYYOR MAHSULOT qismi.
    # ESLATMA: bu funksiyaning qolgan so'rovlari hali tenant bilan
    # cheklanmagan — ular M6 (moliya/hisobotlar) bosqichida ko'riladi.
    _fpm = db.query(FinishedProduct).filter(
        FinishedProduct.source == StockSource.PRODUCED,
        FinishedProduct.created_at >= fp_start,
        FinishedProduct.created_at < fp_end
    )
    if company_id is not None:
        _fpm = _fpm.filter(FinishedProduct.company_id == company_id)
    finished_this_month = _fpm.all()
    for fp in finished_this_month:
        if fp.penoplast_id and fp.volume_m3:
            p = _inv_rep(fp.penoplast_id)
            if p and p.volume_per_unit:
                jami_blok += float(fp.volume_m3) / float(p.volume_per_unit)

    # ── 3. XARAJATLAR (bazadan) ──────────────────────────────
    _mexq = db.query(MonthlyExpense).filter(
        MonthlyExpense.year  == year,
        MonthlyExpense.month == month
    )
    if company_id is not None:      # M6
        _mexq = _mexq.filter(MonthlyExpense.company_id == company_id)
    expense = _mexq.first()

    if not expense:
        # Bo'sh xarajat
        xarajatlar = {
            "arenda": 0, "elektr": 0, "tushlik": 0, "soliqlar": 0,
            "hodim1_ism": "Hodim 1", "hodim1_oylik": 0,
            "hodim2_ism": "Hodim 2", "hodim2_oylik": 0,
            "hodim3_ism": "Hodim 3", "hodim3_oylik": 0,
            "qoplamachi_ism": "Qoplamachi", "qoplamachi_oylik": 0,
            "qoplamachi_bonus": qoplamachi_bonus_avtomatik,
            "notes": ""
        }
    else:
        xarajatlar = {
            "arenda":    float(expense.arenda or 0),
            "elektr":    float(expense.elektr or 0),
            "tushlik":   float(expense.tushlik or 0),
            "soliqlar":  float(expense.soliqlar or 0),
            "hodim1_ism":   expense.hodim1_ism,
            "hodim1_oylik": float(expense.hodim1_oylik or 0),
            "hodim2_ism":   expense.hodim2_ism,
            "hodim2_oylik": float(expense.hodim2_oylik or 0),
            "hodim3_ism":   expense.hodim3_ism,
            "hodim3_oylik": float(expense.hodim3_oylik or 0),
            "qoplamachi_ism":   expense.qoplamachi_ism,
            "qoplamachi_oylik": float(expense.qoplamachi_oylik or 0),
            "qoplamachi_bonus": float(expense.qoplamachi_bonus or qoplamachi_bonus_avtomatik),
            "notes": expense.notes or ""
        }

    # ── YANGI: mavjud bo'lsa, ExpenseTransaction yig'indisidan olamiz;
    # aks holda yuqoridagi (MonthlyExpense'dan) qiymat saqlanadi (orqaga moslik) ──
    xarajatlar["arenda"]   = _monthly_category_amount(db, year, month, "arenda",   xarajatlar["arenda"], company_id=company_id)
    xarajatlar["elektr"]   = _monthly_category_amount(db, year, month, "elektr",   xarajatlar["elektr"], company_id=company_id)
    xarajatlar["tushlik"]  = _monthly_category_amount(db, year, month, "tushlik",  xarajatlar["tushlik"], company_id=company_id)
    xarajatlar["soliqlar"] = _monthly_category_amount(db, year, month, "soliqlar", xarajatlar["soliqlar"], company_id=company_id)

    # ── 4a2. YANGI (moslashuvchan) kategoriyalar — Reklama, Kutilmagan xarajat
    # va h.k. — bular MonthlyExpense'da "qattiq" maydon sifatida yo'q,
    # shuning uchun ExpenseTransaction'dan TO'G'RIDAN-TO'G'RI, dinamik yig'ib olinadi.
    from models import ExpenseTransaction
    from sqlalchemy import func as _func, or_ as _or_kt
    from models import KIRIM_TANNARX_MANBA as _KTM
    KNOWN_FIXED_CATEGORIES = {"arenda", "elektr", "tushlik", "soliqlar"}
    extra_rows = db.query(
        ExpenseTransaction.category, _func.sum(ExpenseTransaction.amount)
    ).filter(
        _tashkent_oyida(ExpenseTransaction.date, year, month),
        ~ExpenseTransaction.category.in_(KNOWN_FIXED_CATEGORIES),
        # kech87 (104-band): tannarxga qo'shilgan kirim xarajati — xomashyo tannarxida, ikkinchi marta EMAS.
        # NULL `source` (eski yozuvlar) — oddiy xarajat (`!=` NULL ni tashlab yuborardi — shuning uchun `or_`).
        _or_kt(ExpenseTransaction.source.is_(None), ExpenseTransaction.source != _KTM),
        *( [ExpenseTransaction.company_id == company_id] if company_id is not None else [] )  # M6
    ).group_by(ExpenseTransaction.category).all()
    qoshimcha_xarajatlar = {cat: float(total or 0) for cat, total in extra_rows}
    qoshimcha_xarajat_jami = sum(qoshimcha_xarajatlar.values())

    # ── 3b. BRAK (yaroqsiz) SABABLI ISROF BO'LGAN XOMASHYO ─────
    # Bu — haqiqiy zarar (xomashyo ishlatildi, lekin sotilmadi), shuning
    # uchun boshqa xarajatlar kabi Sof foydadan ayirilishi kerak.
    import crud as _crud_brak
    _brak_start, _brak_end = _tashkent_oy_oraligi(year, month)
    try:
        brak_summary = _crud_brak.get_brak_material_summary(db, start_date=_brak_start, end_date=_brak_end, company_id=company_id)
        brak_xarajat = float(brak_summary.get("total_value", 0) or 0)
    except Exception:
        brak_xarajat = 0.0

    # Tayyor mahsulot yo'qotishi (masalan omborda turganda sinib qolgan mahsulot) — xarajat. kech107 (49-band,
    # egasi qarori "Bitta raqam"): ilgari "Brak" qatoriga QO'SHILARDI — karta / tahlil bilan uch xil raqam chiqardi;
    # endi ALOHIDA qator (`fp_loss_xarajat` — "Tayyor mahsulot yo'qotishi (omborda)"), "Brak" = faqat brak harakatlari
    # (haqiqiy xomashyo narxi — karta, bosh sahifa, tahlil bilan BITTA raqam). Jami xarajat va sof foyda O'ZGARMAYDI.
    # MUHIM (2026-09 chuqur audit — ikkinchi bosqich): "Ishlab chiqarish
    # jarayonidagi brak" (record_finished_product_production_brak, Tayyor
    # mahsulotlar sahifasi) uchun QO'SHIMCHA sarflangan xomashyo (Penoplast/
    # Loy) IKKI YO'LDA ham qayd etiladi — (1) shu FinishedProductLoss
    # yozuvining cost_amount'ida VA (2) InventoryMovement'da ("Brak
    # (ishlab chiqarish) — ..." sababi bilan, get_brak_material_summary()
    # buni "Brak%" naqshi orqali yig'ib, yuqorida brak_xarajat'ga
    # allaqachon qo'shib bo'lgan). Shuning uchun bu yerda FAQAT haqiqiy
    # "zaxiradan kamaytirish" (record_finished_product_loss, xomashyoga
    # umuman tegmaydi) yozuvlari hisoblanadi — "ishlab chiqarish braki"
    # yozuvlari BU YERDA hisobga OLINMAYDI, aks holda IKKI MARTA
    # ayirilib, "Sof foyda" haqiqatdan kamroq ko'rsatilardi.
    from models import FinishedProductLoss as _FPL
    # kech57 (40-band): belgi — YAGONA manba `crud._ISH_BRAK_BELGI` (ilgari shu
    # yerda literal nusxa edi; biri o'zgarsa ishlab chiqarish braki ikki marta
    # ayirilardi yoki bekor qilish ruxsat etilardi).
    import crud as _crud_belgi
    _PROD_BRAK_MARKER = _crud_belgi._ISH_BRAK_BELGI
    _fplq = db.query(_FPL).filter(
        _tashkent_oyida(_FPL.lost_at, year, month)
    )
    if company_id is not None:      # M6
        _fplq = _fplq.filter(_FPL.company_id == company_id)
    fp_losses = _fplq.all()
    fp_loss_xarajat = sum(
        float(l.cost_amount or 0) for l in fp_losses
        if not (l.reason or '').startswith(_PROD_BRAK_MARKER)
    )
    # kech107 (49-band): `brak_xarajat` ga QO'SHILMAYDI — jami xarajatga alohida qo'shiladi (pastda).

    # Jami xarajat (arenda/elektr/tushlik/soliq/reklama/kutilmagan va h.k. — hodim
    # to'lovi endi "Ustalar KPI / Hodimlar" bo'limida alohida hisoblanadi)
    # kech87 (104-band, FOYDALANUVCHI QARORI): korxona to'lagan transport — to'langan oyning xarajati.
    # (1) kirish transporti: xarid oynasidagi "o'z hisobimdan" va alohida "Kirish transporti"
    #     (`TransportExpense`, `expense_date` bo'yicha); (2) yetkazish transporti — korxona hisobidan
    #     (`Delivery.company_transport_cost`: "company" — to'liq, "split" — yarmi; `delivered_at` bo'yicha).
    # Ilgari ikkalasi ham sof foydaga UMUMAN kirmasdi (faqat "naqd xarajat" qatorida — O'LCHANGAN, probe104
    # K1 / K2 / K7 / K9). Kirim hujjatining transporti bu yerga KIRMAYDI — u `ExpenseTransaction`
    # ("transport_kirim") sifatida yuqoridagi qo'shimcha xarajatlarda (yoki tannarxda) allaqachon bor.
    _tr_foyda = get_transport_stats_for_period(db, year, month, company_id=company_id)
    transport_xarajat_kirish = float(_tr_foyda.get("inbound_aniq", 0) or 0)
    transport_xarajat_yetkazish = float(_tr_foyda.get("outbound_company_aniq", 0) or 0)
    transport_xarajat = transport_xarajat_kirish + transport_xarajat_yetkazish

    jami_xarajat_eski = (
        xarajatlar["arenda"] +
        xarajatlar["elektr"] +
        xarajatlar["tushlik"] +
        xarajatlar["soliqlar"] +
        qoshimcha_xarajat_jami +
        brak_xarajat +
        fp_loss_xarajat +           # kech107 (49-band): tayyor mahsulot yo'qotishi — alohida qator, jami o'zgarmaydi
        transport_xarajat
    )

    # ── 4b. USTA YILLIK KPI (oylik ulush) ─────────────────────
    kpi_result = calculate_monthly_master_kpi(db, year, month, company_id=company_id)
    usta_kpi_xarajat = kpi_result["total"]

    # ── 4b2. EHSON (admin belgilagan foiz, sof foydadan) ──────
    ehson_result = calculate_monthly_ehson(db, year, month, company_id=company_id)
    ehson_xarajat = ehson_result["ehson_amount"]

    # ── 4c. MOSLASHUVCHAN HODIMLAR ─────────────────────────────
    # Foyda (hodim xarajatigacha) — sotuvdan% / foydadan% hisoblash uchun.
    # MUHIM: Tayyor mahsulot to'g'ridan-to'g'ri sotuvi —
    # bu ham korxona sotuvi/foydasi, shuning uchun "sotuvdan %"/"foydadan %"
    # asosida to'lanadigan hodimlar uchun HAM hisobga olinadi (Ehson bilan
    # bir xil mantiq). Lekin ISHLAB CHIQARISH MIQDORIGA (metr/dona/qop)
    # bog'liq to'lov turlariga — ta'sir qilmaydi (chunki sotish — yangi
    # jismoniy ishlab chiqarish emas, faqat ombordagi tayyor narsani sotish).
    sof_foyda_before_emp = sof_daromad - jami_xarajat_eski - usta_kpi_xarajat - ehson_xarajat + fp_sales_foyda
    emp_result = calculate_monthly_employee_pay(
        db, year, month, daromad + fp_sales_daromad, sof_foyda_before_emp,
        jami_metr + jami_panel_metr, jami_dona, jami_blok,
        jami_qoplama_birlik=jami_metr + jami_panel_metr + jami_dona,
        company_id=company_id
    )
    hodimlar_moslashuvchan_xarajat = emp_result["total"]
    jami_xarajat = jami_xarajat_eski + usta_kpi_xarajat + ehson_xarajat + hodimlar_moslashuvchan_xarajat

    sof_foyda = sof_daromad - jami_xarajat + fp_sales_foyda
    foyda_foiz = (sof_foyda / (daromad + fp_sales_daromad) * 100) if (daromad + fp_sales_daromad) > 0 else 0

    # ── 5. NAQD XARAJATLAR (xomashyo xaridi + transport) ─────
    # Diqqat: bu "ishlab_chiqarish_xarajat" dan FARQ QILADI —
    # u shu oy TUGAGAN buyurtmalarga sarflangan xomashyo tan narxi,
    # bu esa shu oy SOTIB OLINGAN xomashyo puli (hali ishlatilmagan bo'lishi mumkin).
    purchase_stats = get_purchase_stats_for_period(db, year, month, company_id=company_id)
    transport_stats = get_transport_stats_for_period(db, year, month, company_id=company_id)

    xomashyo_xaridi = purchase_stats["total_amount"]
    transport_kirish = transport_stats["inbound_total"]
    transport_chiqish = transport_stats["outbound_company"]
    # kech88 (105-band, O'LCHANGAN — probe105 K1 / K2 / K4 / K6): kirim hujjatining qo'shimcha xarajatlari
    # (transport / tushirish / yuklash / boshqa) ham shu oy chiqib ketgan pul — ilgari bu ko'rsatkichga KIRMASDI
    # (kunlik xarajatda esa kirardi). Ikkala tur sanaladi: tannarxga qo'shilmagan (`KIRIM_XARAJAT_MANBA` — sof foydada
    # "qo'shimcha xarajat") va tannarxga qo'shilgan (`KIRIM_TANNARX_MANBA` — xomashyo narxida). Qo'lda yozilgan
    # xarajat (manba "manual") bu yerga KIRMAYDI — kategoriyasi "transport_kirim" bo'lsa ham (probe105 K5).
    # `kirim_xarajatlari_jamida` — shulardan `jami_xarajat` ICHIDA ham bor qismi (bosh sahifa "Chiqim" i uni ikki
    # marta qo'shmasligi uchun).
    from models import KIRIM_XARAJAT_MANBA as _KXM_nq, KIRIM_TANNARX_MANBA as _KTM_nq
    _kx_rows = db.query(
        ExpenseTransaction.source, _func.sum(ExpenseTransaction.amount)
    ).filter(
        _tashkent_oyida(ExpenseTransaction.date, year, month),
        ExpenseTransaction.source.in_([_KXM_nq, _KTM_nq]),
        *( [ExpenseTransaction.company_id == company_id] if company_id is not None else [] )  # M6
    ).group_by(ExpenseTransaction.source).all()
    _kx = {src: float(total or 0) for src, total in _kx_rows}
    kirim_xarajatlari = round(sum(_kx.values()))
    kirim_xarajatlari_jamida = float(_kx.get(_KXM_nq, 0.0))
    naqd_xarajat_jami = xomashyo_xaridi + transport_kirish + transport_chiqish + kirim_xarajatlari

    # ── 6. YO'NALISHLAR BO'YICHA DAROMAD (kech117, A2 — egasi QARORLARI kech114; ilgari «Gips / Penoplast» ikkiga) ──
    # YAGONA qoida — `yonalish_daromadlari` (yo'nalishlar hisoboti, bugungi ko'rsatkich, dashboard grafigi bilan bir):
    # buyurtma — detallar narx ulushida, qaytarish — qaytgan detal, tayyor mahsulot sotuvi — mahsulot turi.
    _yx = _YonXarita(db, company_id)
    yonalishlar_daromadi = yonalishlar_royxati_hisobot(_yx, yonalish_daromadlari(
        db, company_id, ready_orders, lambda _o: yakun_daromadi(db, _o), qaytarishlar=_qaytarishlar,
        tm_sotuvlari=fp_sales, xarita=_yx))

    # kech116 (G1-02, O'LCHANGAN — audit kech114: bir oy uchun «Xarajat» Hisobotlar kartasida 3.3 mln, shu sahifadagi
    # «Xarajat tarkibi» doirasida 3.1 mln (transport va brak yo'q), Dashboard «Jami xarajat» 4.3 mln (tannarx qo'shilgan),
    # Dashboard qatorlari esa hech biriga teng emas; 1.0 mln tannarx Hisobotlarda ko'rinmasdi). «Xarajat» — BITTA ta'rif:
    # `jami_xarajat` (sof foydadan ayriladigan xarajatlar; tannarx ALOHIDA). `xarajat_tarkibi` — uning to'liq tarkibi
    # (yig'indisi = `jami_xarajat`); `tannarx_jami` — sotilgan mahsulot tannarxi (buyurtmalar + tayyor mahsulot sotuvi),
    # shunda: daromad − tannarx_jami − jami_xarajat = sof_foyda. Hisobotlar, Dashboard (va Moliya) shundan.
    xarajat_tarkibi = [
        {"kalit": "doimiy", "nom": "Doimiy (arenda, elektr, tushlik, soliq)",
         "summa": round(xarajatlar["arenda"] + xarajatlar["elektr"] + xarajatlar["tushlik"] + xarajatlar["soliqlar"], 2)},
        {"kalit": "qoshimcha", "nom": "Qo'shimcha xarajatlar", "summa": round(qoshimcha_xarajat_jami, 2)},
        {"kalit": "transport", "nom": "Transport", "summa": round(transport_xarajat, 2)},
        {"kalit": "brak", "nom": "Brak (xomashyo)", "summa": round(brak_xarajat, 2)},
        {"kalit": "tm_yoqotish", "nom": "Tayyor mahsulot yo'qotishi", "summa": round(fp_loss_xarajat, 2)},
        {"kalit": "usta_kpi", "nom": "Usta bonusi (KPI)", "summa": round(usta_kpi_xarajat, 2)},
        {"kalit": "ehson", "nom": "Ehson", "summa": round(ehson_xarajat, 2)},
        {"kalit": "hodimlar", "nom": "Hodimlar oyligi", "summa": round(hodimlar_moslashuvchan_xarajat, 2)},
    ]
    tannarx_jami = ishlab_chiqarish_xarajat + fp_sales_tannarx

    return {
        "year": year,
        "month": month,
        "month_name": [
            "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
            "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"
        ][month],
        "daromad": round(daromad + fp_sales_daromad),
        "daromad_buyurtmalardan": round(daromad),
        # kech102 (144-band): shu oydagi qaytarishlar (daromad va ishlab chiqarish xarajati ICHIDA) — alohida qator uchun
        "qaytarish_daromad": round(qaytarish_daromad),
        "qaytarish_tannarx": round(qaytarish_tannarx),
        "qaytarish_soni": len(_qaytarishlar),
        "fp_sales_daromad": round(fp_sales_daromad),
        "fp_sales_foyda": round(fp_sales_foyda),
        "fp_sales_soni": len(fp_sales),
        "fp_loss_xarajat": round(fp_loss_xarajat),
        "fp_loss_soni": len(fp_losses),
        "ishlab_chiqarish_xarajat": ishlab_chiqarish_xarajat,
        "sof_daromad": sof_daromad,
        "buyurtmalar_soni": buyurtmalar_soni,
        "jami_m2": round(jami_m2, 2),
        "jami_metr": round(jami_metr, 2),
        "jami_dona": int(jami_dona),
        "qoplamachi_bonus_avtomatik": qoplamachi_bonus_avtomatik,
        "xarajatlar": xarajatlar,
        "qoshimcha_xarajatlar": qoshimcha_xarajatlar,
        "hodimlar_breakdown": emp_result["breakdown"],
        "jami_xarajat": jami_xarajat,
        "sof_foyda": sof_foyda,
        "foyda_foiz": round(foyda_foiz, 1),
        "expense_id": expense.id if expense else None,
        # Usta yillik KPI (oylik ulush)
        "usta_kpi_xarajat": usta_kpi_xarajat,
        "usta_kpi_breakdown": kpi_result["breakdown"],
        # Ehson (admin belgilagan foiz)
        "ehson_percent": ehson_result["percent"],
        "ehson_xarajat": ehson_xarajat,
        "brak_xarajat": round(brak_xarajat),
        # Faqat yakunlangan BUYURTMALARNING sof foydasi (oylik xarajatlarsiz) —
        # "Sof foyda"dan FARQLI, qo'shimcha ko'rsatkich. Allaqachon ehson_result
        # ichida hisoblangan qiymatning o'zi — yangi hisob-kitob emas.
        "buyurtmalar_foydasi": ehson_result["monthly_profit"],
        # Moslashuvchan hodimlar
        "hodimlar_moslashuvchan_xarajat": hodimlar_moslashuvchan_xarajat,
        "hodimlar_moslashuvchan_breakdown": emp_result["breakdown"],
        # kech117 (A2): yo'nalishlar bo'yicha daromad [{kalit, nom, daromad}] (yig'indisi = daromad)
        "yonalishlar_daromadi": yonalishlar_daromadi,
        # kech117 (A2, G3-11 / G6-09): sof foydaning AYNAN qismlari (yaxlitlanmagan):
        # daromad_buyurtmalar + daromad_tm − tannarx_buyurtmalar − tannarx_tm − (8 xarajat) = sof_foyda
        "sof_foyda_tarkibi": {
            "daromad_buyurtmalar": daromad, "daromad_tm": fp_sales_daromad,
            "tannarx_buyurtmalar": ishlab_chiqarish_xarajat, "tannarx_tm": fp_sales_tannarx,
            "doimiy": xarajatlar["arenda"] + xarajatlar["elektr"] + xarajatlar["tushlik"] + xarajatlar["soliqlar"],
            "qoshimcha": qoshimcha_xarajat_jami, "transport": transport_xarajat, "brak": brak_xarajat,
            "tm_yoqotish": fp_loss_xarajat, "usta_kpi": usta_kpi_xarajat, "ehson": ehson_xarajat,
            "hodimlar": hodimlar_moslashuvchan_xarajat,
        },
        # kech116 (G1-02): xarajatning YAGONA tarkibi (yig'indisi = jami_xarajat) va to'liq tannarx
        "xarajat_tarkibi": xarajat_tarkibi,
        "tannarx_jami": round(tannarx_jami, 2),
        "fp_sales_tannarx": round(fp_sales_tannarx, 2),
        "jami_blok": round(jami_blok, 2),
        # Naqd xarajatlar (alohida ko'rsatkich — foyda hisobiga kirmaydi)
        "xomashyo_xaridi": xomashyo_xaridi,
        "xomashyo_by_material": purchase_stats["by_material"],
        "transport_kirish": transport_kirish,
        "transport_chiqish_company": transport_chiqish,
        # kech87 (104-band): sof foydadan ayrilgan transport (jami_xarajat ICHIDA)
        "transport_xarajat": transport_xarajat,
        "transport_xarajat_kirish": transport_xarajat_kirish,
        "transport_xarajat_yetkazish": transport_xarajat_yetkazish,
        "naqd_xarajat_jami": naqd_xarajat_jami,
        # kech88 (105-band): kirim hujjati qo'shimcha xarajatlari (naqd ichida) va ularning jami_xarajat dagi qismi
        "kirim_xarajatlari": kirim_xarajatlari,
        "kirim_xarajatlari_jamida": kirim_xarajatlari_jamida,
    }


# ============================================================
# kech117 (A2) — YO'NALISHLAR BO'YICHA MOLIYA (egasi QARORLARI kech114 00:08 — QAYTA SO'RALMAYDI)
# ============================================================
# «Sof foyda» — BITTA raqam (Moliya); yo'nalishlar hisoboti AYNAN shuni bo'ladi (yig'indisi teng — tiyinigacha va
# ko'rsatiladigan butun so'mda ham). Qoidalar:
#   * daromad va tannarx — sotilgan mahsulot yo'nalishiga ANIQ: kodda doimiy turkumlar (profil, panel, donali, blok,
#     loy sotish) — asosiy yo'nalish; MRP detali / MRP tayyor mahsuloti — mahsulot turining yo'nalishi (biriktirilmagan
#     — «Belgilanmagan»); buyurtma kelishilgan summasi detallarga narx ulushida; qaytarish — qaytgan detal bo'yicha;
#   * yo'nalishi belgilangan hodim, xarajat, transport (va kirimning qo'shimcha xarajatlari) — 100 % o'sha yo'nalishga;
#     brak — brak yozuvining detali / tayyor mahsuloti yo'nalishiga; omborda tayyor mahsulot yo'qotishi — mahsulotiga;
#   * qolgani UMUMIY (arenda, svet, soliq, tushlik, Ehson, usta KPI, belgilanmagan transport / «Boshqa», yo'nalishsiz
#     hodimlar, detalga bog'lanmagan brak) — TAQSIMLANMAYDI (egasi QARORI kech118, 15:23 — kech114 dagi «daromad
#     ulushiga qarab» qoidasi BEKOR): faqat «Jami» ustunida alohida qator. Yo'nalish ustunida NATIJA = daromad −
#     tannarx − oyliklar (o'z hodimlari) − xarajatlar (o'ziniki); Jami NATIJA = korxona sof foydasi (Moliya bilan AYNAN).
#     Kassa — BITTA (bo'linmaydi).
_YON_BELGILANMAGAN = "belgilanmagan"
_YON_ASOSIY_VIRTUAL = "asosiy"


class _YonXarita:
    """Korxona yo'nalishlari va bog'lamlar — faqat O'QIYDI (hisobot hech narsa yozmaydi). Kalit: "y<id>" (yo'nalish),
    "belgilanmagan" (MRP turi biriktirilmagan / eski turkum), "asosiy" (asosiy yo'nalish hali yaratilmagan korxona)."""

    def __init__(self, db: Session, company_id: int = None):
        from models import Yonalish, YONALISH_ASOSIY_KOD
        self.db = db
        self.cid = company_id
        q = db.query(Yonalish)
        if company_id is not None:
            q = q.filter(Yonalish.company_id == company_id)
        self.royxat = q.all()
        std = sorted((y for y in self.royxat if y.kod == YONALISH_ASOSIY_KOD), key=lambda y: y.id)
        self.asosiy = std[0] if std else None
        self.asosiy_kalit = f"y{self.asosiy.id}" if self.asosiy is not None else _YON_ASOSIY_VIRTUAL
        self.nomlar = {f"y{y.id}": y for y in self.royxat}
        self._pt = None

    def _turlar(self) -> dict:
        if self._pt is None:
            from production_models import ProductType as _PT117
            db, company_id = self.db, self.cid
            q = db.query(_PT117.id, _PT117.yonalish_id)
            if company_id is not None:
                q = q.filter(_PT117.company_id == company_id)
            self._pt = {i: y for i, y in q.all()}
        return self._pt

    def yid_kalit(self, yid):
        """`yonalish_id` → kalit; NULL / begona — None («Umumiy»)."""
        if yid is None:
            return None
        k = f"y{yid}"
        return k if k in self.nomlar else None

    def tur_kalit(self, pt_id) -> str:
        return self.yid_kalit(self._turlar().get(pt_id)) or _YON_BELGILANMAGAN

    def detal_kalit(self, item) -> str:
        from models import YONALISH_ASOSIY_TURKUMLAR
        cat = (getattr(item, "category", None) or "").lower()
        if cat in YONALISH_ASOSIY_TURKUMLAR:
            return self.asosiy_kalit
        if cat == "mrp_product" and getattr(item, "product_type_id", None):
            return self.tur_kalit(item.product_type_id)
        return _YON_BELGILANMAGAN

    def tm_kalit(self, fp) -> str:
        from models import YONALISH_ASOSIY_TURKUMLAR
        if fp is None:
            return _YON_BELGILANMAGAN
        if getattr(fp, "product_type_id", None):
            return self.tur_kalit(fp.product_type_id)
        if (fp.category or "").lower() in YONALISH_ASOSIY_TURKUMLAR:
            return self.asosiy_kalit
        return _YON_BELGILANMAGAN

    def nom(self, kalit) -> str:
        from models import YONALISH_ASOSIY_NOM
        if kalit == _YON_BELGILANMAGAN:
            return "Belgilanmagan"
        if kalit == _YON_ASOSIY_VIRTUAL:
            return YONALISH_ASOSIY_NOM
        y = self.nomlar.get(kalit)
        return y.nom if y is not None else str(kalit)

    def korinadigan(self) -> list:
        """Ko'rinadigan (yashirilmagan) yo'nalish kalitlari: asosiy birinchi, keyin `tartib`, `id`."""
        from models import YONALISH_ASOSIY_KOD
        ys = [y for y in self.royxat if not y.yashirin]
        ys.sort(key=lambda y: (0 if y.kod == YONALISH_ASOSIY_KOD else 1, y.tartib or 0, y.id))
        k = [f"y{y.id}" for y in ys]
        if self.asosiy is None:
            k.insert(0, _YON_ASOSIY_VIRTUAL)
        return k

    def tartibla(self, kalitlar) -> list:
        """Kalitlarni ko'rsatish tartibida: ko'rinadiganlar, keyin yashirinlar (`id`), oxirida «Belgilanmagan»."""
        asos = self.korinadigan()
        qolgan = sorted((k for k in set(kalitlar) if k not in asos and k != _YON_BELGILANMAGAN),
                        key=lambda k: (int(k[1:]) if k[:1] == "y" and k[1:].isdigit() else 0, k))
        natija = [k for k in asos if k in set(kalitlar)] + qolgan
        if _YON_BELGILANMAGAN in set(kalitlar):
            natija.append(_YON_BELGILANMAGAN)
        return natija


def _vaznli_taqsim(summa, vaznlar) -> dict:
    """`summa` ni [(kalit, vazn)] nisbatida bo'ladi (manfiy vazn — 0). Yig'indi AYNAN `summa` (oxirgi qism — qoldiq).
    Vazn yig'indisi 0 — qatorlarga teng; ro'yxat bo'sh — hammasi «Belgilanmagan»."""
    summa = float(summa or 0)
    qatorlar = [(k, max(float(v or 0), 0.0)) for k, v in (vaznlar or [])]
    if not qatorlar:
        return {_YON_BELGILANMAGAN: summa} if summa else {}
    jami = sum(v for _k, v in qatorlar)
    if jami <= 0:
        qatorlar = [(k, 1.0) for k, _v in qatorlar]
        jami = float(len(qatorlar))
    natija, qoldi = {}, summa
    for i, (k, v) in enumerate(qatorlar):
        ulush = qoldi if i == len(qatorlar) - 1 else summa * v / jami
        natija[k] = natija.get(k, 0.0) + ulush
        qoldi -= ulush if i < len(qatorlar) - 1 else 0.0
    return natija


def _buyurtma_vaznlari(xarita: "_YonXarita", order) -> list:
    """Buyurtma detallari yo'nalishi va vazni (detal narxi) — kelishilgan summa va buyurtma darajasidagi tannarx
    (usta haqi) shu nisbatda bo'linadi (eski «turlar bo'yicha» taqsimot ham shu ulushni ishlatardi)."""
    return [(xarita.detal_kalit(it), float(it.total_price or 0)) for it in (order.items or [])]


def _qosh(d: dict, qism: dict, ishora: float = 1.0) -> None:
    for k, v in qism.items():
        d[k] = d.get(k, 0.0) + ishora * v


def yonalish_daromadlari(db: Session, company_id: int, buyurtmalar, summa_fn, qaytarishlar=(), tm_sotuvlari=(),
                         xarita: "_YonXarita" = None) -> dict:
    """Daromadning yo'nalishlarga taqsimoti {kalit: summa} — YAGONA qoida (oylik hisobot, yo'nalishlar hisoboti,
    bugungi ko'rsatkich, dashboard grafigi). `summa_fn(order)` — buyurtma daromadi (hisobotda `yakun_daromadi`);
    `qaytarishlar` — `davr_qaytarishlari` hodisalari; `tm_sotuvlari` — `FinishedProductSale` lar."""
    x = xarita or _YonXarita(db, company_id)
    natija = {}
    for o in buyurtmalar:
        _qosh(natija, _vaznli_taqsim(summa_fn(o), _buyurtma_vaznlari(x, o)))
    for h in qaytarishlar:
        _qosh(natija, _vaznli_taqsim(h["daromad"], _qaytarish_vaznlari(x, h)))
    for sv in tm_sotuvlari:
        k = x.tm_kalit(getattr(sv, "finished_product", None))
        natija[k] = natija.get(k, 0.0) + float(sv.total_amount or 0)
    return natija


def _qaytarish_vaznlari(xarita: "_YonXarita", h: dict) -> list:
    """Qaytarish hodisasi — qaytgan detallar yo'nalishi (vazn: qaytarilgan pul / omborga qaytgan tannarx); detali
    ma'lum emas — buyurtma detallari ulushida."""
    o = h["order"]
    detallar = {it.id: it for it in (o.items or [])}
    vazn = [(xarita.detal_kalit(detallar[i]), w) for i, w in (h.get("detallar") or [])
            if i in detallar and float(w or 0) > 0]
    return vazn or _buyurtma_vaznlari(xarita, o)


def yonalishlar_royxati_hisobot(xarita: "_YonXarita", summalar: dict) -> list:
    """{kalit: summa} → [{"kalit", "nom", "daromad"}] (ko'rsatish tartibida, ko'rinadigan yo'nalishlar — 0 bo'lsa ham)."""
    kalitlar = set(xarita.korinadigan()) | {k for k, v in summalar.items() if abs(v) >= 0.005}
    return [{"kalit": k, "nom": xarita.nom(k), "daromad": round(summalar.get(k, 0.0), 2)}
            for k in xarita.tartibla(kalitlar)]


def _yaxlit_taqsim(qiymatlar: dict, jami_birlik: int, birlik: int) -> dict:
    """{kalit: qiymat} ni `birlik` (1 — so'm, 100 — tiyin) butunlariga yaxlitlaydi, yig'indisi AYNAN `jami_birlik`
    (eng katta qoldiq usuli)."""
    import math
    kalitlar = list(qiymatlar)
    if not kalitlar:
        return {}
    xom = {k: float(qiymatlar[k]) * birlik for k in kalitlar}
    past = {k: math.floor(xom[k] + 1e-9) for k in kalitlar}
    farq = int(jami_birlik) - sum(past.values())
    tartib = sorted(kalitlar, key=lambda k: -(xom[k] - past[k]))
    if farq >= 0:
        for i in range(farq):
            past[tartib[i % len(tartib)]] += 1
    else:
        for i in range(-farq):
            past[tartib[-1 - (i % len(tartib))]] -= 1
    return past


def _yaxlit(x: float, birlik: int) -> int:
    """Yarmidan yuqoriga (HALF_UP) yaxlitlash `birlik` butunlariga (manfiyda ham simmetrik)."""
    from decimal import Decimal, ROUND_HALF_UP
    return int((Decimal(repr(float(x))) * birlik).quantize(Decimal(1), rounding=ROUND_HALF_UP))


_YON_XARAJAT_NOMLARI = (
    ("hodimlar", "Hodimlar oyligi"),
    ("doimiy", "Doimiy (arenda, elektr, tushlik, soliq)"),
    ("qoshimcha", "Qo'shimcha xarajatlar"),
    ("transport", "Transport"),
    ("brak", "Brak (xomashyo)"),
    ("tm_yoqotish", "Tayyor mahsulot yo'qotishi"),
    ("usta_kpi", "Usta bonusi (KPI)"),
    ("ehson", "Ehson"),
)


_YON_OYLIK = "hodimlar"
_YON_XARAJAT_QISMLARI = tuple(n for n, _x in _YON_XARAJAT_NOMLARI if n != _YON_OYLIK)
_YON_DAVR_MAX_OY = 36
_OY_TOLIQ = ("Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr",
             "Dekabr")


def yonalish_davr_oylari(yil: int, oy: int, gacha_yil: int = None, gacha_oy: int = None) -> list:
    """kech118 (egasi QARORI — «davr tanlash»): [(yil, oy), …] — `yil-oy` dan `gacha_yil-gacha_oy` gacha (ikkalasi
    ham kiradi). Davr OY bo'yicha (hisobotning hamma qismi — oylik hisobotdan, Moliya sof foydasi bilan AYNAN bo'lishi
    uchun). Noto'g'ri davr — ValueError (API 400 ga aylantiradi)."""
    gy = yil if gacha_yil is None else int(gacha_yil)
    go = oy if gacha_oy is None else int(gacha_oy)
    for _y, _o in ((yil, oy), (gy, go)):
        if not (1 <= int(_o) <= 12) or not (2000 <= int(_y) <= 2100):
            raise ValueError("Oy 1–12, yil 2000–2100 oralig'ida bo'lishi kerak")
    boshi, oxiri = int(yil) * 12 + int(oy) - 1, gy * 12 + go - 1
    if oxiri < boshi:
        raise ValueError("Davr oxiri boshidan oldin bo'lmasin")
    if oxiri - boshi + 1 > _YON_DAVR_MAX_OY:
        raise ValueError(f"Davr ko'pi bilan {_YON_DAVR_MAX_OY} oy bo'lsin")
    return [(k // 12, k % 12 + 1) for k in range(boshi, oxiri + 1)]


def yonalish_davr_nomi(oylar: list) -> str:
    """«Sentabr 2026», «Iyul – Sentabr 2026», «Noyabr 2025 – Fevral 2026»."""
    if not oylar:
        return ""
    (y1, o1), (y2, o2) = oylar[0], oylar[-1]
    if (y1, o1) == (y2, o2):
        return f"{_OY_TOLIQ[o1 - 1]} {y1}"
    if y1 == y2:
        return f"{_OY_TOLIQ[o1 - 1]} – {_OY_TOLIQ[o2 - 1]} {y2}"
    return f"{_OY_TOLIQ[o1 - 1]} {y1} – {_OY_TOLIQ[o2 - 1]} {y2}"


def yonalish_oldingi_davr(oylar: list) -> list:
    """Solishtirish davri: yil boshidan (yanvardan) boshlangan davr — o'tgan yilning AYNAN shu oylari; qolgani —
    oldingi TENG uzunlikdagi davr (bir oy — o'tgan oy; chorak — o'tgan chorak)."""
    if not oylar:
        return []
    (y1, o1), y2 = oylar[0], oylar[-1][0]
    if o1 == 1 and y1 == y2 and len(oylar) > 1:
        return [(y - 1, o) for y, o in oylar]
    n = len(oylar)
    boshi = y1 * 12 + o1 - 1 - n
    return [((boshi + i) // 12, (boshi + i) % 12 + 1) for i in range(n)]


def _yon_oy_aniq(db: Session, year: int, month: int, company_id, x: "_YonXarita") -> dict:
    """BIR oyning yo'nalishlar qismlari (yaxlitlanmagan): daromad / tannarx {kalit}, bevosita {qism: {kalit}},
    oylik hisobotning AYNAN qismlari `t` (sof foyda tarkibi), `sof`, «Belgilanmagan» manbalari va izohlar."""
    from models import (ExpenseTransaction as _ET, TransportExpense as _TE, Employee as _Emp,
                        FinishedProductSale as _FPS, FinishedProductLoss as _FPL, FinishedProduct as _FP,
                        ReturnItem as _RI, KIRIM_TANNARX_MANBA as _KTM)
    from sqlalchemy.orm import selectinload as _sil
    import crud as _crud

    full = get_monthly_report(db, year, month, company_id=company_id)
    t = full["sof_foyda_tarkibi"]
    boshi, oxiri = _tashkent_oy_oraligi(year, month)
    izohlar = []

    def _qoldiq_bilan(nom: str, taqsim: dict, pul: float, qoldiq_kalit=None) -> dict:
        """Taqsimot yig'indisi hovuzga teng bo'lishi SHART: suzuvchi nuqta qoldig'i (< 1 tiyin) — eng kattasiga;
        haqiqiy farq — `qoldiq_kalit` ga (None — «Belgilanmagan») va izoh."""
        farq = float(pul) - sum(taqsim.values())
        if abs(farq) < 0.005:
            if taqsim:
                k = max(taqsim, key=lambda q: abs(taqsim[q]))
                taqsim[k] += farq
            elif farq:
                taqsim[qoldiq_kalit or x.asosiy_kalit] = farq
        else:
            k = qoldiq_kalit or _YON_BELGILANMAGAN
            taqsim[k] = taqsim.get(k, 0.0) + farq
            if qoldiq_kalit is None:
                izohlar.append(f"{nom}: {round(farq, 2)} so'm yo'nalishga bog'lanmadi")
        return taqsim

    # ── 1. BUYURTMALAR: daromad va tannarx (yakunlangan paytdagi holat) ──
    _oq = db.query(Order).filter(Order.status == OrderStatus.READY, _tashkent_oyida(Order.completed_at, year, month))
    if company_id is not None:
        _oq = _oq.filter(Order.company_id == company_id)
    buyurtmalar = _oq.all()
    _hk_tayyorla(db, buyurtmalar)
    daromad_b, tannarx_b = {}, {}
    # kech117 (zip 115 jonli sinovi): «Belgilanmagan» daromadning MRP turidan boshqa manbalari (eski turkumli detal,
    # turi tanlanmagan MRP detali, detalsiz buyurtma, turi / asosiy turkumi yo'q tayyor mahsulot sotuvi) — egasiga nomi
    # bilan ko'rsatiladi (ilgari ustunda summa bor, sababi yo'q edi). Turi biriktirilmagan MRP — `belgilanmagan_turlar`.
    belg_manbalar = {}

    def _belg_qosh(nom: str, summa: float) -> None:
        if abs(float(summa or 0)) >= 0.005:
            belg_manbalar[nom] = belg_manbalar.get(nom, 0.0) + float(summa)

    def _buyurtma_belg_manbalari(o, daromad_summa: float) -> None:
        detallar = list(o.items or [])
        if not detallar:
            _belg_qosh(f"Buyurtma {o.order_number or o.id} — detalsiz", daromad_summa)
            return
        vaznlar = [max(float(it.total_price or 0), 0.0) for it in detallar]
        jami_v = sum(vaznlar)
        if jami_v <= 0:
            vaznlar, jami_v = [1.0] * len(detallar), float(len(detallar))
        for it, w in zip(detallar, vaznlar):
            if x.detal_kalit(it) != _YON_BELGILANMAGAN:
                continue
            cat = (getattr(it, "category", None) or "").lower()
            if cat == "mrp_product" and getattr(it, "product_type_id", None):
                continue
            nom = ("MRP detali — mahsulot turi tanlanmagan" if cat == "mrp_product"
                   else f"Eski «{cat or '—'}» turkumli detal")
            _belg_qosh(nom, daromad_summa * w / jami_v)

    for o in buyurtmalar:
        vazn = _buyurtma_vaznlari(x, o)
        _o_daromad = yakun_daromadi(db, o)
        _qosh(daromad_b, _vaznli_taqsim(_o_daromad, vazn))
        _buyurtma_belg_manbalari(o, _o_daromad)
        try:
            p = yakun_foydasi(db, o, company_id=company_id)
        except Exception:
            continue
        if not p.get("success"):
            continue
        detallar = {it.id: it for it in (o.items or [])}
        for q in p.get("tannarx_qismlari", []):
            summa = float(q.get("summa") or 0)
            did = q.get("detal_id")
            if did is not None and did in detallar:
                k = x.detal_kalit(detallar[did])
                tannarx_b[k] = tannarx_b.get(k, 0.0) + summa
            elif q.get("tur") in ("penoplast", "qoplama", "loy_sotish"):
                tannarx_b[x.asosiy_kalit] = tannarx_b.get(x.asosiy_kalit, 0.0) + summa
            else:
                _qosh(tannarx_b, _vaznli_taqsim(summa, vazn))
    for h in davr_qaytarishlari(db, boshi, oxiri, company_id=company_id):
        vazn = _qaytarish_vaznlari(x, h)
        _qosh(daromad_b, _vaznli_taqsim(h["daromad"], vazn))
        _qosh(tannarx_b, _vaznli_taqsim(h["tannarx"], vazn))
    _qoldiq_bilan("Buyurtmalar daromadi", daromad_b, t["daromad_buyurtmalar"])
    _qoldiq_bilan("Buyurtmalar tannarxi", tannarx_b, t["tannarx_buyurtmalar"])

    # ── 2. TAYYOR MAHSULOT SOTUVI (buyurtmasiz) ──
    _sq = db.query(_FPS).filter(_tashkent_oyida(_FPS.sold_at, year, month))
    if company_id is not None:
        _sq = _sq.filter(_FPS.company_id == company_id)
    daromad_tm, tannarx_tm = {}, {}
    for sv in _sq.options(_sil(_FPS.finished_product)).all():
        k = x.tm_kalit(sv.finished_product)
        daromad_tm[k] = daromad_tm.get(k, 0.0) + float(sv.total_amount or 0)
        tannarx_tm[k] = tannarx_tm.get(k, 0.0) + float(sv.cost_amount or 0)
        _fp_s = sv.finished_product
        if k == _YON_BELGILANMAGAN and (_fp_s is None or not getattr(_fp_s, "product_type_id", None)):
            _belg_qosh(f"Tayyor mahsulot sotuvi «{sv.product_name or '—'}» — mahsulot o'chirilgan" if _fp_s is None
                       else f"Tayyor mahsulot sotuvi «{_fp_s.name or sv.product_name or '—'}» (turkumi: "
                            f"{_fp_s.category or '—'})", float(sv.total_amount or 0))
    _qoldiq_bilan("Tayyor mahsulot sotuvi", daromad_tm, t["daromad_tm"])
    _qoldiq_bilan("Tayyor mahsulot sotuvi tannarxi", tannarx_tm, t["tannarx_tm"])

    # ── 3. XARAJATLAR — bevosita (yo'nalishi belgilangan / yozuvi bog'langan) ──
    bevosita = {nom: {} for nom, _n in _YON_XARAJAT_NOMLARI}

    def _et_q():
        q = db.query(_ET).filter(_tashkent_oyida(_ET.date, year, month), _ET.yonalish_id.isnot(None))
        return q.filter(_ET.company_id == company_id) if company_id is not None else q
    _DOIMIY = {"arenda", "elektr", "tushlik", "soliqlar"}
    for et in _et_q().all():
        k = x.yid_kalit(et.yonalish_id)
        if k is None:
            continue
        if et.category in _DOIMIY:
            bevosita["doimiy"][k] = bevosita["doimiy"].get(k, 0.0) + float(et.amount or 0)
        elif et.source is None or et.source != _KTM:
            bevosita["qoshimcha"][k] = bevosita["qoshimcha"].get(k, 0.0) + float(et.amount or 0)
    _tq = db.query(_TE).filter(_TE.expense_date >= boshi, _TE.expense_date < oxiri, _TE.yonalish_id.isnot(None))
    if company_id is not None:
        _tq = _tq.filter(_TE.company_id == company_id)
    for te in _tq.all():
        k = x.yid_kalit(te.yonalish_id)
        if k is not None:
            bevosita["transport"][k] = bevosita["transport"].get(k, 0.0) + float(te.amount or 0)
    # Hodimlar — oylik hisobotdagi AYNAN summalar (`hodimlar_breakdown`)
    _hb = full.get("hodimlar_breakdown", []) or []
    _eids = {b.get("employee_id") for b in _hb if b.get("employee_id")}
    _emap = {}
    if _eids:
        _eq = db.query(_Emp).filter(_Emp.id.in_(_eids))
        if company_id is not None:
            _eq = _eq.filter(_Emp.company_id == company_id)
        _emap = {e.id: e for e in _eq.all()}
    for b in _hb:
        e = _emap.get(b.get("employee_id"))
        k = x.yid_kalit(e.yonalish_id) if e is not None else None
        if k is not None:
            bevosita["hodimlar"][k] = bevosita["hodimlar"].get(k, 0.0) + float(b.get("amount") or 0)
    # Brak (xomashyo) — brak yozuviga bog'langan harakatlar (qaytarish detali / tayyor mahsuloti yo'nalishi) va ishlab
    # chiqarish braki (tayyor mahsulot yozuvi — `_ISH_BRAK_BELGI`) — o'z yo'nalishiga; bog'lanmagani (qo'lda «Brak»
    # chiqimi) — umumiy.
    _brak = _crud.get_brak_material_summary(db, start_date=boshi, end_date=oxiri, company_id=company_id,
                                            harakatlar=True)
    _ri_ids = {h["return_item_id"] for h in _brak.get("harakatlar", []) if h.get("return_item_id")}
    _ri = {}
    if _ri_ids:
        _rq = db.query(_RI).filter(_RI.id.in_(_ri_ids))
        if company_id is not None:
            _rq = _rq.filter(_RI.company_id == company_id)
        _ri = {r.id: r for r in _rq.all()}
    _oi_ids = {r.order_item_id for r in _ri.values() if r.order_item_id}
    _fp_ids = {r.finished_product_id for r in _ri.values() if r.finished_product_id}
    _oi = {}
    if _oi_ids:
        _iq = db.query(OrderItem).filter(OrderItem.id.in_(_oi_ids))
        if company_id is not None:
            _iq = _iq.filter(OrderItem.company_id == company_id)
        _oi = {i.id: i for i in _iq.all()}
    _fpl_q = db.query(_FPL).filter(_tashkent_oyida(_FPL.lost_at, year, month))
    if company_id is not None:
        _fpl_q = _fpl_q.filter(_FPL.company_id == company_id)
    _yoqotishlar = _fpl_q.all()
    _fp_ids |= {l.finished_product_id for l in _yoqotishlar if l.finished_product_id}
    _fp = {}
    if _fp_ids:
        _fq = db.query(_FP).filter(_FP.id.in_(_fp_ids))
        if company_id is not None:
            _fq = _fq.filter(_FP.company_id == company_id)
        _fp = {f.id: f for f in _fq.all()}
    for h in _brak.get("harakatlar", []):
        r = _ri.get(h.get("return_item_id"))
        k = None
        if r is not None and r.order_item_id in _oi:
            k = x.detal_kalit(_oi[r.order_item_id])
        elif r is not None and r.finished_product_id in _fp:
            k = x.tm_kalit(_fp[r.finished_product_id])
        if k is not None:
            bevosita["brak"][k] = bevosita["brak"].get(k, 0.0) + float(h.get("value") or 0)
    _ISH = _crud._ISH_BRAK_BELGI
    for l in _yoqotishlar:
        k = x.tm_kalit(_fp.get(l.finished_product_id)) if l.finished_product_id in _fp else None
        if k is None:
            continue
        if (l.reason or "").startswith(_ISH):
            bevosita["brak"][k] = bevosita["brak"].get(k, 0.0) + float(l.cost_amount or 0)
        else:
            bevosita["tm_yoqotish"][k] = bevosita["tm_yoqotish"].get(k, 0.0) + float(l.cost_amount or 0)
    return {"daromad_b": daromad_b, "daromad_tm": daromad_tm, "tannarx_b": tannarx_b, "tannarx_tm": tannarx_tm,
            "bevosita": bevosita, "t": {k: float(v or 0) for k, v in t.items()}, "sof": float(full["sof_foyda"]),
            "belg_manbalar": belg_manbalar, "izohlar": izohlar}


def _yon_davr_jami(db: Session, oylar: list, company_id=None) -> dict:
    """Solishtirish uchun davr yig'indisi (oylik hisobotdan): daromad, xarajat (tannarx + oylik + xarajatlar), natija
    (sof foyda). Butun so'mda."""
    d = x_ = n = 0.0
    for _y, _o in oylar:
        f = get_monthly_report(db, _y, _o, company_id=company_id)
        t = f["sof_foyda_tarkibi"]
        _d = float(t["daromad_buyurtmalar"]) + float(t["daromad_tm"])
        d += _d
        n += float(f["sof_foyda"])
        x_ += _d - float(f["sof_foyda"])
    return {"daromad": _yaxlit(d, 1), "xarajat": _yaxlit(x_, 1), "natija": _yaxlit(n, 1)}


def _ozgarish_foiz(joriy, oldingi):
    """(joriy − oldingi) / |oldingi| × 100, 1 xona; oldingi 0 — None (foiz ma'nosiz)."""
    joriy, oldingi = float(joriy or 0), float(oldingi or 0)
    if abs(oldingi) < 0.5:
        return None
    return round((joriy - oldingi) / abs(oldingi) * 100, 1)


@_hisobot_keshi_bilan
def calculate_split_profit_report(db: Session, year: int, month: int, company_id: int = None,
                                  gacha_yil: int = None, gacha_oy: int = None, solishtirish: bool = False) -> dict:
    """YO'NALISHLAR bo'yicha moliyaviy natija (kech117 A2; kech118 — egasi QARORI 15:23: umumiy xarajat TAQSIMLANMAYDI,
    oyliklar alohida, oxirida natija +/−; davr — bir yoki bir necha oy).

    Har yo'nalish ustuni (`som` — butun so'm, `aniq` — tiyin): daromad, tannarx, oylik (yo'nalishi belgilangan hodimlar
    — oylik hisobotdagi AYNAN summa), xarajat (o'ziga yozilgan: doimiy, qo'shimcha, transport, brak, tayyor mahsulot
    yo'qotishi …, `xarajat_qismlari`), natija = daromad − tannarx − oylik − xarajat. «Jami»: hamma ustunlar + yo'nalishsiz
    (umumiy) oylik va xarajatlar (`umumiy_oylik`, `umumiy_xarajat`, `umumiy_qismlari` — faqat shu yerda); Jami natija =
    Moliya sof foydasi (davr oylari yig'indisi; tiyinigacha va butun so'mda AYNAN). Moslik uchun: `bevosita` = oylik +
    xarajat, `bevosita_qismlari` (hodimlar + xarajat qismlari), `sof_foyda` = natija, `jami_xarajat` = oylik + xarajat.
    `solishtirish` — oldingi davr (`yonalish_oldingi_davr`) daromad / xarajat / natijasi va o'zgarish foizi."""
    oylar = yonalish_davr_oylari(year, month, gacha_yil, gacha_oy)
    x = _YonXarita(db, company_id)
    daromad, tannarx = {}, {}
    bevosita = {nom: {} for nom, _n in _YON_XARAJAT_NOMLARI}
    t_jami = {}
    sof = 0.0
    belg_manbalar, izohlar = {}, []
    ko_p_oy = len(oylar) > 1
    for _y, _o in oylar:
        q = _yon_oy_aniq(db, _y, _o, company_id, x)
        _qosh(daromad, q["daromad_b"])
        _qosh(daromad, q["daromad_tm"])
        _qosh(tannarx, q["tannarx_b"])
        _qosh(tannarx, q["tannarx_tm"])
        for nom, _n in _YON_XARAJAT_NOMLARI:
            _qosh(bevosita[nom], q["bevosita"][nom])
        for k, v in q["t"].items():
            t_jami[k] = t_jami.get(k, 0.0) + v
        sof += q["sof"]
        _qosh(belg_manbalar, q["belg_manbalar"])
        izohlar += [(f"{_OY_TOLIQ[_o - 1]} {_y}: " if ko_p_oy else "") + iz for iz in q["izohlar"]]

    # ── Yo'nalish ustunlari (aniq) ──
    kalitlar = set(x.korinadigan())
    for d in [daromad, tannarx] + list(bevosita.values()):
        kalitlar |= {k for k, v in d.items() if abs(v) >= 0.005}
    tartib = x.tartibla(kalitlar)
    umumiy = {nom: float(t_jami.get(nom, 0.0)) - sum(bevosita[nom].values()) for nom, _n in _YON_XARAJAT_NOMLARI}
    aniq = {}
    for k in tartib:
        _d, _t = daromad.get(k, 0.0), tannarx.get(k, 0.0)
        _ol = bevosita[_YON_OYLIK].get(k, 0.0)
        _xr = sum(bevosita[n].get(k, 0.0) for n in _YON_XARAJAT_QISMLARI)
        aniq[k] = {"daromad": _d, "tannarx": _t, "oylik": _ol, "xarajat": _xr, "natija": _d - _t - _ol - _xr}
    tekshiruv_farq = sof - (sum(a["natija"] for a in aniq.values()) - sum(umumiy.values()))

    def _ustunlar(birlik: int):
        """Butun `birlik` (1 — so'm, 100 — tiyin) larda: ustun ichida D − T − O − X = N; Jami: ΣN − umumiy = sof."""
        D = _yaxlit_taqsim({k: aniq[k]["daromad"] for k in tartib}, _yaxlit(sum(a["daromad"] for a in aniq.values()), birlik), birlik)
        T = _yaxlit_taqsim({k: aniq[k]["tannarx"] for k in tartib}, _yaxlit(sum(a["tannarx"] for a in aniq.values()), birlik), birlik)
        O = _yaxlit_taqsim({k: aniq[k]["oylik"] for k in tartib}, _yaxlit(sum(a["oylik"] for a in aniq.values()), birlik), birlik)
        X = _yaxlit_taqsim({k: aniq[k]["xarajat"] for k in tartib}, _yaxlit(sum(a["xarajat"] for a in aniq.values()), birlik), birlik)
        f = (lambda v: v) if birlik == 1 else (lambda v: v / birlik)
        natija, jn = {}, 0
        jq = {n: 0 for n in _YON_XARAJAT_QISMLARI}
        for k in tartib:
            N = D[k] - T[k] - O[k] - X[k]
            jn += N
            xq = _yaxlit_taqsim({n: bevosita[n].get(k, 0.0) for n in _YON_XARAJAT_QISMLARI}, X[k], birlik)
            for n in _YON_XARAJAT_QISMLARI:
                jq[n] += xq[n]
            natija[k] = {"daromad": f(D[k]), "tannarx": f(T[k]), "oylik": f(O[k]), "xarajat": f(X[k]), "natija": f(N),
                         "xarajat_qismlari": {n: f(v) for n, v in xq.items()},
                         # moslik (eski maydonlar — bevosita = o'ziga yozilgan hamma xarajat)
                         "bevosita": f(O[k] + X[k]), "jami_xarajat": f(O[k] + X[k]), "sof_foyda": f(N),
                         "bevosita_qismlari": dict({_YON_OYLIK: f(O[k])}, **{n: f(v) for n, v in xq.items()})}
        NJ = _yaxlit(sof, birlik)
        UJ = jn - NJ                                        # umumiy (yo'nalishsiz) oylik + xarajat, butun birlikda
        _uxr = sum(umumiy[n] for n in _YON_XARAJAT_QISMLARI)
        U = _yaxlit_taqsim({"oylik": umumiy[_YON_OYLIK], "xarajat": _uxr}, UJ, birlik)
        uq = _yaxlit_taqsim({n: umumiy[n] for n in _YON_XARAJAT_QISMLARI}, U["xarajat"], birlik)
        so = sum(O.values()) + U["oylik"]
        sx = sum(X.values()) + U["xarajat"]
        jami = {"daromad": f(sum(D.values())), "tannarx": f(sum(T.values())), "oylik": f(so), "xarajat": f(sx),
                "natija": f(NJ), "umumiy_oylik": f(U["oylik"]), "umumiy_xarajat": f(U["xarajat"]),
                "yonalishlar_oyligi": f(sum(O.values())), "yonalishlar_xarajati": f(sum(X.values())),
                "yonalishlar_natijasi": f(jn),
                "umumiy_qismlari": dict({_YON_OYLIK: f(U["oylik"])}, **{n: f(v) for n, v in uq.items()}),
                "xarajat_qismlari": {n: f(jq[n] + uq[n]) for n in _YON_XARAJAT_QISMLARI},
                "bevosita": f(sum(O.values()) + sum(X.values())), "jami_xarajat": f(so + sx), "sof_foyda": f(NJ),
                "bevosita_qismlari": dict({_YON_OYLIK: f(sum(O.values()))}, **{n: f(jq[n]) for n in _YON_XARAJAT_QISMLARI})}
        return natija, jami

    (som, jami_som), (tiyin, jami_tiyin) = _ustunlar(1), _ustunlar(100)
    yonalishlar = []
    for k in tartib:
        s_ = som[k]
        yonalishlar.append({
            "kalit": k, "nom": x.nom(k),
            "asosiy": k == x.asosiy_kalit,
            "belgilanmagan": k == _YON_BELGILANMAGAN,
            "yashirin": bool(x.nomlar[k].yashirin) if k in x.nomlar else False,
            "som": s_, "aniq": tiyin[k],
            "rentabellik": round(s_["natija"] / s_["daromad"] * 100, 1) if s_["daromad"] else None,
            "foyda_foiz": round(s_["natija"] / s_["daromad"] * 100, 1) if s_["daromad"] else 0.0,
        })
    # Xarajatlar tarkibi (doira): tannarxsiz — oyliklar va har xarajat turi (yo'nalishniki + umumiy)
    _tarkib = [(_YON_OYLIK, "Hodimlar oyligi", jami_som["oylik"])] + [
        (n, dict(_YON_XARAJAT_NOMLARI)[n], jami_som["xarajat_qismlari"][n]) for n in _YON_XARAJAT_QISMLARI]
    _musbat = sum(v for _k, _n, v in _tarkib if v > 0)
    tarkib = [{"kalit": k, "nom": nm, "summa": v, "foiz": round(v / _musbat * 100, 1) if _musbat and v > 0 else 0.0}
              for k, nm, v in _tarkib if v != 0]
    tarkib.sort(key=lambda r: -r["summa"])
    # «Belgilanmagan» — qaysi MRP turlari biriktirilmagan (egasiga ko'rsatiladi)
    belgilanmagan_turlar = []
    if _YON_BELGILANMAGAN in tartib:
        from production_models import ProductType as _PT117b
        _pq = db.query(_PT117b.name).filter(_PT117b.yonalish_id.is_(None), _PT117b.is_active == True)  # noqa: E712
        if company_id is not None:
            _pq = _pq.filter(_PT117b.company_id == company_id)
        belgilanmagan_turlar = sorted(r[0] for r in _pq.all())
    _y_ustun = [y for y in yonalishlar if not y["belgilanmagan"] and (y["som"]["daromad"] or y["som"]["natija"])]
    natija = {
        "year": year, "month": month,
        "davr": {"dan": f"{oylar[0][0]}-{oylar[0][1]:02d}", "gacha": f"{oylar[-1][0]}-{oylar[-1][1]:02d}",
                 "oylar": len(oylar), "nom": yonalish_davr_nomi(oylar)},
        "yonalishlar": yonalishlar,
        "jami": jami_som,
        "jami_aniq": jami_tiyin,
        "rentabellik": round(jami_som["natija"] / jami_som["daromad"] * 100, 1) if jami_som["daromad"] else None,
        "foydada_soni": sum(1 for y in _y_ustun if y["som"]["natija"] > 0),
        "zararda_soni": sum(1 for y in _y_ustun if y["som"]["natija"] < 0),
        "moliya_sof_foyda": _yaxlit(sof, 1),
        "moliya_sof_foyda_aniq": _yaxlit(sof, 100) / 100,
        "moliya_daromad": _yaxlit(float(t_jami.get("daromad_buyurtmalar", 0)) + float(t_jami.get("daromad_tm", 0)), 1),
        "umumiy_xarajatlar": {n: round(umumiy[n], 2) for n, _x in _YON_XARAJAT_NOMLARI},
        "xarajat_nomlari": dict(_YON_XARAJAT_NOMLARI),
        "xarajat_qism_nomlari": {n: dict(_YON_XARAJAT_NOMLARI)[n] for n in _YON_XARAJAT_QISMLARI},
        "tarkib": tarkib,
        "korinadigan_soni": len(x.korinadigan()),
        "belgilanmagan_turlar": belgilanmagan_turlar,
        # «Belgilanmagan» ustunidagi daromadning MRP turidan boshqa manbalari (eng kattasi birinchi, ko'pi bilan 10 ta)
        "belgilanmagan_manbalar": ([{"nom": n, "summa": round(v, 2)} for n, v in
                                    sorted(belg_manbalar.items(), key=lambda q: -abs(q[1]))[:10]]
                                   if _YON_BELGILANMAGAN in tartib else []),
        "izohlar": izohlar,
        "tekshiruv_farq": round(tekshiruv_farq, 6),
    }
    if solishtirish:
        _old = yonalish_oldingi_davr(oylar)
        # kech119 (egasi QARORI «Shu kunlar bilan» — Hisobotlar solishtirishi bilan BIR qoida): davr JORIY (tugamagan)
        # oy bilan tugasa — solishtirish davrining oxirgi oyi ham o'sha kunlargacha (1–N), aks holda butun oylar.
        import calendar as _calendar_yk
        from database import tashkent_oy_kesimi as _tashkent_oy_kesimi_yk
        _bugun_yk = _tashkent_date()
        _kesim_yk = None
        if (tuple(oylar[-1]) == (_bugun_yk.year, _bugun_yk.month)
                and _bugun_yk.day < _calendar_yk.monthrange(_old[-1][0], _old[-1][1])[1]):
            _kesim_yk = _bugun_yk.day
        if _kesim_yk is None:
            _oj = _yon_davr_jami(db, _old, company_id=company_id)
            _old_nom = yonalish_davr_nomi(_old)
        else:
            with _tashkent_oy_kesimi_yk(_old[-1][0], _old[-1][1], _kesim_yk):
                _oj = _yon_davr_jami(db, _old, company_id=company_id)
            _oy_k = _OY_KICHIK[_old[-1][1] - 1]
            _kunlar = "1" if _kesim_yk == 1 else f"1–{_kesim_yk}"
            # «1–10-sentabr 2026» (bir oy) / «Iyul – Sentabr 2026 (sentabr — 1–10-kun)» (bir necha oy)
            _old_nom = (f"{_kunlar}-{_oy_k} {_old[-1][0]}" if len(_old) == 1
                        else f"{yonalish_davr_nomi(_old)} ({_oy_k} — {_kunlar}-kun)")
        _jx = jami_som["tannarx"] + jami_som["oylik"] + jami_som["xarajat"]
        natija["oldingi"] = dict(_oj, davr={"dan": f"{_old[0][0]}-{_old[0][1]:02d}",
                                            "gacha": f"{_old[-1][0]}-{_old[-1][1]:02d}", "nom": _old_nom,
                                            "kun_gacha": _kesim_yk})
        natija["ozgarish"] = {"daromad": _ozgarish_foiz(jami_som["daromad"], _oj["daromad"]),
                              "xarajat": _ozgarish_foiz(_jx, _oj["xarajat"]),
                              "natija": _ozgarish_foiz(jami_som["natija"], _oj["natija"])}
    return natija


def _kassa_qismlari(db: Session, company_id: int = None, boshi=None, oxiri=None) -> dict:
    """kech116 (G1-03 — egasi QARORI kech114 «Pul oqimi — haqiqiy pul»): kassa harakatlarining qismlari — YAGONA manba.
    Kassa balansi (`get_cash_balance` — butun davr) va «Pul oqimi» (`get_pul_oqimi` — oy / kun) shu funksiyadan, shuning
    uchun bir kassa qoidasi: har kunning pul oqimi yig'indisi + boshlang'ich balans = kassa balansi.

    `boshi` / `oxiri` — UTC (naive) davr `[boshi, oxiri)` (Toshkent kun / oy chegaralari — `database.tashkent_*_oraligi`);
    ikkalasi `None` — butun davr (kassa). Har qism o'z sanasi bo'yicha: mijoz to'lovi `paid_at` (qaytarilgan pul — manfiy
    to'lov — ayriladi), tayyor mahsulot sotuvi `sold_at`, naqd xarid `purchased_at` (nasiya va boshlang'ich ombor — yo'q,
    nasiya to'lanishi — ta'minotchiga to'lov), ta'minotchiga to'lov `paid_at`, xarajat `date`, kirish transporti
    `expense_date`, yetkazishning korxona ulushi `delivered_at`, hodimga avans / oylik (`EmployeeAdvance` — oylik qarzini
    yopish ham shu yozuv) `date`, kassaga qo'lda yozuv `created_at`. Eski oylik shakl (`MonthlyExpense` — shu oy / turkum
    uchun tranzaksiya bo'lmasa) — oyning 1-kuniga (Toshkent) tegishli. Faqat o'qiydi."""
    from models import (Payment, InventoryPurchase, SupplierPayment, MonthlyExpense,
                         ExpenseTransaction, TransportExpense, EmployeeAdvance, CashTransaction,
                         FinishedProductSale)
    from sqlalchemy import func

    # M6 (2026-09-18) — TENANT: kassaning HAR BIR yig'indisi joriy korxona
    # bilan cheklanadi. `Payment`/`SupplierPayment`/`InventoryPurchase`da
    # company_id ustuni yo'q — ular ota (Order/Supplier/Inventory) orqali
    # cheklanadi; qolganlarida ustunning o'zi bor.
    from models import Order as _Ord_cash, Supplier as _Sup_cash, Inventory as _Inv_cash

    def _davr(q, ustun):
        """kech116: davr sharti (butun davr — shartsiz)."""
        if boshi is not None:
            q = q.filter(ustun >= boshi)
        if oxiri is not None:
            q = q.filter(ustun < oxiri)
        return q

    _pq = db.query(func.sum(Payment.amount))
    if company_id is not None:
        _pq = _pq.join(_Ord_cash, _Ord_cash.id == Payment.order_id).filter(
            _Ord_cash.company_id == company_id)
    kirim_tolov = float(_davr(_pq, Payment.paid_at).scalar() or 0)

    # MUHIM: Tayyor mahsulotni to'g'ridan-to'g'ri (buyurtmasiz) sotishdan
    # kelgan pul ham kassa KIRIMI — avval bu umuman hisobga olinmasdi,
    # shuning uchun sotuvdan tushgan pul Moliyada ko'rinmasdi.
    _fsq = db.query(func.sum(FinishedProductSale.total_amount))
    if company_id is not None:
        _fsq = _fsq.filter(FinishedProductSale.company_id == company_id)
    kirim_tayyor_sotuv = float(_davr(_fsq, FinishedProductSale.sold_at).scalar() or 0)

    _ipq = db.query(func.sum(InventoryPurchase.total_amount)).filter(
        InventoryPurchase.is_credit == False,
        InventoryPurchase.is_opening_stock.isnot(True)
    )
    if company_id is not None:
        _ipq = _ipq.join(_Inv_cash, _Inv_cash.id == InventoryPurchase.inventory_id).filter(
            _Inv_cash.company_id == company_id)
    chiqim_xomashyo_naqd = float(_davr(_ipq, InventoryPurchase.purchased_at).scalar() or 0)

    _spq = db.query(func.sum(SupplierPayment.amount))
    if company_id is not None:
        _spq = _spq.join(_Sup_cash, _Sup_cash.id == SupplierPayment.supplier_id).filter(
            _Sup_cash.company_id == company_id)
    chiqim_yetkazib_beruvchi = float(_davr(_spq, SupplierPayment.paid_at).scalar() or 0)

    _meq = db.query(MonthlyExpense)
    if company_id is not None:
        _meq = _meq.filter(MonthlyExpense.company_id == company_id)
    me_rows = _meq.all()
    # kech88 (108-band, O'LCHANGAN — probe105b C7): eski oylik forma (`save_monthly_expense`) arenda / elektr /
    # tushlik / soliqni IKKI joyga yozadi — `MonthlyExpense` qatori VA `monthly_form` manbali `ExpenseTransaction`.
    # Kassa ikkalasini ham ayirardi (1 000 so'mlik arenda → −2 000). Endi oylik hisobot qoidasi
    # (`_monthly_category_amount`) bilan bir xil: shu oy / kategoriya uchun BIRORTA tranzaksiya bo'lsa — faqat
    # tranzaksiyalar (ular pastdagi `chiqim_qoshimcha` da), bo'lmasa — `MonthlyExpense` qiymati (eski oy, C8).
    _OYLIK_KAT = ("arenda", "elektr", "tushlik", "soliqlar")
    _mtq = db.query(ExpenseTransaction.date, ExpenseTransaction.category
                    ).filter(ExpenseTransaction.category.in_(_OYLIK_KAT))
    if company_id is not None:
        _mtq = _mtq.filter(ExpenseTransaction.company_id == company_id)
    # kech105 (9 + 50-band): tranzaksiya oyi — TOSHKENT kalendari (oylik hisobot `_monthly_category_amount` bilan bir
    # qoida; ilgari SQL `extract` — UTC oyi).
    _tranzaksiyali = {(_tashkent_date(d).year, _tashkent_date(d).month, cat)
                      for d, cat in _mtq.distinct().all() if d is not None}

    def _oy_davrda(m):
        """kech116: eski oylik shakl qatori — oyning 1-kuni (Toshkent) davrdami (butun davr — har doim)."""
        if boshi is None and oxiri is None:
            return True
        try:
            _b, _ = _tashkent_oy_oraligi(int(m.year), int(m.month))
        except Exception:
            return False
        return (boshi is None or _b >= boshi) and (oxiri is None or _b < oxiri)

    chiqim_oylik = sum(
        float(getattr(m, cat) or 0)
        for m in me_rows if _oy_davrda(m) for cat in _OYLIK_KAT
        if (int(m.year), int(m.month), cat) not in _tranzaksiyali
    )
    _etq = db.query(func.sum(ExpenseTransaction.amount))
    if company_id is not None:
        _etq = _etq.filter(ExpenseTransaction.company_id == company_id)
    chiqim_qoshimcha = float(_davr(_etq, ExpenseTransaction.date).scalar() or 0)

    _teq = db.query(func.sum(TransportExpense.amount))
    if company_id is not None:
        _teq = _teq.filter(TransportExpense.company_id == company_id)
    chiqim_transport = float(_davr(_teq, TransportExpense.expense_date).scalar() or 0)

    # kech88 (107-band, O'LCHANGAN — probe105b C4 / C5; 104-band QARORI: korxona to'lagan yetkazish transporti —
    # xarajat): mijozga yuk yetkazishda korxona to'lagan qism ("company" — to'liq, "split" — yarmi,
    # `Delivery.company_transport_cost` — oylik hisobot bilan AYNAN bir qoida) kassadan chiqib ketgan pul. Ilgari
    # kassada umuman YO'Q edi (sinovda 625 000 so'm). Yuk xati o'chirilsa — yozuv yo'qoladi, pul qaytadi.
    from models import Delivery as _Dlv_cash
    _dvq = db.query(_Dlv_cash).filter(_Dlv_cash.transport_cost > 0)
    if company_id is not None:      # M6: ota (buyurtma) orqali
        _dvq = _dvq.join(_Ord_cash, _Ord_cash.id == _Dlv_cash.order_id).filter(
            _Ord_cash.company_id == company_id)
    chiqim_yetkazish_transport = float(sum(float(d.company_transport_cost or 0)
                                           for d in _davr(_dvq, _Dlv_cash.delivered_at).all()))
    # M5 — avans yig'indisi: `EmployeeAdvance`da company_id ustuni yo'q,
    # tenant otasi (Employee) orqali cheklanadi.
    _avq = db.query(func.sum(EmployeeAdvance.amount))
    if company_id is not None:
        from models import Employee as _Emp_cash
        _avq = _avq.join(_Emp_cash, _Emp_cash.id == EmployeeAdvance.employee_id
                         ).filter(_Emp_cash.company_id == company_id)
    chiqim_avans = float(_davr(_avq, EmployeeAdvance.date).scalar() or 0)

    _ctq = db.query(func.sum(CashTransaction.amount))
    if company_id is not None:
        _ctq = _ctq.filter(CashTransaction.company_id == company_id)
    qolda_jami = float(_davr(_ctq, CashTransaction.created_at).scalar() or 0)
    # kech116: boshlang'ich balans — pul HARAKATI emas (tizimga kirishdagi qoldiq); pul oqimi uni olmaydi
    _cbq = db.query(func.sum(CashTransaction.amount)).filter(CashTransaction.category == "boshlangich")
    if company_id is not None:
        _cbq = _cbq.filter(CashTransaction.company_id == company_id)
    qolda_boshlangich = float(_davr(_cbq, CashTransaction.created_at).scalar() or 0)

    return {
        "kirim_tolov": kirim_tolov,
        "kirim_tayyor_sotuv": kirim_tayyor_sotuv,
        "chiqim_xomashyo_naqd": chiqim_xomashyo_naqd,
        "chiqim_yetkazib_beruvchi": chiqim_yetkazib_beruvchi,
        "chiqim_oylik": chiqim_oylik,
        "chiqim_qoshimcha": chiqim_qoshimcha,
        "chiqim_transport": chiqim_transport,
        "chiqim_yetkazish_transport": chiqim_yetkazish_transport,
        "chiqim_avans": chiqim_avans,
        "qolda_jami": qolda_jami,
        "qolda_boshlangich": qolda_boshlangich,
    }


def get_cash_balance(db: Session, company_id: int = None) -> dict:
    """Kassa + bank balansi — kompaniyada HOZIR haqiqatda qancha pul bor (naqd, karta va bank o'tkazmasi — hammasi bitta;
    kech118 D-1, G3-14 — egasi QARORI «Bitta: Kassa + bank»).

    ➕ Kirim: mijozlardan kelgan barcha to'lovlar
    ➖ Chiqim: naqd to'langan xomashyo xaridi, yetkazib beruvchiga to'lovlar,
       oylik xarajatlar, transport, xodim avanslari
    ➕/➖ Qo'lda: boshlang'ich balans, "Usta KPI to'landi", "Ehson to'landi"
       (bular — FAQAT admin aniq belgilaganda hisoblanadi, oy oxirida
       o'zi avtomatik chiqib ketmaydi).

    kech116 (G1-03): qismlar — `_kassa_qismlari` (butun davr); «Pul oqimi» (`get_pul_oqimi`) ham AYNAN shu qismlardan
    (davr bilan) — natija o'zgarmadi."""
    q = _kassa_qismlari(db, company_id=company_id)
    # kech118 (D-1, G3-14 — egasi QARORI «Bitta: Kassa + bank»): boshlang'ich balans kiritilganmi — kiritilmagan bo'lsa
    # Moliya kartasi ogohlantiradi (tizimdan oldingi pul hisobda yo'q — summa manfiy chiqishi shundan) va tugma ko'rsatadi
    from models import CashTransaction as _CT_bosh
    from sqlalchemy import func as _f_bosh
    _bq = db.query(_f_bosh.count(_CT_bosh.id)).filter(_CT_bosh.category == "boshlangich")
    if company_id is not None:
        _bq = _bq.filter(_CT_bosh.company_id == company_id)
    boshlangich_kiritilgan = (_bq.scalar() or 0) > 0
    kirim_tolov = q["kirim_tolov"]
    kirim_tayyor_sotuv = q["kirim_tayyor_sotuv"]
    chiqim_xomashyo_naqd = q["chiqim_xomashyo_naqd"]
    chiqim_yetkazib_beruvchi = q["chiqim_yetkazib_beruvchi"]
    chiqim_oylik = q["chiqim_oylik"]
    chiqim_qoshimcha = q["chiqim_qoshimcha"]
    chiqim_transport = q["chiqim_transport"]
    chiqim_yetkazish_transport = q["chiqim_yetkazish_transport"]
    chiqim_avans = q["chiqim_avans"]
    qolda_jami = q["qolda_jami"]

    jami_kirim = kirim_tolov + kirim_tayyor_sotuv
    jami_chiqim = (chiqim_xomashyo_naqd + chiqim_yetkazib_beruvchi + chiqim_oylik +
                   chiqim_qoshimcha + chiqim_transport + chiqim_avans +
                   chiqim_yetkazish_transport)

    balance = jami_kirim - jami_chiqim + qolda_jami

    return {
        "balance": round(balance),
        "kirim_tolov": round(kirim_tolov),
        "kirim_tayyor_sotuv": round(kirim_tayyor_sotuv),
        "chiqim_xomashyo_naqd": round(chiqim_xomashyo_naqd),
        "chiqim_yetkazib_beruvchi": round(chiqim_yetkazib_beruvchi),
        "chiqim_oylik": round(chiqim_oylik),
        "chiqim_qoshimcha": round(chiqim_qoshimcha),
        "chiqim_transport": round(chiqim_transport),
        "chiqim_yetkazish_transport": round(chiqim_yetkazish_transport),
        "chiqim_avans": round(chiqim_avans),
        "qolda_jami": round(qolda_jami),
        "boshlangich_kiritilgan": boshlangich_kiritilgan,
    }


def _pul_oqimi_oraliq(db: Session, boshi, oxiri, company_id: int = None) -> dict:
    """kech116 (G1-03): `[boshi, oxiri)` (UTC, naive) davrdagi HAQIQIY pul harakati — `_kassa_qismlari` dan (kassa bilan
    BITTA qoida). Kirim — mijozlardan olingan to'lovlar (qaytarilgan pul ayrilgan) + tayyor mahsulot sotuvi; chiqim —
    naqd xarid, ta'minotchiga to'lov, hodimlarga (avans / oylik), xarajatlar, transport, yetkazishning korxona ulushi,
    kassadan qo'lda to'langan (Usta KPI, Ehson). Boshlang'ich balans — harakat emas (kirmaydi). Qiymatlar — tiyin."""
    from models import pul_tiyin, pul_tiyin_yigindi
    q = _kassa_qismlari(db, company_id=company_id, boshi=boshi, oxiri=oxiri)
    _pt = pul_tiyin
    qolda_chiqim = _pt(-(q["qolda_jami"] - q["qolda_boshlangich"]))     # "Usta KPI / Ehson to'landi" — manfiy yozuvlar
    kirim_qatorlar = [
        {"kalit": "mijoz_tolovlari", "nom": "Mijozlardan to'lovlar", "summa": _pt(q["kirim_tolov"])},
        {"kalit": "tayyor_sotuv", "nom": "Tayyor mahsulot sotuvi", "summa": _pt(q["kirim_tayyor_sotuv"])},
    ]
    chiqim_qatorlar = [
        {"kalit": "xomashyo_naqd", "nom": "Xomashyo xaridi (naqd)", "summa": _pt(q["chiqim_xomashyo_naqd"])},
        {"kalit": "taminotchiga", "nom": "Ta'minotchilarga to'lov", "summa": _pt(q["chiqim_yetkazib_beruvchi"])},
        {"kalit": "hodimlarga", "nom": "Hodimlarga (avans / oylik)", "summa": _pt(q["chiqim_avans"])},
        {"kalit": "xarajatlar", "nom": "Xarajatlar (arenda, elektr, boshqa)",
         "summa": _pt(q["chiqim_qoshimcha"] + q["chiqim_oylik"])},
        {"kalit": "transport", "nom": "Transport (kirish)", "summa": _pt(q["chiqim_transport"])},
        {"kalit": "yetkazish_transport", "nom": "Yetkazish transporti (korxona ulushi)",
         "summa": _pt(q["chiqim_yetkazish_transport"])},
        {"kalit": "kassadan_qolda", "nom": "Kassadan to'langan (Usta KPI, Ehson)", "summa": qolda_chiqim},
    ]
    kirim = pul_tiyin_yigindi(x["summa"] for x in kirim_qatorlar)
    chiqim = pul_tiyin_yigindi(x["summa"] for x in chiqim_qatorlar)
    return {
        "kirim": kirim, "chiqim": chiqim, "balans": pul_tiyin(kirim - chiqim),
        "kirim_qatorlar": kirim_qatorlar, "chiqim_qatorlar": chiqim_qatorlar,
        "harakat_bor": any(abs(x["summa"]) >= 0.01 for x in kirim_qatorlar + chiqim_qatorlar),
    }


def get_pul_oqimi(db: Session, year: int = None, month: int = None, sana=None, company_id: int = None) -> dict:
    """kech116 (G1-03 — egasi QARORI kech114 «Pul oqimi — haqiqiy pul», O'LCHANGAN audit: Hisobotlar kartasi «Pul oqimi»
    = daromad − jami xarajat (−1.6 mln), Dashboard «Pul oqimi (bu oy)» = daromad − (xarajat + naqd xarid − transport)
    (−26.8 mln), Moliya «Pul oqimi» = bugungi savdo − xarajat; hech biri mijoz haqiqatda to'lagan pul emas — Katta
    korxonada 13.4 mln tushgan kuni Hisobotlar «0 so'm, Yaxshi» derdi). YAGONA «Pul oqimi»: Toshkent oyi (`year`,
    `month`) yoki kuni (`sana` — `date`) uchun `_pul_oqimi_oraliq`; uchala sahifa va «Korxona sog'ligi» shundan."""
    if sana is not None:
        boshi, oxiri = _tashkent_kun_oraligi(sana)
        davr = {"tur": "kun", "sana": sana.isoformat()}
    else:
        boshi, oxiri = _tashkent_oy_oraligi(year, month)
        davr = {"tur": "oy", "year": int(year), "month": int(month)}
    natija = _pul_oqimi_oraliq(db, boshi, oxiri, company_id=company_id)
    natija["davr"] = davr
    return natija


def get_purchase_stats_for_period(db: Session, year: int, month: int,
                                 company_id: int = None) -> dict:
    """Berilgan oy uchun xomashyo xaridi statistikasi.
    MUHIM: "boshlang'ich (mavjud) ombor" sifatida belgilangan kirimlar
    bu yerga KIRMAYDI — chunki ular yangi xarid emas, tizimni ishlata
    boshlaganda mavjud xomashyoni hisobga olish uchun (bir martalik
    kiritish). Aks holda, "shu oy xarajati" noto'g'ri, shishirilgan
    chiqib qolar edi."""
    from models import InventoryPurchase, Inventory as _Inv_ps

    start, end = _tashkent_oy_oraligi(year, month)

    # M6 — TENANT: `InventoryPurchase`da company_id yo'q, ota (material) orqali.
    _pq = db.query(InventoryPurchase).filter(
        InventoryPurchase.purchased_at >= start,
        InventoryPurchase.purchased_at < end,
        InventoryPurchase.is_opening_stock.isnot(True)
    )
    if company_id is not None:
        _pq = _pq.join(_Inv_ps, _Inv_ps.id == InventoryPurchase.inventory_id).filter(
            _Inv_ps.company_id == company_id)
    purchases = _pq.all()

    by_material = {}
    total = 0.0
    for p in purchases:
        key = p.item_name
        if key not in by_material:
            by_material[key] = {"name": key, "quantity": 0.0, "total": 0.0, "unit": p.unit}
        by_material[key]["quantity"] += float(p.quantity)
        by_material[key]["total"] += float(p.total_amount)
        total += float(p.total_amount)

    items = sorted(by_material.values(), key=lambda x: x["total"], reverse=True)
    for it in items:
        it["total"] = round(it["total"])

    return {"total_amount": round(total), "by_material": items}


def get_transport_stats_for_period(db: Session, year: int, month: int,
                                  company_id: int = None) -> dict:
    """Berilgan oy uchun transport xarajatlari."""
    from models import TransportExpense, Delivery, Order as _Ord_tp

    start, end = _tashkent_oy_oraligi(year, month)

    _iq = db.query(TransportExpense).filter(
        TransportExpense.expense_date >= start,
        TransportExpense.expense_date < end
    )
    if company_id is not None:      # M6
        _iq = _iq.filter(TransportExpense.company_id == company_id)
    inbound = _iq.all()
    inbound_total = sum(float(e.amount) for e in inbound)

    _dq = db.query(Delivery).filter(
        Delivery.delivered_at >= start,
        Delivery.delivered_at < end,
        Delivery.transport_cost > 0
    )
    if company_id is not None:      # M6: ota (buyurtma) orqali
        _dq = _dq.join(_Ord_tp, _Ord_tp.id == Delivery.order_id).filter(
            _Ord_tp.company_id == company_id)
    deliveries = _dq.all()
    outbound_company = sum(d.company_transport_cost for d in deliveries)

    return {
        "inbound_total": round(inbound_total),
        "outbound_company": round(outbound_company),
        # kech87 (104-band): sof foyda uchun — YAXLITLANMAGAN (tiyingacha aniq)
        "inbound_aniq": float(inbound_total),
        "outbound_company_aniq": float(outbound_company),
    }


def save_monthly_expense(db: Session, year: int, month: int, data: dict,
                        performed_by: Optional[str] = None, company_id: int = None):
    """Oylik xarajatlarni saqlaydi yoki yangilaydi.

    O'ZGARMAGAN: MonthlyExpense jadvaliga yozish — bu hech qanday o'zgarishsiz,
    avvalgi holatidek ishlaydi (backward compatibility).

    YANGI (qo'shimcha): shu bilan bir vaqtda 4 ta asosiy kategoriya
    (arenda/elektr/tushlik/soliqlar) uchun ExpenseTransaction yozuvlari ham
    sinxronlanadi — bu get_monthly_report() endi shu tranzaksiyalardan
    hisoblashi uchun kerak. Faqat 'monthly_form' manbali eski tranzaksiyalar
    almashtiriladi — qo'lda kiritilgan tranzaksiyalarga tegilmaydi.
    """
    from models import MonthlyExpense, ExpenseTransaction
    from datetime import datetime as _datetime

    # M6 (2026-09-18) — TENANT: qator (year, month) bo'yicha GLOBAL
    # qidirilardi. Ikki korxonali bazada bu — o'qish sizishi emas,
    # MA'LUMOT BUZILISHI edi: A "Saqlash" bosganda B korxonaning
    # arenda/elektr/soliq qatorini o'chirib yozib yuborardi (lokal
    # sinovda aniq ko'rsatilgan). Endi qidiruv ham, yangi qator ham
    # korxona bilan bog'langan.
    _meq = db.query(MonthlyExpense).filter(
        MonthlyExpense.year  == year,
        MonthlyExpense.month == month
    )
    if company_id is not None:
        _meq = _meq.filter(MonthlyExpense.company_id == company_id)
    expense = _meq.first()

    if not expense:
        expense = MonthlyExpense(company_id=company_id, year=year, month=month)
        db.add(expense)

    expense.arenda   = data.get("arenda", 0)
    expense.elektr   = data.get("elektr", 0)
    expense.tushlik  = data.get("tushlik", 0)
    expense.soliqlar = data.get("soliqlar", 0)
    expense.hodim1_ism    = data.get("hodim1_ism", "Hodim 1")
    expense.hodim1_oylik  = data.get("hodim1_oylik", 0)
    expense.hodim2_ism    = data.get("hodim2_ism", "Hodim 2")
    expense.hodim2_oylik  = data.get("hodim2_oylik", 0)
    expense.hodim3_ism    = data.get("hodim3_ism", "Hodim 3")
    expense.hodim3_oylik  = data.get("hodim3_oylik", 0)
    expense.qoplamachi_ism    = data.get("qoplamachi_ism", "Qoplamachi")
    expense.qoplamachi_oylik  = data.get("qoplamachi_oylik", 0)
    expense.qoplamachi_bonus  = data.get("qoplamachi_bonus", 0)
    expense.notes = data.get("notes", "")

    db.commit()
    db.refresh(expense)

    # ── YANGI: ExpenseTransaction sinxronlash (xato bo'lsa ham asosiy saqlashga ta'sir qilmasin) ──
    try:
        tx_date = _datetime(year, month, 1)
        for cat in ("arenda", "elektr", "tushlik", "soliqlar"):
            amount = data.get(cat, 0) or 0
            # Avvalgi 'monthly_form' manbali tranzaksiyani o'chirib, yangisini yozamiz
            # M6 — TENANT: bu yerdagi O'CHIRISH ham, YARATISH ham korxona
            # bilan bog'lanadi. Aks holda A "Saqlash" bosganda B ning
            # 'monthly_form' tranzaksiyalari o'chib ketardi, yangisi esa
            # DEFAULT 1 ga yozilardi.
            _delq = db.query(ExpenseTransaction).filter(
                _tashkent_oyida(ExpenseTransaction.date, year, month),
                ExpenseTransaction.category == cat,
                ExpenseTransaction.source == "monthly_form"
            )
            if company_id is not None:
                _delq = _delq.filter(ExpenseTransaction.company_id == company_id)
            _delq.delete(synchronize_session=False)
            if amount > 0:
                db.add(ExpenseTransaction(
                    company_id=company_id,
                    date=tx_date, category=cat, amount=amount,
                    notes=data.get("notes") or None,
                    created_by=performed_by, source="monthly_form"
                ))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"⚠️ ExpenseTransaction sinxronlashda xato (asosiy saqlash bajarildi): {e}")

    return expense


# ============================================================
# BUYURTMA SAQLASHDA OMBOR TEKSHIRUVI VA AYIRISH
# ============================================================
def get_penoplast_list(db: Session, company_id: int = None):
    """Korxonaning penoplast (plotnost) turlari.

    2026-09-21 — TENANT (O'LCHANGAN): filtr umuman yo'q edi — B korxona
    `/api/penoplasts`, `/orders`, `/finished` da A ning penoplastlarini
    (nomi, qoldig'i, narxi) ko'rardi. Korxona noma'lum bo'lsa — bo'sh
    ro'yxat (begona ro'yxatdan xavfsizroq)."""
    from models import Inventory
    from sqlalchemy import or_, and_
    if company_id is None:
        return []
    try:
        # kech105 (K105-3, O'LCHANGAN — work/probe105.py): nom bo'yicha FAQAT belgisi NOMA'LUM (NULL) eski
        # qatorlar. Ilgari nomida "penoplast" bo'lgan HAR material (masalan ataylab `is_penoplast=false`
        # yaratilgan "Penoplast kleyi" — Kimyoviy qo'shimcha) buyurtma / tayyor mahsulot oynasidagi plotnost
        # tanlovida chiqardi. ANIQ "penoplast emas" (false) material — hech qachon plotnost emas.
        items = db.query(Inventory).filter(
            Inventory.company_id == company_id,
            or_(
                Inventory.is_penoplast == True,
                and_(Inventory.is_penoplast.is_(None), Inventory.item_name.ilike("%penoplast%"))
            ),
            Inventory.is_deleted.isnot(True)
        ).order_by(Inventory.item_name).all()
        return items
    except Exception:
        db.rollback()
        return db.query(Inventory).filter(
            Inventory.company_id == company_id,
            Inventory.item_name.ilike("%penoplast%")
        ).all()


def get_default_penoplast(db: Session, company_id: int = None):
    """Asosiy plotnost.

    M6 — TENANT: company_id berilsa, standart penoplast FAQAT shu
    korxona omboridan tanlanadi (aks holda A ning hisobida B ning
    materiali ishlatilib qolishi mumkin edi)."""
    from models import Inventory

    # 2026-09-21 — O'LCHANGAN: 6 ta chaqiruvchi `company_id` bermasdi va
    # bu yerda butun bazadagi BIRINCHI asosiy penoplast qaytardi — ya'ni
    # odatda A niki. B ning penoplast tanlanmagan buyurtmasi A ning
    # penoplastiga bog'lanib, 409 bilan rad etilardi (filtr o'chiq). Endi
    # (loy retsepti bilan bir xil qoida) korxona noma'lum bo'lsa zaxira yo'li
    # UMUMAN ishlamaydi: penoplastsiz qolish begona penoplastdan xavfsizroq.
    if company_id is None:
        return None

    def _scoped(q):
        return q.filter(Inventory.company_id == company_id)

    p = _scoped(db.query(Inventory).filter(
        Inventory.is_penoplast == True,
        Inventory.is_default_penoplast == True,
        Inventory.is_deleted.isnot(True)
    )).first()
    if p:
        return p
    # kech37 (18-band): zaxira tanlovi BARQAROR — eng kichik id (15-band saboqi:
    # PG da tartibsiz `.first()` UPDATE dan keyin boshqa qatorni qaytarishi mumkin)
    p = _scoped(db.query(Inventory).filter(
        Inventory.is_penoplast == True, Inventory.is_deleted.isnot(True))).order_by(Inventory.id).first()
    if p:
        return p
    # kech105 (K105-3): nom bo'yicha zaxira FAQAT belgisi NOMA'LUM (NULL) eski qatorlar — ANIQ
    # `is_penoplast = false` material ("Penoplast kleyi") asosiy plotnost bo'lmaydi; tartib barqaror (id).
    return _scoped(db.query(Inventory).filter(
        Inventory.is_penoplast.is_(None),
        Inventory.item_name.ilike("%penoplast%"), Inventory.is_deleted.isnot(True)
    )).order_by(Inventory.id).first()


def _sub_detail_field(sub, name, default=None):
    """OrderItemSubDetail ORM obyekti yoki dict — ikkalasidan ham bir xil
    tarzda maydon o'qish uchun kichik yordamchi."""
    if isinstance(sub, dict):
        return sub.get(name, default)
    return getattr(sub, name, default)


def _calc_dim_volume_price(category, width, thickness, length, quantity, base_price, is_coated=False):
    """Profil/Panel formulasi bilan hajm (m³) va narxni hisoblaydi.
    Frontend (orders.html calculateItem()) dagi FORMULA BILAN AYNAN BIR
    XIL bo'lishi SHART — aks holda hajm/narx serverda boshqacha chiqadi.
    Asosiy detal ham, ICHKI QO'SHIMCHA detal ham shu bitta formuladan
    foydalanadi (ikkalasi ham bir xil xomashyodan)."""
    cat = (category or '').lower()
    w = float(width or 0)
    t = float(thickness or 0)
    l = float(length or 0)
    q = float(quantity or 1)
    bp = float(base_price or 0)

    if cat == 'profil':
        eni_m, keng_m = w / 100, t / 100
        volume = (eni_m * keng_m * l) / 2
        per_meter = (eni_m * keng_m * bp) / 2
        price = per_meter * l
    elif cat == 'panel':
        eni_m, qalin_m = w / 100, t / 100
        volume = eni_m * qalin_m * q
        per_dona = eni_m * qalin_m * bp
        price = per_dona * q
    else:
        return 0.0, 0.0

    if is_coated:
        price *= 2

    return volume, price


def _sub_details_volume_m3(item) -> float:
    """Bitta OrderItemning ICHKI QO'SHIMCHA detallari (bor bo'lsa) —
    jami hajmini (m³) qaytaradi. Har biri O'Z turi (profil/panel)
    formulasi bilan, lekin PARENT bilan bir xil xomashyo hisobiga."""
    total = 0.0
    for sub in (getattr(item, 'sub_details', None) or []):
        vol, _ = _calc_dim_volume_price(
            _sub_detail_field(sub, 'category', 'profil'),
            _sub_detail_field(sub, 'width'),
            _sub_detail_field(sub, 'thickness'),
            _sub_detail_field(sub, 'length'),
            _sub_detail_field(sub, 'quantity'),
            base_price=0,  # bu yerda faqat HAJM kerak, narx emas
        )
        total += vol
    return total


def _item_volume_m3(db, item, default_penoplast=None, penoplast_narxi=None, company_id=None) -> float:
    """Bitta detalning hajmini (m³) hisoblaydi.

    Donali mahsulot uchun:
        hajm = (1 dona narxi ÷ 1 m³ sotuv narxi) × miqdor
    unit_price — QOPLAMASIZ narx (qoplama hajmga ta'sir qilmaydi).

    kech99 (112-band): detal penoplasti (dona — narx-nisbat zaxirasi, blok — 1 blok hajmi) FAQAT korxonadan
    (`_korxona_materiali`): `company_id` berilmasa — detalning O'Z korxonasi (ORM detali); soxta detal
    (`_FakeItem`, `_Tmp`) chaqiruvchisi korxonani beradi. Begona penoplast — hajm 0 (ombordan yechish ham uni
    o'tkazib yuboradi — `_peno_of`).
    """
    _cid_v = company_id if company_id is not None else getattr(item, 'company_id', None)

    # Tayyor mahsulotdan olingan — xomashyo hisoblanmaydi
    if getattr(item, 'finished_product_id', None):
        return 0.0

    cat = (item.category or '').lower()
    qty = float(item.quantity or 1)

    if cat == 'profil':
        vol = 0.0
        if item.width and item.thickness and item.length:
            vol = (item.width/100) * (item.thickness/100) / 2 * float(item.length)
        # Ichki qo'shimcha detallar (masalan karniz ichidagi rebristo
        # qism) — bor bo'lsa, hajmiga QO'SHILADI (bir xil xomashyodan,
        # shuning uchun ombordan yechishda ALOHIDA hisoblanmaydi).
        vol += _sub_details_volume_m3(item)
        return vol
    elif cat == 'panel':
        if item.width and item.thickness:
            return (item.width/100) * (item.thickness/100) * qty
    elif cat == 'dona':
        # YANGI (2026-08): agar Kenglik+Qalinlik+"metr ekvivalenti"
        # (length maydonida, "Blok" turkumidagi kabi) saqlangan bo'lsa —
        # PROFIL formulasidan foydalanamiz (aniq, "1 metrdan necha dona
        # chiqadi" asosida hisoblangan). Bu — eskidan MUSTAQIL, YANGI yo'l.
        if item.width and item.thickness and item.length:
            return (item.width/100) * (item.thickness/100) / 2 * float(item.length)

        # ESKI (orqaga moslik): narx-nisbat usuli — yangi maydonlar
        # bo'lmagan, eski yozuvlar uchun, o'zgarishsiz qoladi.
        # MUHIM: agar "qulflangan" (unit_price_for_volume) qiymat saqlangan
        # bo'lsa — o'shani ishlatamiz (sotuv narxi keyinroq o'zgargan bo'lsa
        # ham, haqiqiy hajm o'zgarmasligi uchun). Eski yozuvlarda bu maydon
        # bo'lmasa — orqaga moslik uchun unit_price'ning o'zidan olamiz.
        unit_price = float(getattr(item, 'unit_price_for_volume', None) or item.unit_price or 0)
        if unit_price <= 0:
            return 0.0

        # 1 m³ sotuv narxi — detalda saqlangan bo'lsa shuni olamiz
        price_m3 = float(getattr(item, 'price_per_m3', None) or 0)

        # QO'SHILDI 2026-09-20. Detalda o'z "1 m³ narxi" maydoni bo'sh bo'lsa,
        # brauzer hisoblashda buyurtmaning "Asosiy narx"idan foydalangan
        # (orders.html: `effM3 = m3price || base_price`), lekin uni detalga
        # SAQLAMAGAN. Shuning uchun bu yerda ham avval o'sha asosiy narxga
        # murojaat qilamiz. Aks holda pastdagi TAN narxga tushib ketardik va
        # hajm sotuv/tan nisbatiga shishib qolardi — bu "hajmni qulflab
        # narxni oshirish" holatida o'lcham maydonlari tozalangan bo'lsa
        # jonli o'lchovda 74.5% farq bergan edi.
        if price_m3 <= 0:
            _ord = getattr(item, 'order', None)
            _bp = getattr(_ord, 'base_price', None) if _ord is not None else None
            if _bp:
                price_m3 = float(_bp)

        # Bo'lmasa — buyurtmadagi boshqa detallardan, oxirida penoplast tan narxidan
        if price_m3 <= 0:
            pid = getattr(item, 'penoplast_id', None)
            # kech89 (52-band): hisobot keshi; kech99 (112-band): FAQAT korxonadan
            p = _korxona_materiali(db, pid, _cid_v) if pid else default_penoplast
            # kech48 (K47-1, 5-bo'lim 32-band): `penoplast_narxi` — foyda hisobi
            # (`calculate_order_profit`) shu buyurtmaning MUZLATILGAN 1 blok
            # narxini beradi. Bu zaxira yo'lda hajm = summa ÷ narx, tan narx esa
            # hajm × narx — ikkalasi BIR narxdan bo'lmasa (hajm joriy, narx
            # muzlatilgan) tan narx joriy narx bilan suzardi. Boshqa
            # chaqiruvchilar (ombordan yechish, tahrir farqi) bermaydi — xulq
            # o'zgarmaydi.
            _pn = penoplast_narxi if penoplast_narxi is not None else (p.price_per_unit if p else None)
            if p and _pn and p.volume_per_unit:
                # Tan narxi: blok narxi ÷ blok hajmi = 1 m³ tan narxi
                price_m3 = float(_pn) / float(p.volume_per_unit)

        if price_m3 <= 0:
            return 0.0

        return (unit_price / price_m3) * qty

    elif cat == 'blok':
        # Butun blok evaziga hisoblanadi. quantity = blokdan CHIQQAN metr (mijozga
        # ko'rsatiladigan), length = ISHLATILGAN blok soni (ombordan shuncha yechiladi).
        blok_soni = float(item.length or 0)
        pid = getattr(item, 'penoplast_id', None)
        # kech89 (52-band): hisobot keshi; kech99 (112-band): FAQAT korxonadan
        p = _korxona_materiali(db, pid, _cid_v) if pid else default_penoplast
        if p and p.volume_per_unit and blok_soni > 0:
            return blok_soni * float(p.volume_per_unit)

    return 0.0


def _peno_of(db, pid, company_id=None, lock=False):
    """Penoplast pozitsiyasi — FAQAT shu korxona omboridan (2026-09-21).

    `pid` detalning o'z havolasi yoki korxonaning asosiy penoplasti. Korxona
    ma'lum bo'lsa, so'rov unga cheklanadi: begona pozitsiya topilmaydi va
    hech qachon ayirilmaydi/qaytarilmaydi."""
    from models import Inventory
    if not pid:
        return None
    q = db.query(Inventory).filter(Inventory.id == pid)
    if company_id is not None:
        q = q.filter(Inventory.company_id == company_id)
    if lock:
        q = q.with_for_update()
    return q.first()


def _company_of_items(items):
    """Detallar ro'yxatidan korxona (ORM detallarida `company_id` bor)."""
    for it in items or []:
        cid = getattr(it, 'company_id', None)
        if cid:
            return cid
    return None


def _group_volumes_by_penoplast(db, items, company_id=None) -> dict:
    """Detallarni plotnost bo'yicha guruhlaydi.
    Qaytaradi: {penoplast_id: total_volume_m3}
    MUHIM: "Tayyor mahsulotdan" tanlangan detallar (finished_product_id
    bor) — BU YERGA QO'SHILMAYDI, chunki ularning xomashyosi ALLAQACHON,
    o'sha mahsulot birinchi marta ishlab chiqarilganda ayirilgan edi.
    Agar shu yerda ham hisoblasak — IKKI MARTA ayirilgan bo'lardi."""
    if company_id is None:
        company_id = _company_of_items(items)
    default_p = get_default_penoplast(db, company_id=company_id)
    default_id = default_p.id if default_p else None

    volumes = {}
    for item in items:
        if getattr(item, 'finished_product_id', None):
            continue
        vol = _item_volume_m3(db, item, default_p, company_id=company_id)   # kech99 (112-band)
        if vol <= 0:
            continue
        pid = getattr(item, 'penoplast_id', None) or default_id
        if not pid:
            continue
        volumes[pid] = volumes.get(pid, 0.0) + vol
    return volumes


def _sxema_detal_dict(it, base_price) -> dict:
    """126-band (kech96): sxema (pydantic) detalidan ombor hisobi uchun dict (`_FakeItem`) — asosiy narx bilan."""
    if isinstance(it, dict):
        d = dict(it)
    elif hasattr(it, 'model_dump'):
        d = it.model_dump()
    else:
        d = {k: getattr(it, k, None) for k in ('category', 'width', 'thickness', 'length', 'quantity', 'unit_price',
                                             'unit_price_for_volume', 'penoplast_id', 'price_per_m3',
                                             'finished_product_id', 'sub_details')}
    d['order_base_price'] = float(base_price) if base_price is not None else None
    return d


def check_inventory_for_order(db: Session, order_data, company_id: int = None) -> dict:
    """
    Buyurtma uchun xomashyo yetishini tekshiradi.
    Har detal o'z plotnostidan hisoblanadi.
    company_id — `order_data` sxema (OrderCreate) bo'lsa, unda korxona
    yo'q, shuning uchun chaqiruvchi aniq beradi; ORM buyurtmada o'zidan.
    """
    cid = company_id if company_id is not None else getattr(order_data, 'company_id', None)
    shortages = []
    # 126-band (kech96, O'LCHANGAN `work/probe126.py` D5): sxema detallarida (`OrderCreate`) `order` yo'q —
    # Donalik (eski usul) hajmi asosiy narx o'rniga penoplast tannarxidan hisoblanib, yetarli qoldiqda ham
    # "yetishmaydi" (409) ogohlantirishi chiqardi (qoldiq 0.5, kerak 0.34 → "kerak 0.7 blok"). Yechish
    # (`deduct_inventory_for_order` — OrderItem obyekti) bilan BIR qoida: asosiy narx snapshotga beriladi.
    _tek_items = order_data.items
    _tek_bp = getattr(order_data, 'base_price', None)
    if _tek_bp:
        _tek_items = [it if hasattr(it, 'order') else _FakeItem(_sxema_detal_dict(it, _tek_bp))
                      for it in (order_data.items or [])]
    volumes = _group_volumes_by_penoplast(db, _tek_items, company_id=cid)
    total_volume_m3 = sum(volumes.values())

    if not volumes:
        return {"enough": True, "shortages": [], "total_volume_m3": 0}

    for pid, vol in volumes.items():
        p = _peno_of(db, pid, cid)
        if not p:
            continue
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks_needed = vol / vol_per_unit
        if float(p.stock_quantity) < blocks_needed:
            shortages.append(
                f"{p.item_name}: kerak {blocks_needed:.1f} blok, "
                f"qoldi {float(p.stock_quantity):.1f} blok"
            )

    return {
        "enough": len(shortages) == 0,
        "shortages": shortages,
        "total_volume_m3": round(total_volume_m3, 3)
    }


def deduct_inventory_for_order(db: Session, order, commit: bool = True) -> list:
    """
    Buyurtma saqlangandan keyin ombordan xomashyo ayiradi.
    Har detal o'z plotnostidan ayiriladi.

    kech65 (K65-2): `commit=False` — oxirida faqat `flush`; chaqiruvchi qulf (101, buyurtma)
    ostida ishlasa (qoralamani jarayonga olish), oraliq `commit` qulfni muddatidan OLDIN
    bo'shatardi.
    """
    import crud as _crud_lm

    log = []
    cid = getattr(order, 'company_id', None)
    volumes = _group_volumes_by_penoplast(db, order.items, company_id=cid)

    for pid, vol in volumes.items():
        p = _peno_of(db, pid, cid, lock=True)
        if not p:
            continue
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks_needed = vol / vol_per_unit
        # MUHIM: 0 ga cheklamaymiz — agar admin "yetishmasa ham davom et"
        # deb tasdiqlagan bo'lsa, ombor MANFIY ko'rsatishi kerak (haqiqiy
        # tanqislik miqdorini yashirmaslik uchun — bu ataylab qilingan).
        p.stock_quantity = float(p.stock_quantity) - blocks_needed
        log.append(f"{p.item_name}: -{blocks_needed:.2f} blok")
        # MUHIM: avval bu yerda "Ombor harakatlari" jurnaliga UMUMAN
        # yozilmasdi — faqat vaqtinchalik xabar uchun ishlatilardi. Endi
        # boshqa materiallar (Gips, Bazalt va h.k.) bilan bir xilda, haqiqiy
        # jurnalga ham yoziladi.
        try:
            _crud_lm.log_movement(db, p.id, p.item_name, movement_type="out",
                                   quantity=blocks_needed, unit="blok",
                                   order_id=getattr(order, 'id', None),
                                   reason=f"Buyurtma {getattr(order, 'order_number', '')} — Penoplast")
        except Exception:
            pass

    if volumes:
        if commit:
            db.commit()
        else:
            db.flush()
    return log
class _ProratedItem:
    """Buyurtma detalining faqat 'qolgan (topshirilmagan) qismi'ni ifodalovchi
    vaqtinchalik obyekt — mavjud hajm hisoblash funksiyalarini o'zgartirmasdan
    qayta ishlatish uchun."""
    def __init__(self, real_item, fraction):
        self.category = real_item.category
        self.width = real_item.width
        self.thickness = real_item.thickness
        self.penoplast_id = real_item.penoplast_id
        self.is_coated = real_item.is_coated
        self.price_per_m3 = real_item.price_per_m3
        self.finished_product_id = real_item.finished_product_id
        self.recipe_id = real_item.recipe_id
        cat = (real_item.category or '').lower()
        if cat == 'profil':
            self.length = float(real_item.length or 0) * fraction
            self.quantity = float(real_item.quantity or 1)
        else:
            self.length = real_item.length
            self.quantity = float(real_item.quantity or 0) * fraction

        # Ichki qo'shimcha detallar — ular ham xuddi shu "qolgan qism"
        # ulushida (fraction) qaytishi/qayta yechilishi kerak (parent
        # bilan bir xil xomashyodan bo'lgani uchun, alohida topshirish
        # ulushi kuzatilmaydi — parentnikiga qarab proratsiya qilinadi).
        self.sub_details = []
        for sub in (getattr(real_item, 'sub_details', None) or []):
            scat = (sub.category or 'profil').lower()
            sd = {"category": sub.category, "width": sub.width, "thickness": sub.thickness}
            if scat == 'profil':
                sd["length"] = float(sub.length or 0) * fraction
                sd["quantity"] = float(sub.quantity or 1)
            else:
                sd["length"] = sub.length
                sd["quantity"] = float(sub.quantity or 0) * fraction
            self.sub_details.append(sd)


def get_undelivered_items(order):
    """Buyurtmadagi har bir detal uchun 'hali topshirilmagan' ulushni hisoblaydi.
    Qaytaradi: [(real_item, fraction, remaining_qty, ordered_qty), ...]
    fraction — 0 dan 1 gacha (masalan 0.36 — 36% hali topshirilmagan)."""
    result = []
    for item in order.items:
        if (item.finished_product_id or None):
            continue  # Tayyor mahsulotdan olingan — bu yerda hisoblanmaydi
        ordered = item.order_qty_normalized
        if ordered <= 0:
            continue
        # kech60 (57-band): omborga qo'yilgan ortiqcha qism ham buyurtmadan chiqqan
        # (`OrderItem.remaining_qty`) — uning xomashyosi IKKINCHI marta qaytmaydi.
        remaining = item.remaining_qty
        if remaining <= 0.001:
            continue  # To'liq topshirilgan / omborga qo'yilgan — qaytariladigan narsa yo'q
        fraction = remaining / ordered
        result.append((item, fraction, remaining, ordered))
    return result


def buyurtmadan_qisman_chiqqan(order) -> bool:
    """kech60 (57-band, K59-3): buyurtmadan biror qism allaqachon CHIQQANMI — mijozga
    topshirilgan YOKI ortiqcha sifatida omborga qo'yilgan. Shunda o'chirish / tiklash
    xomashyoni faqat QOLGAN qism uchun qaytaradi / qayta yechadi
    (`return_inventory_for_order_partial`, loy — `loy_relevant_remaining_fraction`).
    Ikkalasi ham yo'q bo'lsa — avvalgidek butun buyurtma (`return_inventory_for_order`)."""
    if order.deliveries:
        return True
    return any(it.ortiqcha_qty > 0.001 for it in (order.items or []))


def return_inventory_for_order_partial(db: Session, order, sign: float = 1.0) -> list:
    """Qisman topshirilgan buyurtma bekor qilinganda/o'chirilganda —
    FAQAT hali topshirilmagan (mijozga berilmagan) qismi uchun xomashyoni
    omborga qaytaradi. Topshirib bo'lingan qism — mijozda, qaytmaydi.
    sign=-1.0 — buyurtma tiklanganda qayta ombordan yechish uchun."""

    log = []
    undelivered = get_undelivered_items(order)
    if not undelivered:
        return log

    prorated_items = [_ProratedItem(item, fraction) for item, fraction, _, _ in undelivered]
    verb = "qaytarildi" if sign > 0 else "qayta yechildi"

    # 1) Penoplast — qolgan qism bo'yicha
    cid = getattr(order, 'company_id', None)
    volumes = _group_volumes_by_penoplast(db, prorated_items, company_id=cid)
    for pid, vol in volumes.items():
        p = _peno_of(db, pid, cid, lock=True)
        if not p:
            continue
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks = (vol / vol_per_unit) * sign
        p.stock_quantity = float(p.stock_quantity) + blocks
        log.append(f"{p.item_name}: {blocks:+.2f} blok {verb} (qolgan qism)")

    return log


def return_inventory_for_order(db: Session, order, sign: float = 1.0) -> list:
    """
    Buyurtma o'chirilganda omborga xomashyo qaytaradi.
    Har detal o'z plotnostiga qaytariladi.
    sign=1.0 — qaytarish (standart). sign=-1.0 — teskarisi, ya'ni
    buyurtma TIKLANGANDA xuddi shu miqdorni qayta ombordan yechish uchun.
    """

    log = []
    cid = getattr(order, 'company_id', None)
    volumes = _group_volumes_by_penoplast(db, order.items, company_id=cid)

    for pid, vol in volumes.items():
        p = _peno_of(db, pid, cid, lock=True)
        if not p:
            continue
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks = (vol / vol_per_unit) * sign
        p.stock_quantity = float(p.stock_quantity) + blocks
        verb = "qaytarildi" if sign > 0 else "qayta yechildi"
        log.append(f"{p.item_name}: {blocks:+.2f} blok {verb}")

    if volumes:
        db.commit()
    return log


# ============================================================
# TAYYOR LOY ZAXIRASI
# ============================================================

def _get_planned_loy(order) -> float:
    """Buyurtma yaratilganda rejalashtirilgan loy miqdorini oladi.
    MUHIM: endi ALOHIDA, ishonchli ustundan (order.planned_loy_kg) o'qiladi —
    matn ichidan (notes) qidirish faqat shu tuzatishdan OLDIN yaratilgan
    ESKI buyurtmalar uchun zaxira (fallback) sifatida qoladi."""
    if getattr(order, 'planned_loy_kg', None) is not None:
        return float(order.planned_loy_kg)
    notes = order.notes or ''
    for part in notes.split(','):
        part = part.strip()
        if part.startswith('planned_loy='):
            try:
                return float(part.split('=')[1])
            except (ValueError, IndexError):
                pass
    return 0.0


def _remaining_fraction_for_items(items) -> float:
    """Berilgan detallar ro'yxati bo'yicha (ORDER-WIDE emas, faqat SHU
    detallar bo'yicha) QOLGAN (topshirilmagan) ulushni hisoblaydi —
    Order.delivery_percent bilan bir xil mantiq, lekin faqat kerakli
    detal to'plamiga cheklangan holda."""
    total_ordered = 0.0
    total_delivered = 0.0
    for it in items:
        ordered = it.order_qty_normalized
        if ordered <= 0:
            continue
        total_ordered += ordered
        # kech60 (57-band): omborga qo'yilgan ortiqcha qism ham chiqqan hisoblanadi
        total_delivered += min(it.delivered_qty + it.ortiqcha_qty, ordered)
    if total_ordered <= 0:
        return 1.0
    return max(0.0, 1 - total_delivered / total_ordered)


def loy_relevant_remaining_fraction(order) -> float:
    """Buyurtma o'chirilganda/tiklanganda LOY (qoplama) proporsional
    qaytarish/qayta yechish uchun QOLGAN ulush.

    MUHIM (2026-09 chuqur audit — ikkinchi bosqich): oldin bu yerda
    butun buyurtmaning ORDER-WIDE Order.delivery_percent'i ishlatilardi —
    lekin bu, buyurtmada LOY sarflamaydigan detallar (masalan "Tayyor
    mahsulotdan" olingan yoki qoplamasiz detallar) ham bo'lsa, juda
    noto'g'ri natija berishi mumkin edi. Masalan: 10 birlik qoplamali
    profil (loy kerak, hali topshirilmagan) + 990 birlik tayyor
    mahsulotdan detal (loy kerak emas, to'liq topshirilgan) — bunda
    order-wide delivery_percent ~99% chiqadi-yu, "qolgan 1%" loy
    qaytariladi, holbuki HAQIQATDA ~100% qaytishi kerak edi (chunki loy
    talab qiladigan yagona detal umuman topshirilmagan).

    Endi FAQAT haqiqatda LOY sarflaydigan detallar (qoplamali
    EMAS — uning loyi alohida tizim orqali hisoblanadi — va "Tayyor
    mahsulotdan" EMAS — uning xomashyosi ishlab chiqarishda allaqachon
    sarflangan) bo'yicha QOLGAN ulush hisoblanadi.

    kech62 (44-band, O'LCHANGAN — asl `25bcd8d`, SQLite va PG 16 AYNAN, `work/probe62.py`):
    bu ro'yxat MRP detalini (`mrp_product`) ham buyurtma loyini sarflovchi deb sanardi, holbuki
    MRP detali qoplamasi o'z BOM ining qoplama qatoridan yechiladi (11.0-band, ishlab chiqarishda
    avtomatik) — 41-band `_buyurtma_loyi_detalimi` ham uni chiqaradi. Natija: qoplamali profil 10 m
    (topshirilmagan) + qoplamali MRP 10 (to'liq topshirilgan), loy 30 kg — o'chirishda 15 kg qaytardi
    (to'g'risi 30), tiklashda 15 kg yechdi; aksi (profil topshirilgan, MRP yo'q) — 15 kg qaytardi
    (to'g'risi 0). Endi predikat YAGONA: qoplamali VA `_buyurtma_loyi_detalimi`."""
    items = [
        it for it in (order.items or [])
        if it.is_coated
        and _buyurtma_loyi_detalimi(it)
    ]
    if not items:
        return 1.0
    return _remaining_fraction_for_items(items)


def _set_planned_loy(order, kg: float) -> None:
    """Rejalashtirilgan loyni saqlaydi — endi to'g'ridan-to'g'ri, ishonchli
    ustunga (order.planned_loy_kg). Eski notes-belgisi ham, orqaga moslik
    uchun, parallel yozilib turadi (hozircha, keyinchalik olib tashlanishi
    mumkin)."""
    order.planned_loy_kg = kg
    notes = order.notes or ''
    parts = [p.strip() for p in notes.split(',') if p.strip() and not p.strip().startswith('planned_loy=')]
    parts.append(f'planned_loy={kg}')
    order.notes = ','.join(parts)


# ════════════════════════════════════════════════════════════════════
# kech58 (K58-1 / K58-2 / K58-3, 43-band) — BUYURTMA QOPLAMA RETSEPTI: YAGONA MANBA
# ════════════════════════════════════════════════════════════════════
# O'LCHANGAN (asl kod `e7dd594`, `work/probe58.py`, SQLite va HAQIQIY PG 16 — AYNAN):
#   K58-1: birinchi detal "Loy sotish" bo'lsa, buyurtmaning UMUMIY loyi tanlangan retseptdan
#          emas, "Loy sotish" retseptidan yechilardi (R1 5 200 / R2 20 000 so'm/kg: foydadagi
#          qoplama 52 000, to'g'risi 200 000). Brak summasi — birinchi QOPLAMALI detal
#          retseptidan, brak yechimi — detalning O'Z retseptidan: UCH xil manba (43-band).
#   K58-2: retsept "— Yo'q —" — loy korxonaning birinchi retseptidan yechilardi, lekin
#          foydada qoplama xarajati UMUMAN yo'q edi (jonli: buyurtma 185, 234 564.48 so'm).
#   K58-3: tahrirda retsept R1 -> R2 — ombor tegilmasdi, o'chirilganda loy R2 ga qaytardi
#          (R2 dan olinmagan 10 kg paydo bo'ldi, R1 ning 10 kg i qaytmadi).
# YECHIM (texnik — Claude): `orders.qoplama_retsept_id` — umumiy loy qaysi retseptdan yechilgan.
# FAQAT kech58 dan keyin YARATILGAN buyurtmaga yoziladi (FOYDALANUVCHI QARORI kech58:
# "Yo'q, faqat yangi buyurtmalar" — eski buyurtmalar foydasi o'zgarmaydi). Eski (NULL)
# buyurtma — avvalgi qoida AYNAN. Yechish, qaytarish, foyda, brak summasi va brak yechimi —
# hammasi `resolve_recipe(order=...)` / `buyurtma_qoplama_retsept_nomzodlari` orqali.

def _qoplama_retsept_nomzodlari_yangi(order) -> list:
    """YANGI buyurtma uchun qoplama retsepti nomzodlari (ustuvorlik tartibida, takrorsiz):
    1) buyurtma loyidan sarflaydigan QOPLAMALI detal (`_buyurtma_loyi_detalimi`);
    2) "Loy sotish" dan boshqa detal (UI buyurtma retseptini shu detallarga yozadi va
       tahrirda shu qoida bilan o'qiydi — `orders.html` `mainItem`);
    3) istalgan detal.
    Detallar `id` tartibida (PG da `ORDER BY` siz tartib UPDATE dan keyin o'zgarishi mumkin)."""
    items = list(getattr(order, 'items', None) or [])
    tartib = sorted(range(len(items)), key=lambda i: (getattr(items[i], 'id', None) is None,
                                                       getattr(items[i], 'id', None) or 0, i))
    items = [items[i] for i in tartib]

    def _tur(x):
        return (getattr(x, 'category', None) or '').lower()

    guruhlar = (
        [x for x in items if getattr(x, 'is_coated', False) and _buyurtma_loyi_detalimi(x)],
        [x for x in items if _tur(x) != 'loy_sotish'],
        items,
    )
    natija = []
    for g in guruhlar:
        for x in g:
            rid = getattr(x, 'recipe_id', None)
            if rid and rid not in natija:
                natija.append(rid)
    return natija


def buyurtma_qoplama_retsept_nomzodlari(order) -> list:
    """Buyurtma UMUMIY loyi retsepti nomzodlari — `resolve_recipe(order=...)` va foyda uchun.
    `qoplama_retsept_id` bor (kech58 dan keyin yaratilgan buyurtma) — avval u; so'ng (eski
    NULL buyurtmada — FAQAT) avvalgi qoida AYNAN: `order.items` tartibida `recipe_id` li detallar."""
    natija = []
    saqlangan = getattr(order, 'qoplama_retsept_id', None)
    if saqlangan:
        natija.append(saqlangan)
    for x in (getattr(order, 'items', None) or []):
        rid = getattr(x, 'recipe_id', None)
        if rid and rid not in natija:
            natija.append(rid)
    return natija


def buyurtma_qoplama_retseptini_tanla(db: Session, order, company_id: int = None):
    """YANGI qoida bo'yicha qoplama retsepti (korxona doirasida). Hech bir detalda retsept
    bo'lmasa — `resolve_recipe` zaxirasi (korxonaning birinchi retsepti): loy baribir shundan
    yechiladi, shuning uchun foyda ham shu retseptni ko'rishi SHART (K58-2)."""
    from models import Recipe
    cid = company_id if company_id is not None else getattr(order, 'company_id', None)
    q = db.query(Recipe)
    if cid is not None:
        q = q.filter(Recipe.company_id == cid)
    for rid in _qoplama_retsept_nomzodlari_yangi(order):
        r = q.filter(Recipe.id == rid).first()
        if r:
            return r
    if cid is None:
        return None
    return resolve_recipe(db, company_id=cid)


def resolve_recipe(db: Session, recipe_id: int = None, order=None,
                   company_id: int = None):
    """Retseptni HAR DOIM bitta korxona doirasida topadi — YAGONA manba.

    ⚠ 2026-09-21 — O'LCHANGAN SIZISH. Oldin retsept qidiruvi kamida
    5 joyda takrorlanardi va har birining oxirida `db.query(Recipe).first()`
    bor edi — BUTUN bazadagi birinchi retsept, ya'ni BOSHQA korxonaniki.

    Bu faqat o'qish sizishi emas edi: ingredientlar retseptning ichidan
    (`recipe.ingredients` → `ing.inventory_id`) olinadi, shuning uchun
    noto'g'ri retsept = noto'g'ri OMBOR. O'lchandi: retsepti yo'q YANGI
    korxona (B) loy ishlatganda A korxonaning omboridan xomashyo
    ayirildi (1000 → 995 → 992.5 kg).

    Shuning uchun ildiz shu yerda yopiladi: retsept to'g'ri korxonaniki
    bo'lsa — ombor ham avtomatik to'g'ri bo'ladi.

    Korxona qayerdan olinadi (tartib bilan):
      1) aniq berilgan `company_id`
      2) `order.company_id` (soxta buyurtma obyektlariga ham shu maydon
         qo'yilgan — pastdagi `_FakeOrder` larga qarang)
    Korxona ANIQLANMASA — "bazadagi birinchi retsept" zaxira yo'li
    ATAYLAB ishlatilmaydi. Retseptsiz qolish (hech narsa ayirilmaydi,
    jurnalga yoziladi) begona korxonaning retseptini jimgina
    ishlatishdan ko'ra xavfsizroq.
    """
    from models import Recipe

    cid = company_id
    if cid is None and order is not None:
        cid = getattr(order, 'company_id', None)

    q = db.query(Recipe)
    if cid is not None:
        q = q.filter(Recipe.company_id == cid)

    if recipe_id:
        r = q.filter(Recipe.id == recipe_id).first()
        if r:
            return r

    if order is not None:
        # kech58 (K58-1): buyurtmaning SAQLANGAN qoplama retsepti (yangi buyurtma), so'ng
        # avvalgi qoida AYNAN (eski buyurtma) — `buyurtma_qoplama_retsept_nomzodlari`.
        for rid in buyurtma_qoplama_retsept_nomzodlari(order):
            r = q.filter(Recipe.id == rid).first()
            if r:
                return r

    # Zaxira yo'l — FAQAT korxona aniq bo'lganda.
    # kech103 (K103-6, O'LCHANGAN `work/probe54r.py`, HAQIQIY PG 16): "birinchi retsept" `ORDER BY` siz edi — PG qatorlarni
    # jismoniy joylashuv tartibida beradi (UPDATE dan keyin o'zgaradi): SQLite da REC (id 1), PG da "Loy sotish"
    # retsepti (id 2) chiqdi. Endi AYNAN birinchi (id tartibida). 54-band dan keyin yangi buyurtma loyi bu yo'lga
    # tushmaydi (retsept majburiy) — eski buyurtmalar va retseptsiz so'rovlar (`/api/loy-stock` va h.k.) uchun.
    if cid is not None:
        return q.order_by(Recipe.id).first()
    return None


def _get_order_recipe(db: Session, order, company_id: int = None):
    """Buyurtmaning retseptini topadi (korxona doirasida)."""
    return resolve_recipe(db, order=order, company_id=company_id)


def get_or_create_loy_stock(db: Session, recipe, company_id: int = None, commit: bool = True):
    """Retsept uchun 'Tayyor loy' ombor pozitsiyasini topadi yoki yaratadi.

    2026-09-18 — M8/F1a: qidiruv FAQAT `item_name` bo'yicha global edi va
    yangi pozitsiya `company_id` siz yaratilardi (vaqtinchalik `DEFAULT 1`
    ga tayanardi). Ya'ni B korxonaning buyurtmasi A korxonaning "Tayyor
    loy" zaxirasini topib, undan ayirib olishi mumkin edi.

    Korxona retseptning O'ZIDAN olinadi (`recipe.company_id`) — retsept
    esa chaqiruvchi tomonidan allaqachon tenant-tekshirilgan. Ataylab
    shunday: bu funksiya buyurtma oqimining ichidan, turli joylardan
    chaqiriladi va retsept har doim to'g'ri tenantni beradi.
    Biznes mantig'i (nom shakli, birlik, boshlang'ich qoldiq) O'ZGARMADI."""
    from models import Inventory

    if not recipe:
        return None

    cid = company_id if company_id is not None else getattr(recipe, "company_id", None)

    recipe_name = recipe.name.value if hasattr(recipe.name, 'value') else str(recipe.name)
    item_name = f"Tayyor loy ({recipe_name})"

    _q = db.query(Inventory).filter(Inventory.item_name == item_name)
    if cid is not None:
        _q = _q.filter(Inventory.company_id == cid)
    stock = _q.with_for_update().first()
    if stock:
        return stock

    stock = Inventory(
        company_id=cid,
        item_name=item_name,
        stock_quantity=0.0,
        unit="kg",
        min_stock=0.0,
        price_per_unit=None,
        volume_per_unit=1.0,
        is_penoplast=False,
        notes="Buyurtmalardan ortgan tayyor loy — avtomatik yaratilgan"
    )
    db.add(stock)
    # kech63 (53-band): `commit=False` — chaqiruvchi qulf (101, buyurtma) ostida BITTA tranzaksiyada
    # ishlaydi (buyurtma tahriri); oraliq `commit` qulfni muddatidan OLDIN bo'shatardi.
    if commit:
        db.commit()
        db.refresh(stock)
    else:
        db.flush()
    print(f"✓ Ombor pozitsiyasi yaratildi: {item_name}")
    return stock


def add_loy_to_stock(db: Session, recipe, kg: float) -> str:
    """Ortgan loyni omborga qo'shadi."""
    if kg <= 0:
        return ""
    stock = get_or_create_loy_stock(db, recipe)
    if not stock:
        return ""
    stock.stock_quantity = float(stock.stock_quantity or 0) + kg
    db.commit()
    msg = f"{stock.item_name}: +{kg:.1f} kg (ortdi)"
    print(f"✓ {msg}")
    return msg


def take_loy_from_stock(db: Session, recipe, kg_needed: float, order=None, reason_override: str = None,
                        commit: bool = True):
    """Ombordagi tayyor loydan oladi.
    Qaytaradi: (olingan_kg, qolgan_ehtiyoj_kg, log_matni)
    kech63 (53-band): `commit=False` — faqat `flush` (chaqiruvchining tranzaksiyasi / qulfi saqlanadi)."""
    if kg_needed <= 0:
        return 0.0, 0.0, ""

    stock = get_or_create_loy_stock(db, recipe, commit=commit)
    if not stock:
        return 0.0, kg_needed, ""

    available = float(stock.stock_quantity or 0)
    if available <= 0:
        return 0.0, kg_needed, ""

    taken = min(available, kg_needed)
    stock.stock_quantity = available - taken
    if taken > 0:
        import crud as _crud
        # kech107 (36-band, O'LCHANGAN `work/probe107c.py`): tayyor loy pozitsiyasi narxsiz — harakat 0 so'm bilan
        # yozilardi: to'liq zaxiradan qoplangan buyurtma tannarxi keyingi narx o'zgarishi bilan siljirdi, brak esa zaxira
        # loyini 0 ga baholardi. Endi — OLINGAN paytdagi retsept tannarxi (1 kg), "ishlatilgan paytdagi narx" qarori.
        # Pozitsiyaga egasi narx qo'ygan bo'lsa (> 0) — o'sha narx (avvalgidek, `log_movement` joriy narxni oladi).
        _zaxira_narxi = None
        if not float(stock.price_per_unit or 0) > 0:
            try:
                _zaxira_narxi = float(get_loy_cost_per_kg(db, getattr(recipe, "id", None),
                                                          company_id=getattr(stock, "company_id", None))
                                      .get("cost_per_kg") or 0)
            except Exception:
                _zaxira_narxi = None
        _crud.log_movement(
            db, stock.id, stock.item_name, movement_type="out",
            quantity=taken, unit=stock.unit,
            reason=reason_override or f"Buyurtma {getattr(order, 'order_number', order.id) if order else '?'} (tayyor loy zaxirasidan)",
            order_id=order.id if order else None,
            unit_cost=_zaxira_narxi
        )
    if commit:
        db.commit()
    else:
        db.flush()
    msg = f"{stock.item_name}: -{taken:.1f} kg (zaxiradan)"
    print(f"✓ {msg}")
    return taken, kg_needed - taken, msg


# MUHIM (2026-09 — Fasa 3, brak-yozish konsolidatsiyasi): deduct_raw_material_
# for_finished_product_brak() shu yerda bo'lgan — yagona chaqiruvchisi
# crud.create_finished_product_brak() (Qaytarishlar sahifasi, "Ishlab
# chiqarishdan brak") olib tashlangani sabab, bu funksiya ham endi
# ishlatilmaydi va olib tashlandi. O'rniga: record_finished_product_
# production_brak() (crud.py) — Tayyor mahsulotlar sahifasi — ishlatiladi,
# u xuddi shu ishni (qo'shimcha xomashyoni ombordan ayirish, mahsulot
# soniga tegmasdan) qiladi, ammo ombor yetarliligini oldindan tekshiradi
# va InventoryMovement'ni izchil qayd etadi.


# ════════════════════════════════════════════════════════════════════
# kech54 (13-band, 41-band) — BRAK LOYI: buyurtma loyining detalga tushadigan ulushi
# ════════════════════════════════════════════════════════════════════
# O'LCHANGAN (asl kod `aecce02`, SQLite va HAQIQIY PG 16, `work/probe54.py`): buyurtmada
# loy BITTA umumiy son bo'lib kiritiladi ("Loy miqdori — barcha detallar uchun"), brakda
# esa u detallarga `order_qty_normalized` yig'indisi bo'yicha bo'linardi — metr (profil,
# panel) va dona bir xil birlik deb qo'shilardi (profil 10 m + panel 10 m + 100 dona, loy
# 30 kg: 100 dona loyning 25 kg ini "olardi"); maxrajga tayyor mahsulotdan olingan detal va
# MRP detali ham kirardi, holbuki bu buyurtma loyidan ular uchun sarf YO'Q (`_loy_remaining_
# fraction` ham ularni chiqaradi) — yangi profil braki 1 kg o'rniga 0.5 kg loy yechardi.
# FOYDALANUVCHI QARORI (kech54, tugma bilan): "Qoplama narxi ulushiga qarab (qimmat detal
# ko'proq)". Qoplama narxi — detal narxining qoplama uchun olingan qismi: penoplast
# detallarida qoplamali narx = qoplamasiz × QOPLAMA_NARX_KOEF (frontend `calculateItem`,
# `crud.create_order` izohi — narx YAKUNIY holda saqlanadi), ya'ni qoplama qismi =
# narx × (1 − 1 / KOEF). Ichki qo'shimcha detallar (`sub_details`) — o'z qoplama belgisi va
# narxi bilan (ota narxiga ALLAQACHON qo'shilgan, shuning uchun otadan ayiriladi).
# Hamma detal narxi 0 bo'lsa (narxsiz buyurtma) — eski usul (birlik soni), taxmin qilinmaydi.
QOPLAMA_NARX_KOEF = 2.0


def _buyurtma_loyi_kg(order) -> float:
    """Buyurtmaning loy miqdori (kg): haqiqiy → izohdagi `loy_kg=` → reja (avvalgidek)."""
    loy_kg = float(order.actual_loy_kg) if order.actual_loy_kg is not None else 0.0
    if loy_kg <= 0 and order.notes:
        import re as _re_loykg54
        m = _re_loykg54.search(r'loy_kg=([\d.]+)', str(order.notes))
        if m:
            try:
                loy_kg = float(m.group(1))
            except ValueError:
                pass
    if loy_kg <= 0:
        loy_kg = _get_planned_loy(order)
    return float(loy_kg or 0)


def _buyurtma_loyi_detalimi(oi) -> bool:
    """Detal buyurtmaning UMUMIY loyidan sarf qiladimi: tayyor mahsulotdan olingan
    (loyi ishlab chiqarishda sarflangan), "Loy sotish" (o'z retsepti bilan alohida
    yechiladi) va MRP detali (qoplamasi o'z BOM ining qoplama qatoridan) — YO'Q."""
    cat = (getattr(oi, 'category', None) or '').lower()
    if cat in ('loy_sotish', 'mrp_product'):
        return False
    return not getattr(oi, 'finished_product_id', None)


def _qoplama_narxi(oi) -> float:
    """Detal narxining QOPLAMA uchun olingan qismi (so'm) — 41-band qarori."""
    ulush = 1.0 - 1.0 / QOPLAMA_NARX_KOEF
    subs = list(getattr(oi, 'sub_details', None) or [])
    sub_jami = sum(max(0.0, float(getattr(s, 'total_price', 0) or 0)) for s in subs)
    asosiy = max(0.0, float(getattr(oi, 'total_price', 0) or 0) - sub_jami)
    q = asosiy * ulush if getattr(oi, 'is_coated', False) else 0.0
    for s in subs:
        if getattr(s, 'is_coated', False):
            q += max(0.0, float(getattr(s, 'total_price', 0) or 0)) * ulush
    return q


def _brak_loyi_birlikka(order, order_item) -> float:
    """Detalning 1 birligi (`order_qty_normalized` birligi) uchun buyurtma loyidan
    tushadigan kg. Brak yechimi (`deduct_raw_material_for_brak`) va brak summasi
    (`get_order_item_unit_cost`) SHU BITTA manbadan oladi."""
    if not order or not order_item or not getattr(order_item, 'is_coated', False):
        return 0.0
    if not _buyurtma_loyi_detalimi(order_item):
        return 0.0
    miqdor = float(order_item.order_qty_normalized or 0)
    if miqdor <= 0:
        return 0.0
    loy_kg = _buyurtma_loyi_kg(order)
    if loy_kg <= 0:
        return 0.0
    loy_detallari = [oi for oi in (order.items or []) if _buyurtma_loyi_detalimi(oi)]
    jami = sum(_qoplama_narxi(oi) for oi in loy_detallari)
    if jami > 0:
        return loy_kg * (_qoplama_narxi(order_item) / jami) / miqdor
    # Zaxira: buyurtmada narx yo'q — eski usul (qoplamali detallar birlik soni bo'yicha)
    birliklar = sum(float(oi.order_qty_normalized or 0) for oi in loy_detallari if oi.is_coated)
    return (loy_kg / birliklar) if birliklar > 0 else 0.0


# ════════════════════════════════════════════════════════════════════
# kech54 (13-band, 5-qadam) — MRP MAHSULOTI BRAKI: retsept SURATIDAN
# ════════════════════════════════════════════════════════════════════
# O'LCHANGAN (asl kod `aecce02`, SQLite va HAQIQIY PG 16, `work/probe55.py`): MRP detali
# (penoplast / loy retsepti yo'q) braki summasi 0 va xomashyo yechilmasdi; qoplamali MRP
# detalida esa BUYURTMA loyi retseptidan (MRP qoplamasi emas) yechilardi; "Ishlab
# chiqarishda chiqdi" (MRP tayyor mahsuloti) — 400 "xomashyo nisbati topilmadi".
# YECHIM (texnik — Claude): 1 birlik sarf — shu mahsulotni ishlab chiqargan (boshlangan
# yoki yakunlangan) ishlab chiqarish buyurtmasi(lar)ning `recipe_snapshot_json` idan,
# OMBOR birligida (`total_quantity_needed_stock_unit`, isrof foizi bilan), bir necha
# buyurtma bo'lsa — miqdor bo'yicha o'rtacha. Qadoq (`packaging`) qatorlari brakda
# sarflanmaydi (brak — ishlab chiqarish ichida, qadoqdan oldin). Qoplama qatorlari —
# faqat qoplama tortilgan bo'lsa (buyurtma braki: "loy tortilganmi"). Bekor qilingan
# / qoralama buyurtma hisobga olinmaydi. Surat yo'q (ishlab chiqarish boshlanmagan) — None.


def _mrp_eski_surat_qoplamalari(db, po) -> set:
    """`is_coating` kaliti bo'lmagan (kech54 dan oldingi) suratlar uchun: qoplama
    xomashyolari — buyurtmada TANLANGAN ixtiyoriy qatorlardan `is_coating` belgililari;
    ular BOM dan o'chib ketgan bo'lsa — shu BOM ning hozirgi qoplama qatorlari."""
    import json as _json_eq
    from production_models import BOMItem
    try:
        tanlangan = set(_json_eq.loads(po.selected_optional_bom_item_ids_json or "[]"))
    except Exception:
        tanlangan = set()
    bis = db.query(BOMItem).filter(BOMItem.bom_id == po.bom_id,
                                       BOMItem.company_id == po.company_id).all()
    inv = {bi.inventory_id for bi in bis
           if bi.id in tanlangan and bi.is_optional and getattr(bi, 'is_coating', False)}
    if inv:
        return inv
    return {bi.inventory_id for bi in bis if bi.is_optional and getattr(bi, 'is_coating', False)}


def _mrp_birlik_sarfi(db, company_id, order_item=None, finished_product=None,
                      qoplama: bool = True, surat_narxlari: dict = None):
    """MRP mahsulotining 1 birligi uchun xomashyo: {inventory_id: miqdor (ombor birligida)}.
    None — surati bor ishlab chiqarish buyurtmasi YO'Q (hali boshlanmagan).

    kech55 (34-band): `surat_narxlari` (lug'at) berilsa — har material uchun
    [miqdor, qiymat] yig'iladi, qiymat suratdagi `unit_price_at_time` (ishlab
    chiqarish paytidagi ombor birligi narxi) bilan; chaqiruvchi o'rtacha narxni
    oladi. Sarf (qaytadigan natija) va qatorlar tanlovi O'ZGARMAYDI.
    """
    import json as _json_ms
    from production_models import ProductionOrder
    q = db.query(ProductionOrder).filter(
        ProductionOrder.status.in_(["in_progress", "completed"]),
        ProductionOrder.recipe_snapshot_json.isnot(None))
    if company_id is not None:
        q = q.filter(ProductionOrder.company_id == company_id)
    if order_item is not None:
        q = q.filter(ProductionOrder.source_order_item_id == order_item.id)
    elif finished_product is not None:
        q = q.filter(ProductionOrder.finished_product_id == finished_product.id)
    else:
        return None
    jami_miqdor = 0.0
    sarf = {}
    for po in q.order_by(ProductionOrder.id).all():
        pq = float(po.quantity or 0)
        try:
            surat = _json_ms.loads(po.recipe_snapshot_json or "[]")
        except Exception:
            surat = None
        if pq <= 0 or not isinstance(surat, list):
            continue
        jami_miqdor += pq
        eski_qoplama = None
        for qator in surat:
            if not isinstance(qator, dict) or not qator.get("included"):
                continue
            if (qator.get("component_type") or "raw_material") == "packaging":
                continue
            if "is_coating" in qator:
                qoplamami = bool(qator.get("is_coating"))
            else:
                if eski_qoplama is None:
                    eski_qoplama = _mrp_eski_surat_qoplamalari(db, po)
                qoplamami = bool(qator.get("is_optional")) and qator.get("inventory_id") in eski_qoplama
            if qoplamami and not qoplama:
                continue
            kerak = float(qator.get("total_quantity_needed_stock_unit",
                                    qator.get("total_quantity_needed", 0)) or 0)
            if kerak <= 0 or not qator.get("inventory_id"):
                continue
            sarf[qator["inventory_id"]] = sarf.get(qator["inventory_id"], 0.0) + kerak
            if surat_narxlari is not None and qator.get("unit_price_at_time") is not None:
                _sx = surat_narxlari.setdefault(qator["inventory_id"], [0.0, 0.0])
                _sx[0] += kerak
                _sx[1] += kerak * float(qator.get("unit_price_at_time") or 0)
    if jami_miqdor <= 0:
        return None
    return {k: v / jami_miqdor for k, v in sarf.items()}


def _mrp_sarf_qiymati(db, sarf: dict, company_id, narxlar: dict = None) -> float:
    """1 birlik sarfning JORIY narxdagi qiymati (brak yozilgan paytdagi narx — 13-band 2-qadam).
    kech55 (34-band): `narxlar` berilsa ({inventory_id: narx}) — lug'atdagi material o'sha
    narxda (qaytgan mahsulot — ishlab chiqarish paytidagi narx), qolgani joriy narxda."""
    from models import Inventory
    jami = 0.0
    for inv_id, miqdor in (sarf or {}).items():
        q = db.query(Inventory).filter(Inventory.id == inv_id)
        if company_id is not None:
            q = q.filter(Inventory.company_id == company_id)
        inv = q.first()
        if inv:
            _nx = narxlar.get(inv_id) if narxlar else None
            jami += float(miqdor) * (float(_nx) if _nx is not None else float(inv.price_per_unit or 0))
    return jami


def _mrp_brakini_yech(db, order_item, order, brak_qty: float, coating_applied: bool,
                      company_id, log: list) -> list:
    """Buyurtmadagi MRP detali braki: suratdagi 1 birlik sarf × brak miqdori ombordan
    yechiladi (`crud.log_movement` — brak yozuviga bog'lam, brak belgisi va narx shu
    yerdan). Ombor 0 ga qirqilmaydi (20-band qoidasi — xomashyo haqiqatan sarflangan)."""
    import crud as _crud_mb
    from models import Inventory
    sarf = _mrp_birlik_sarfi(db, company_id, order_item=order_item, qoplama=bool(coating_applied))
    for inv_id, birlik in sorted((sarf or {}).items()):
        kerak = float(birlik) * float(brak_qty)
        if kerak <= 0:
            continue
        q = db.query(Inventory).filter(Inventory.id == inv_id)
        if company_id is not None:
            q = q.filter(Inventory.company_id == company_id)
        inv = q.with_for_update().first()
        if not inv:
            continue
        inv.stock_quantity = float(inv.stock_quantity or 0) - kerak
        _crud_mb.log_movement(
            db, inv.id, inv.item_name, movement_type="out", quantity=kerak, unit=inv.unit,
            reason=_crud_mb._jurnal_sabab(f"Brak — {order_item.name} (MRP, {brak_qty:g} birlik)"),
            order_id=order.id if order else None, company_id=getattr(inv, 'company_id', None))
        log.append(f"{inv.item_name}: -{kerak:g} {inv.unit} (brak — MRP)")
    db.commit()
    return log


def deduct_raw_material_for_brak(db: Session, order_item, order, brak_qty: float, coating_applied: bool) -> list:
    """Brak bo'lgan detal uchun xomashyoni ombordan yechadi.

    - Penoplast — HAR DOIM yechiladi (detal shakli kesilgan bo'lsa, xomashyo
      allaqachon sarflangan — brak bo'lishidan qat'i nazar).
    - Loy (qoplama) — FAQAT coating_applied=True bo'lsa yechiladi (ya'ni
      brak AYNAN qoplama tortilgandan keyin, uni sindirib/tirnab
      yuborilgan bo'lsa). Agar qoplamagacha (masalan kesish jarayonida)
      brak bo'lgan bo'lsa — loy sarflanmagan, hisoblanmaydi.

    Faqat log qaytaradi, hech qanday moliyaviy hisob-kitobni o'zgartirmaydi
    (bu — create_return_item() dagi refund_amount hisobidan MUSTAQIL)."""
    from models import InventoryMovement

    log = []
    if brak_qty <= 0 or not order_item:
        return log

    _bcid = getattr(order, 'company_id', None) or getattr(order_item, 'company_id', None)
    # kech54 (13-band, 5-qadam): MRP detali — retsept suratidan (yuqoridagi izoh).
    # Tayyor mahsulotdan olingan MRP detali — avvalgidek (xomashyo yechilmaydi).
    if ((getattr(order_item, 'category', None) or '').lower() == 'mrp_product'
            and not getattr(order_item, 'finished_product_id', None)):
        return _mrp_brakini_yech(db, order_item, order, brak_qty, coating_applied, _bcid, log)
    default_p = get_default_penoplast(db, company_id=_bcid)
    total_volume = _item_volume_m3(db, order_item, default_p, company_id=_bcid)   # kech99 (112-band)
    qty_units = order_item.order_qty_normalized
    if total_volume > 0 and qty_units > 0:
        per_unit_volume = total_volume / qty_units
        brak_volume = per_unit_volume * brak_qty
        pid = order_item.penoplast_id or (default_p.id if default_p else None)
        if pid and brak_volume > 0:
            p = _peno_of(db, pid, _bcid)
            if p and p.volume_per_unit and p.volume_per_unit > 0:
                blocks = brak_volume / float(p.volume_per_unit)
                old_qty = float(p.stock_quantity or 0)
                # 20-band (2026-09-21): 0 ga QIRQILMAYDI. Penoplast allaqachon
                # kesilgan — sarf haqiqiy; jurnalga ham to'liq `blocks` yoziladi.
                # Ilgari `max(0, ...)` manfiy qoldiqni ("qarz" — masalan
                # `deduct_inventory_for_order` ataylab qoldirgan tanqislikni)
                # jimgina 0 ga ko'tarib o'chirardi, jurnal esa to'liq sarfni
                # ko'rsatardi — ombor va jurnal bir-biriga zid bo'lib qolardi.
                p.stock_quantity = old_qty - blocks
                db.add(InventoryMovement(
                    inventory_id=p.id, item_name=p.item_name, movement_type="out",
                    quantity=blocks, unit=p.unit,
                    reason=f"Brak — {order_item.name} ({brak_qty:g} birlik)",
                    order_id=order.id if order else None,
                    # kech45 (13-band): brak yozuviga bog'lam (o'chirishda qaytadi)
                    return_item_id=db.info.get("_brak_qaytarish_id"),
                    # kech46 (13-band, 2-qadam): chiqim paytidagi narx muzlatiladi
                    unit_cost=float(p.price_per_unit or 0),
                    # kech52 (13-band, 3-qadam): brak belgisi — hisobot matnga qaramaydi
                    is_brak=True
                ))
                log.append(f"{p.item_name}: -{blocks:.3f} blok (brak uchun)")

    if coating_applied and order_item.is_coated and order:
        # kech54 (41-band): 1 birlik loyi — qoplama narxi ulushi bo'yicha (`_brak_loyi_birlikka`)
        loy_per_unit = _brak_loyi_birlikka(order, order_item)
        if loy_per_unit > 0:
            brak_loy_kg = loy_per_unit * brak_qty
            if brak_loy_kg > 0:
                # kech58 (K58-1, 43-band): brak loyi — buyurtma loyi YECHILGAN retseptdan
                # (`resolve_recipe(order=...)`), detalning o'z `recipe_id` sidan EMAS.
                loy_log = deduct_loy_ingredients(
                    db, order, brak_loy_kg, recipe_id=None,
                    reason_override=f"Brak — {order_item.name} (qoplama, {brak_qty:g} birlik)"
                )
                log.extend([f"{l} (brak — qoplama)" for l in loy_log])

    db.commit()
    return log


def check_loy_ingredients_for_order(db: Session, order_recipe_id: int, loy_kg: float,
                                    company_id: int = None, commit: bool = True) -> dict:
    """Qoplama (loy) uchun kerakli xomashyo yetarli-yetarli emasligini
    OLDINDAN tekshiradi (hali hech narsa ayirilmasdan). Avval "tayyor loy"
    zaxirasi hisobga olinadi, keyin qolgan qism uchun retsept xomashyosi
    tekshiriladi — deduct_loy_ingredients() bilan BIR XIL mantiq."""
    from models import Inventory

    if loy_kg <= 0:
        return {"enough": True, "shortages": []}

    # 2026-09-21 — TENANT: retsept faqat o'z korxonasidan (resolve_recipe).
    recipe = resolve_recipe(db, recipe_id=order_recipe_id, company_id=company_id)
    if not recipe:
        return {"enough": True, "shortages": []}

    # Tayyor loy zaxirasi bor-yo'qligini tekshiramiz (ayirmasdan, faqat o'qib)
    # kech63 (53-band): `commit=False` — pozitsiya yangi yaratilsa ham faqat `flush` (tahrir qulfi).
    stock = get_or_create_loy_stock(db, recipe, commit=commit)
    available_stock = float(stock.stock_quantity or 0) if stock else 0.0
    remaining_kg = max(0.0, loy_kg - available_stock)

    if remaining_kg <= 0:
        return {"enough": True, "shortages": []}

    batch = float(recipe.batch_size_kg or 100)
    shortages = []
    for ing in recipe.ingredients:
        recipe_kg = float(ing.quantity_kg or 0)
        # kech99 (112-band): begona ingredient (eski ma'lumot) — o'tkazib yuboriladi, B nomi / qoldig'i A ga chiqmaydi
        if recipe_kg <= 0 or not _retsept_materiali(ing, recipe):
            continue
        needed_kg = remaining_kg * (recipe_kg / batch)
        inv_item = db.query(Inventory).filter(Inventory.id == ing.inventory_id,
                                              Inventory.company_id == recipe.company_id).first()
        if inv_item and float(inv_item.stock_quantity or 0) < needed_kg:
            shortages.append(
                f"{inv_item.item_name} (loy uchun): kerak {needed_kg:.2f} {inv_item.unit}, "
                f"qoldi {float(inv_item.stock_quantity or 0):.2f} {inv_item.unit}"
            )

    return {"enough": len(shortages) == 0, "shortages": shortages}


# ════════════════════════════════════════════════════════════════════
# kech82 (102-band, FOYDALANUVCHI QARORI "A") — BUYURTMA LOYI OLINGAN JOYIGA QAYTADI
# ════════════════════════════════════════════════════════════════════
# O'LCHANGAN (asl kod = zip 77, `work/probe102.py`, SQLite = PG 16 — 20 / 103 yiqilish AYNAN; JONLI — buyurtma
# 218, "Tayyor loy (Oq marmar)"): buyurtma loyni `deduct_loy_ingredients(use_stock=True)` bilan AVVAL
# "Tayyor loy (<retsept>)" zaxirasidan oladi, `return_loy_ingredients` esa DOIM xom ingredientlarga qaytarardi —
# o'chirish, "Loy sotish", qisman "Tayyor" dagi ortgan loy, loy rejasini kamaytirish, qoplama retseptini
# almashtirish. Har sikl tayyor loyni xom ashyoga "aylantirardi" (zaxiradan 10 kg olgan buyurtmani o'chirish ->
# tiklash -> o'chirish: zaxira -20, kley +20 — hech qachon sotib olinmagan xomashyo). Tiklash esa o'chirish xomga
# qaytargan loyni ZAXIRADAN yechardi.
#
# Endi buyurtma (`Order.loy_manba_json`, retsept bo'yicha) ushlab turgan loyining qancha qismi zaxiradan (`z`),
# qanchasi xomdan (`x`) olinganini saqlaydi ("r" bo'limi). Qaytishda avval XOM qism, qolgani (zaxiradan olingan
# qismgacha) ZAXIRAGA: buyurtma tayyor (aralashtirilgan) loyni birinchi ishlatadi, ishlatilmay qolgani —
# aralashtirilmagan xom ashyo (`complete_order` dagi qisman yakunlash qoidasi bilan bir xil). To'liq qaytishda
# natija AYNAN olingan joylar. O'chirish nima qilganini ("o" bo'limi: + qaytgan, - qo'shimcha yechilgan) yozadi —
# tiklash AYNAN teskarisi. NULL — migratsiyadan OLDINGI buyurtma: eski qoida (qaytish xomga); uning tiklanishi ham
# faqat xomdan (o'sha o'chirish xomga qaytargan). Qoralama faollashtirilganda kuzatuv boshlanadi (hech narsa
# yechilmagan edi).
#
# Rejim sessiyada (`db.info`, brakdagi `_brak_qaytarish_id` naqshi) — chaqiruv qatorlari o'zgarmaydi:
#   "ushla"    — buyurtma loyi yechiladi / ishlatilmagani qaytadi (yaratish, faollashtirish, tahrir, qisman "Tayyor");
#   "ochirish" — buyurtma o'chirilmoqda (qaytish va qo'shimcha sarf "o" ga yoziladi);
#   "tiklash"  — o'chirishning teskarisi ("o" bo'yicha).
# Rejimsiz chaqiruvlar (brak, tayyor mahsulot, "Tayyor" dagi qo'shimcha sarf) — avvalgidek, hech narsa yozilmaydi.
import contextlib as _contextlib_lm

LOY_MANBA_KALIT = "_loy_manba_rejimi"
LOY_MANBA_REJIMLARI = ("ushla", "ochirish", "tiklash")
LOY_MANBA_BOSH = '{"r": {}}'
_LM_EPS = 1e-9


@_contextlib_lm.contextmanager
def loy_manba_rejimi(db, rejim):
    """Blok ichidagi `deduct_loy_ingredients` / `return_loy_ingredients` chaqiruvlari buyurtma loyi manbasini
    `rejim` bo'yicha hisobga oladi. Blokdan keyin (istisnoda ham) oldingi holat qaytadi."""
    if rejim not in LOY_MANBA_REJIMLARI:
        raise ValueError(f"Noma'lum loy manbasi rejimi: {rejim}")
    _yoq = object()
    eski = db.info.get(LOY_MANBA_KALIT, _yoq)
    db.info[LOY_MANBA_KALIT] = rejim
    try:
        yield
    finally:
        if eski is _yoq:
            db.info.pop(LOY_MANBA_KALIT, None)
        else:
            db.info[LOY_MANBA_KALIT] = eski


def _loy_manba_joriy_rejim(db, order):
    """Faol rejim — faqat haqiqiy buyurtma (`loy_manba_json` atributi bor) uchun; soxta buyurtma — None."""
    if order is None or not hasattr(order, "loy_manba_json"):
        return None
    info = getattr(db, "info", None)
    rejim = info.get(LOY_MANBA_KALIT) if isinstance(info, dict) else None
    return rejim if rejim in LOY_MANBA_REJIMLARI else None


def loy_manba_ol(order):
    """`Order.loy_manba_json` -> dict yoki None (NULL / buzuq qiymat / buyurtma emas)."""
    import json as _json_lm
    raw = getattr(order, "loy_manba_json", None) if order is not None else None
    if not raw:
        return None
    try:
        d = _json_lm.loads(raw)
    except (TypeError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def _loy_manba_saqla(order, d):
    import json as _json_lm
    order.loy_manba_json = _json_lm.dumps(d, sort_keys=True) if d else None


def _lm_son(d, bolim, kalit, maydon):
    try:
        return float(((d.get(bolim) or {}).get(kalit) or {}).get(maydon) or 0.0)
    except (AttributeError, TypeError, ValueError):
        return 0.0


def _lm_qosh(d, bolim, kalit, maydon, qiymat):
    b = d.get(bolim)
    if not isinstance(b, dict):
        b = {}
        d[bolim] = b
    k = b.get(kalit)
    if not isinstance(k, dict):
        k = {}
        b[kalit] = k
    try:
        eski = float(k.get(maydon) or 0.0)
    except (TypeError, ValueError):
        eski = 0.0
    yangi = eski + float(qiymat)
    if abs(yangi) < _LM_EPS:
        yangi = 0.0
    k[maydon] = yangi


def loy_manba_ochirish_boshla(order):
    """O'chirishda ombor qaytishidan OLDIN: "o" bo'limi yangidan (tiklash shu yozuv bo'yicha)."""
    if order is None or not hasattr(order, "loy_manba_json"):
        return
    d = loy_manba_ol(order) or {}
    d["o"] = {}
    _loy_manba_saqla(order, d)


def loy_manba_ochirish_tozala(order):
    """Tiklash tugagach: "o" bo'limi olib tashlanadi (kuzatilmaydigan eski buyurtma — yana NULL)."""
    if order is None or not hasattr(order, "loy_manba_json"):
        return
    d = loy_manba_ol(order)
    if d is None:
        return
    d.pop("o", None)
    _loy_manba_saqla(order, d)


def _loy_manba_tiklash_zaxira_kg(order, kalit, kg):
    """Tiklashda shu yechishning qancha qismi ZAXIRADAN olinadi — o'chirish zaxiraga qaytargan qismgacha.
    O'chirish yozuvi yo'q (migratsiyadan oldin o'chirilgan) — 0: o'sha o'chirish hammasini xomga qaytargan."""
    d = loy_manba_ol(order)
    if d is None or "o" not in d:
        return 0.0
    return min(float(kg), max(0.0, _lm_son(d, "o", kalit, "z")))


def _loy_manba_yechish_qayd(order, rejim, kalit, jami, stokdan, kerak_z=0.0):
    """`deduct_loy_ingredients` natijasini yozadi: jami — yechilgan loy (kg), stokdan — shundan zaxiradan."""
    d = loy_manba_ol(order)
    xom = max(0.0, float(jami) - float(stokdan))
    ozgardi = False
    if rejim == "ushla":
        if d is not None and "r" in d:
            _lm_qosh(d, "r", kalit, "z", stokdan)
            _lm_qosh(d, "r", kalit, "x", xom)
            ozgardi = True
    elif rejim == "ochirish":
        # Hodim rejadan KO'P ishlatgan (qo'shimcha sarf) — ushlanmaydi, faqat tiklash uchun yoziladi.
        d = d if d is not None else {}
        _lm_qosh(d, "o", kalit, "z", -float(stokdan))
        _lm_qosh(d, "o", kalit, "x", -xom)
        ozgardi = True
    elif rejim == "tiklash":
        if d is not None and "o" in d:
            _lm_qosh(d, "o", kalit, "z", -float(kerak_z))
            _lm_qosh(d, "o", kalit, "x", -(float(jami) - float(kerak_z)))
            ozgardi = True
        if d is not None and "r" in d:
            _lm_qosh(d, "r", kalit, "z", stokdan)
            _lm_qosh(d, "r", kalit, "x", xom)
            ozgardi = True
    if ozgardi:
        _loy_manba_saqla(order, d)


def _loy_manba_qaytish_zaxiraga(order, rejim, kalit, kg):
    """`return_loy_ingredients`: qaytadigan `kg` loydan qanchasi TAYYOR LOY ZAXIRASIGA (qolgani xomga)."""
    d = loy_manba_ol(order)
    kg = float(kg)
    zaxiraga = 0.0
    ozgardi = False
    if rejim in ("ushla", "ochirish"):
        if d is not None and "r" in d:
            rx = min(kg, max(0.0, _lm_son(d, "r", kalit, "x")))
            rz = min(kg - rx, max(0.0, _lm_son(d, "r", kalit, "z")))
            _lm_qosh(d, "r", kalit, "x", -rx)
            _lm_qosh(d, "r", kalit, "z", -rz)
            zaxiraga = rz
            ozgardi = True
        if rejim == "ochirish":
            d = d if d is not None else {}
            _lm_qosh(d, "o", kalit, "z", zaxiraga)
            _lm_qosh(d, "o", kalit, "x", kg - zaxiraga)
            ozgardi = True
    elif rejim == "tiklash":
        # O'chirishdagi QO'SHIMCHA sarf teskarisi: zaxiradan olingani zaxiraga, xomdan olingani xomga.
        if d is not None and "o" in d:
            zaxiraga = min(kg, max(0.0, -_lm_son(d, "o", kalit, "z")))
            _lm_qosh(d, "o", kalit, "z", zaxiraga)
            _lm_qosh(d, "o", kalit, "x", kg - zaxiraga)
            ozgardi = True
    if ozgardi:
        _loy_manba_saqla(order, d)
    return zaxiraga


def deduct_loy_ingredients(db: Session, order, loy_kg: float, use_stock: bool = True, recipe_id: int = None, reason_override: str = None, company_id: int = None, commit: bool = True) -> list:
    """
    Loy (qoplama) uchun ingredientlarni ombordan ayiradi.
    use_stock=True bo'lsa — avval tayyor loy zaxirasidan oladi.
    recipe_id berilsa — aynan O'SHA retsept ishlatiladi (masalan "Loy sotish"
    detali uchun, buyurtmaning umumiy qoplama retseptidan farqli bo'lishi
    mumkin). Berilmasa — avvalgidek, buyurtmadan avtomatik topiladi.
    reason_override berilsa — jurnal yozuvida standart "Buyurtma X (loy)"
    o'rniga shu matn ishlatiladi (masalan brak hisoboti uchun "Brak — ...").
    kech63 (53-band): `commit=False` — oxirida (va tayyor loy zaxirasida) faqat `flush`:
    chaqiruvchi qulf (101, buyurtma) ostida BITTA tranzaksiyada ishlaydi (buyurtma tahriri).
    """
    from models import Inventory

    if loy_kg <= 0:
        return []

    log = []

    # 2026-09-21 — TENANT: berilgan recipe_id ham korxona bo'yicha
    # tekshiriladi; zaxira yo'l ("bazadagi birinchi retsept") korxona
    # noma'lum bo'lsa ISHLATILMAYDI. Sabab: ingredientlar retseptdan
    # olinadi, ya'ni begona retsept = begona OMBORDAN ayirish.
    recipe = resolve_recipe(db, recipe_id=recipe_id, order=order,
                            company_id=company_id)

    if not recipe:
        print("⚠ Retsept topilmadi — loy ingredientlari ayirilmadi")
        return []

    # 1) Avval tayyor loy zaxirasidan olamiz
    # kech82 (102-band): buyurtma loyi manbasi (yuqoridagi "OLINGAN JOYIGA QAYTADI" izohi). Tiklashda zaxiradan
    # faqat o'chirish zaxiraga qaytargan qismgacha, qolgani xomdan — o'chirishning AYNAN teskarisi.
    _lm_rejim = _loy_manba_joriy_rejim(db, order)
    _lm_kalit = str(recipe.id)
    _lm_jami = float(loy_kg)
    _lm_stokdan = 0.0
    _lm_kerak_z = 0.0
    if _lm_rejim == "tiklash":
        _lm_kerak_z = _loy_manba_tiklash_zaxira_kg(order, _lm_kalit, loy_kg)
        if _lm_kerak_z > _LM_EPS:
            taken, _lm_qoldi, msg = take_loy_from_stock(db, recipe, _lm_kerak_z, order=order,
                                                         reason_override=reason_override, commit=commit)
            if msg:
                log.append(msg)
            _lm_stokdan = float(taken)
            loy_kg = loy_kg - float(taken)
    elif use_stock:
        taken, loy_kg, msg = take_loy_from_stock(db, recipe, loy_kg, order=order, reason_override=reason_override,
                                                 commit=commit)
        if msg:
            log.append(msg)
        _lm_stokdan = float(taken)
    if _lm_rejim:
        _loy_manba_yechish_qayd(order, _lm_rejim, _lm_kalit, _lm_jami, _lm_stokdan, _lm_kerak_z)
    if loy_kg <= 0:
        if _lm_rejim:
            # loy manbasi yozuvi ham shu chaqiruvning o'zida saqlanadi (zaxira qismi allaqachon yozilgan)
            if commit:
                db.commit()
            else:
                db.flush()
        return log  # Zaxira yetdi, xomashyo kerak emas

    batch = float(recipe.batch_size_kg or 100)

    for ing in recipe.ingredients:
        recipe_kg = float(ing.quantity_kg or 0)
        # kech99 (112-band): begona ingredient (eski ma'lumot) — yechilmaydi (penoplast `_peno_of` qoidasi)
        if recipe_kg <= 0 or not _retsept_materiali(ing, recipe):
            continue
        needed_kg = loy_kg * (recipe_kg / batch)
        inv_item = db.query(Inventory).filter(
            Inventory.id == ing.inventory_id,
            Inventory.company_id == recipe.company_id,
        ).with_for_update().first()
        if inv_item:
            # 2026-09-21 — FOYDALANUVCHI QARORI (19-band): loy xomashyosi
            # yetishmasa ishlab chiqarish TO'XTAMAYDI, qoldiq MANFIYGA
            # tushadi va keyingi kirimda qoplanadi (so'zma-so'z: "ishlab
            # chiqarish to'xtamaydi, manfiyga tushib qoladi, omborga kirim
            # qilinganda ayirilib tashlanadi, shunday ishlasin").
            # Ilgari (2026-09 audit) bu yerda qoldiq 0 da to'xtatilardi —
            # yetishmagan miqdor HECH QAYERDA qolmasdi: keyingi kirim uni
            # qoplamas, ombor haqiqatdagidan KO'P ko'rinardi. Kirim
            # (`crud._purchase_stock_no_commit`) manfiy qoldiqni arifmetik
            # qoplaydi va narxni faqat yangi xariddan oladi. Qo'lda chiqim
            # (`crud.update_stock`) manfiy qoldiqdan chiqim qilishni RAD
            # etadi (qarz jimgina o'chmasin). Faqat LOY ingredientlari —
            # penoplast yetishmasa avvalgidek to'xtaydi.
            current = float(inv_item.stock_quantity or 0)
            new_qty = current - needed_kg
            inv_item.stock_quantity = new_qty
            log.append(f"{inv_item.item_name}: -{needed_kg:.2f} {inv_item.unit}")
            if new_qty < -0.001:
                # Shu ayirishning omborda YO'Q qismi (qoldiq oldindan
                # manfiy bo'lsa — butun ayirish).
                shortage = min(needed_kg, -new_qty)
                log.append(f"⚠️ {inv_item.item_name}: omborda YETARLI EMAS EDI — {shortage:.2f} {inv_item.unit} yetishmovchilik; qoldiq manfiy: {new_qty:.2f} {inv_item.unit}, keyingi kirimda qoplanadi")
                print(f"⚠ {inv_item.item_name}: YETISHMOVCHILIK {shortage:.2f} {inv_item.unit}, qoldiq {new_qty:.2f}")
            print(f"✓ {inv_item.item_name}: -{needed_kg:.2f} ayirildi")
            import crud as _crud
            _crud.log_movement(
                db, inv_item.id, inv_item.item_name, movement_type="out",
                quantity=needed_kg, unit=inv_item.unit,
                reason=reason_override or f"Buyurtma {getattr(order, 'order_number', None) or (order.id if order else '?')} (loy)",
                order_id=order.id if order else None
            )

    if commit:
        db.commit()
    else:
        db.flush()
    return log


def return_loy_ingredients(db: Session, order, loy_kg: float, recipe_id: int = None,
                           company_id: int = None, reason_override: str = None,
                           commit: bool = True) -> list:
    """
    Loy ingredientlarini omborga qaytaradi (buyurtma o'chirilganda).
    recipe_id berilsa — aynan O'SHA retsept ishlatiladi.

    20-band (2026-09-21): `reason_override` — jurnal sababi (masalan tayyor
    mahsulot o'chirilganda). Ilgari u yo'l soxta "TERMOPANEL +" buyurtma
    obyekti bilan chaqirilar va HAR QANDAY mahsulot o'chirilganda jurnalga
    "Buyurtma TERMOPANEL + bekor qilindi" yozilardi. Berilmasa — eski matn.

    2026-09-21 — TENANT: retsept qidiruvi `resolve_recipe` ga o'tkazildi.
    Qaytarish ham xuddi ayirish kabi xavfli edi — begona retsept bilan
    BEGONA omborga xomashyo "qaytarilardi".

    kech63 (53-band): `commit=False` — oxirida faqat `flush` (buyurtma tahriri qulf ostida).
    """
    from models import Inventory

    if loy_kg <= 0:
        return []

    log = []

    recipe = resolve_recipe(db, recipe_id=recipe_id, order=order,
                            company_id=company_id)

    if not recipe:
        return []

    # kech82 (102-band): buyurtma loyi manbasi rejimida zaxiradan olingan qism (xom qismdan ortgani) TAYYOR LOY
    # ZAXIRASIGA qaytadi — jurnalga "in" harakati bilan; qolgani avvalgidek xom ingredientlarga.
    _lm_rejim = _loy_manba_joriy_rejim(db, order)
    _lm_zaxiraga = 0.0
    if _lm_rejim:
        _lm_zaxiraga = _loy_manba_qaytish_zaxiraga(order, _lm_rejim, str(recipe.id), loy_kg)
    if _lm_zaxiraga > _LM_EPS:
        _zx = get_or_create_loy_stock(db, recipe, commit=False)
        if _zx is not None:
            _zx.stock_quantity = float(_zx.stock_quantity or 0) + _lm_zaxiraga
            log.append(f"{_zx.item_name}: +{_lm_zaxiraga:.2f} kg tayyor loy zaxirasiga qaytarildi")
            import crud as _crud_lm
            _crud_lm.log_movement(
                db, _zx.id, _zx.item_name, movement_type="in",
                quantity=_lm_zaxiraga, unit=_zx.unit,
                reason=reason_override or (f"Buyurtma {getattr(order, 'order_number', order.id)} — ishlatilmagan loy "
                                           f"tayyor loy zaxirasiga qaytarildi"),
                order_id=order.id
            )
            loy_kg = loy_kg - _lm_zaxiraga
    if loy_kg <= _LM_EPS:
        if commit:
            db.commit()
        else:
            db.flush()
        return log

    batch = float(recipe.batch_size_kg or 100)

    for ing in recipe.ingredients:
        recipe_kg = float(ing.quantity_kg or 0)
        # kech99 (112-band): begona ingredient (eski ma'lumot) — qaytarilmaydi (yechilmagan ham)
        if recipe_kg <= 0 or not _retsept_materiali(ing, recipe):
            continue
        needed_kg = loy_kg * (recipe_kg / batch)
        inv_item = db.query(Inventory).filter(
            Inventory.id == ing.inventory_id,
            Inventory.company_id == recipe.company_id,
        ).with_for_update().first()
        if inv_item:
            inv_item.stock_quantity = float(inv_item.stock_quantity) + needed_kg
            log.append(f"{inv_item.item_name}: +{needed_kg:.2f} qaytarildi")
            import crud as _crud
            _crud.log_movement(
                db, inv_item.id, inv_item.item_name, movement_type="in",
                quantity=needed_kg, unit=inv_item.unit,
                reason=reason_override or f"Buyurtma {getattr(order, 'order_number', order.id)} bekor qilindi (loy qaytarildi)",
                order_id=order.id
            )

    if commit:
        db.commit()
    else:
        db.flush()
    return log


# ============================================================
# BUYURTMANI TAHRIRLASH — OMBORNI FARQ BO'YICHA TO'G'RILASH
# ============================================================

class _FakeItem:
    """Ombor hisobi uchun soxta detal (schema yoki dict dan)."""
    def __init__(self, d):
        self.category = d.get('category')
        self.width = d.get('width')
        self.thickness = d.get('thickness')
        self.length = d.get('length')
        self.quantity = d.get('quantity', 1)
        self.unit_price = d.get('unit_price', 0)
        self.unit_price_for_volume = d.get('unit_price_for_volume')
        self.penoplast_id = d.get('penoplast_id')
        self.price_per_m3 = d.get('price_per_m3')
        self.finished_product_id = d.get('finished_product_id')
        # Ichki qo'shimcha detallar — dict shaklida keladi (bevosita
        # _item_volume_m3/_sub_details_volume_m3 buni o'qiy oladi)
        self.sub_details = d.get('sub_details') or []
        # 126-band (kech96, O'LCHANGAN `work/probe126.py`): Donalik (eski usul — hajm narxdan) hajmi uchun
        # buyurtmaning "Asosiy narx"i. `_item_volume_m3` uni `item.order.base_price` dan o'qiydi — OrderItem
        # obyektida bor (yaratishda yechish, buyurtmani o'chirish), dict snapshotda YO'Q edi: to'liq / detal
        # tahriri, detalni o'chirish va yaratishdagi yetishlik tekshiruvi penoplast tannarxi zaxirasiga tushib,
        # hajmni boshqa qoida bilan hisoblardi (asosiy narx 1 000 000, tannarx 500 000 → farq IKKI baravar).
        _bp = d.get('order_base_price')
        self.order = _SnapshotBuyurtma(_bp) if _bp is not None else None


class _SnapshotBuyurtma:
    """126-band (kech96): `_FakeItem.order` — faqat `base_price` (hajm hisobi shuni o'qiydi)."""
    def __init__(self, base_price):
        self.base_price = base_price


def adjust_inventory_diff(db: Session, old_items, new_items, order_id: int = None,
                          company_id: int = None, commit: bool = True) -> list:
    """Eski va yangi detallarni solishtirib, ombordagi penoplastni
    faqat farq miqdorida to'g'rilaydi.

    old_items / new_items — OrderItem obyektlari yoki dict lar ro'yxati.

    kech41 (14-band): `commit=False` — faqat `flush`; chaqiruvchi qulf (101,
    buyurtma) ostida ishlasa, oraliq `commit` qulfni muddatidan OLDIN
    bo'shatmasin. O'LCHANGAN (PG): `delete_order_item` qulf olsa ham shu
    `commit` qulfni bo'shatar, parallel yetkazish detal hali o'chmagan holatni
    ko'rib, keyin FK xatosi (500) bilan yiqilardi.
    """
    import crud as _crud

    def _norm(items):
        out = []
        for it in items:
            out.append(_FakeItem(it) if isinstance(it, dict) else it)
        return out

    if company_id is None and order_id:
        from models import Order as _Ord
        company_id = db.query(_Ord.company_id).filter(_Ord.id == order_id).scalar()
    old_vol = _group_volumes_by_penoplast(db, _norm(old_items), company_id=company_id)
    new_vol = _group_volumes_by_penoplast(db, _norm(new_items), company_id=company_id)

    log = []
    all_ids = set(old_vol.keys()) | set(new_vol.keys())

    for pid in all_ids:
        old_v = old_vol.get(pid, 0.0)
        new_v = new_vol.get(pid, 0.0)
        diff = new_v - old_v          # + = ko'paydi, − = kamaydi

        if abs(diff) < 0.0001:
            continue

        p = _peno_of(db, pid, company_id, lock=True)
        if not p:
            continue

        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks = diff / vol_per_unit

        if blocks > 0:
            # 20-band (2026-09-21): 0 ga QIRQILMAYDI — `deduct_inventory_for_order`
            # bilan bir xil qoida (tanqislik yashirilmaydi, manfiy "qarz"
            # keyingi kirimda qoplanadi). Jurnalga ham to'liq `blocks` yoziladi.
            p.stock_quantity = float(p.stock_quantity) - blocks
            log.append(f"{p.item_name}: -{blocks:.2f} blok (qo'shildi)")
            # MUHIM: bu harakat AVVAL "Ombor harakatlari" jurnaliga yozilmasdi
            # — shuning uchun buyurtma tahrirlanganda Penoplast o'zgarishi
            # "yashirin" qolib, faqat oxirgi raqamda ko'rinib turardi.
            _crud.log_movement(db, pid, p.item_name, "out", blocks, unit="blok",
                                reason="Buyurtma tahrirlandi — qo'shimcha detal", order_id=order_id)
        else:
            p.stock_quantity = float(p.stock_quantity) + abs(blocks)
            log.append(f"{p.item_name}: +{abs(blocks):.2f} blok (qaytdi)")
            _crud.log_movement(db, pid, p.item_name, "in", abs(blocks), unit="blok",
                                reason="Buyurtma tahrirlandi — detal kamaytirildi/o'chirildi", order_id=order_id)

    if log:
        if commit:
            db.commit()
        else:
            db.flush()
    return log


def check_inventory_diff(db: Session, old_items, new_items, company_id: int = None) -> dict:
    """Tahrirlashdan keyin xomashyo yetadimi — tekshiradi."""

    def _norm(items):
        return [_FakeItem(it) if isinstance(it, dict) else it for it in items]

    old_vol = _group_volumes_by_penoplast(db, _norm(old_items), company_id=company_id)
    new_vol = _group_volumes_by_penoplast(db, _norm(new_items), company_id=company_id)

    shortages = []
    for pid in set(old_vol.keys()) | set(new_vol.keys()):
        diff = new_vol.get(pid, 0.0) - old_vol.get(pid, 0.0)
        if diff <= 0:
            continue
        p = _peno_of(db, pid, company_id)
        if not p:
            continue
        vol_per_unit = float(p.volume_per_unit or 1.0)
        blocks = diff / vol_per_unit
        if float(p.stock_quantity) < blocks:
            shortages.append(
                f"{p.item_name}: qo'shimcha {blocks:.1f} blok kerak, "
                f"qoldi {float(p.stock_quantity):.1f} blok"
            )

    return {"enough": len(shortages) == 0, "shortages": shortages}


def adjust_loy_diff(db: Session, order, old_loy: float, new_loy: float) -> list:
    """Loy rejasi o'zgarganda ombordagi xomashyoni to'g'rilaydi."""
    diff = float(new_loy or 0) - float(old_loy or 0)
    if abs(diff) < 0.01:
        return []

    log = []
    recipe = _get_order_recipe(db, order)

    # kech82 (102-band): buyurtma loyi — ko'payganda zaxira / xom manbasi yoziladi, kamayganda olingan joyiga qaytadi.
    with loy_manba_rejimi(db, "ushla"):
        if diff > 0:
            # Loy ko'paydi — farq uchun xomashyo ayiramiz
            log.extend(deduct_loy_ingredients(db, order, diff))
        else:
            # Loy kamaydi — farqni omborga qaytaramiz
            log.extend(return_loy_ingredients(db, order, abs(diff)))

    return log


def get_loy_cost_per_kg(db: Session, recipe_id: int = None,
                        company_id: int = None, narxlar: dict = None) -> dict:
    """Retsept bo'yicha 1 kg loyning tan narxi.

    ⚠ 2026-09-21: `company_id` YO'Q edi. Ikki xavf bor edi:
      1) berilgan `recipe_id` korxona bo'yicha tekshirilmasdi;
      2) retsept topilmasa `db.query(Recipe).first()` — BUTUN bazadagi
         birinchi retseptni olardi, ya'ni boshqa korxonanikini.
    O'lchangan: B korxona admini `/api/loy-cost` da A ning retsepti
    (`AAA_Rec`) va uning tan narxini ko'rdi."""

    # 2026-09-21 (2-tuzatish): qidiruv `resolve_recipe` ga o'tkazildi.
    # Sabab: bu yerdagi zaxira yo'l `company_id` BERILMAGANDA hamon
    # butun bazadan birinchi retseptni olardi — ya'ni himoya
    # chaqiruvchining esida saqlashiga bog'liq edi. Endi korxona
    # noma'lum bo'lsa zaxira yo'l umuman ishlamaydi.
    recipe = resolve_recipe(db, recipe_id=recipe_id, company_id=company_id)

    if not recipe:
        return {"cost_per_kg": 0, "recipe": None, "breakdown": []}

    batch = float(recipe.batch_size_kg or 100)

    cost = 0.0
    breakdown = []
    for ing in recipe.ingredients:
        kg = float(ing.quantity_kg or 0)
        inv = _retsept_materiali(ing, recipe)   # kech99 (112-band): begona ingredient — hisobga kirmaydi
        if kg <= 0 or not inv:
            continue
        # kech55 (34-band): `narxlar` berilsa ({inventory_id: 1 birlik narxi} —
        # buyurtmada ISHLATILGAN paytdagi narx, `_buyurtma_sarf_narxlari`) o'sha
        # narx; lug'atda yo'q material va `narxlar` berilmagan chaqiruv — JORIY
        # narx (avvalgi xulq AYNAN).
        _ing_narx = (float(narxlar[inv.id]) if (narxlar and inv.id in narxlar)
                     else float(inv.price_per_unit or 0))
        if _ing_narx:
            per_kg = (kg / batch) * _ing_narx
            cost += per_kg
            breakdown.append({
                "name": inv.item_name,
                "kg_per_batch": kg,
                "price": _ing_narx,
                "cost_per_kg": round(per_kg, 2)
            })

    recipe_name = recipe.name.value if hasattr(recipe.name, 'value') else str(recipe.name)
    return {
        "cost_per_kg": round(cost, 2),
        "recipe": recipe_name,
        "recipe_id": recipe.id,
        "batch_size": batch,
        "breakdown": breakdown
    }


# ============================================================
# USTA KPI VA HODIM TO'LOVI — Oylik hisobga qo'shish
# ============================================================

@_hisobot_keshi_bilan      # kech97 (111-band): alohida chaqirilganda ham buyurtma foydalari oldindan o'qiladi
def calculate_monthly_master_kpi(db: Session, year: int, month: int,
                                 company_id: int = None) -> dict:
    """Shu oy SOF FOYDASIDAN usta KPI xarajatini hisoblaydi (yillik jamlanadi,
    lekin har oy tegishli ulushi xarajat sifatida yoziladi)."""
    from models import Order, OrderStatus, Master, FinishedProductSale as _FPS_kpi

    # M5 (2026-09-18) — TENANT: ilgari barcha korxonalar ustalari
    # olinardi, ya'ni B ustasining KPI xarajati A ning oylik hisobiga
    # tushardi.
    _mq = db.query(Master).filter(Master.is_active == True, Master.kpi_percent > 0)
    if company_id is not None:
        _mq = _mq.filter(Master.company_id == company_id)
    masters = _mq.all()
    breakdown = []
    total = 0.0

    # kech97 (111-band, O'LCHANGAN `work/probe116.py`): oy buyurtmalari va TM sotuvlari usta boshiga ALOHIDA
    # so'ralardi (usta boshiga 2 so'rov; tarix — 12 oy). Endi bitta IN so'rovi bilan (o'sha shartlar), usta bo'yicha
    # guruhlanadi — har usta ro'yxati asl so'rovdagi tartibda (ORDER BY siz, baza tartibi).
    _mids = [m.id for m in masters]
    _buyurtma_oy, _sotuv_oy = {}, {}
    for _b in _hk_bolaklar(_mids):
        # MUHIM: o'chirilgan buyurtmalar ham hisobga olinadi — moliyaviy
        # tarix (shu jumladan Usta KPI hisobi) o'zgarmasligi kerak.
        _oq = db.query(Order).filter(
            Order.master_id.in_(_b),
            Order.status == OrderStatus.READY,
            _tashkent_oyida(Order.completed_at, year, month)
        )
        if company_id is not None:      # M5
            _oq = _oq.filter(Order.company_id == company_id)
        for _o in _oq.all():
            _buyurtma_oy.setdefault(_o.master_id, []).append(_o)
        for _s in db.query(_FPS_kpi).filter(
            _FPS_kpi.master_id.in_(_b),
            _tashkent_oyida(_FPS_kpi.sold_at, year, month)
        ).all():
            _sotuv_oy.setdefault(_s.master_id, []).append(_s)
    _hk_tayyorla(db, [o for _l in _buyurtma_oy.values() for o in _l])   # kech89 (52-band): hisobot ichida
    # kech102 (144-band, QAROR — usta KPI "yo'qotilgan foydaga"): shu oyda bo'lgan qaytarishlar o'sha buyurtma ustasining
    # foydasiga (qaytarilgan pul − omborga qaytgan tannarx); buyurtmaning o'zi — yakunlangan paytdagi holatda.
    _qaytarish_usta = {}
    for _h144 in davr_qaytarishlari(db, *_tashkent_oy_oraligi(year, month),
                                   company_id=company_id):
        _qaytarish_usta[_h144["master_id"]] = _qaytarish_usta.get(_h144["master_id"], 0.0) + _h144["foyda"]

    for m in masters:
        orders = _buyurtma_oy.get(m.id, [])

        monthly_profit = 0.0
        for o in orders:
            try:
                profit_data = yakun_foydasi(db, o)
                monthly_profit += float(profit_data.get("foyda", 0))
            except Exception as e:
                try:
                    import crud as _crud_log
                    _crud_log.log_error(db, str(e), endpoint=f"calculate_monthly_master_kpi:calculate_order_profit order#{o.id}")
                except Exception:
                    pass

        # MUHIM (2026-09): Tayyor mahsulot bo'limidan TO'G'RIDAN-TO'G'RI
        # (buyurtmasiz) sotilgan, lekin sotuv paytida shu ustaga
        # BIRIKTIRILGAN (master_id) sotuvlar — ular ham shu ustaning KPI
        # hisobiga qo'shiladi. Aks holda usta "Tayyor mahsulot" bo'limidan
        # to'g'ridan-to'g'ri xarid qilib sotsa, buyurtma ochilmagani uchun
        # KPI umuman hisoblanmay qolar edi.
        fp_sales = _sotuv_oy.get(m.id, [])
        monthly_profit += sum(float(s.total_amount or 0) - float(s.cost_amount or 0) for s in fp_sales)
        monthly_profit += _qaytarish_usta.get(m.id, 0.0)      # kech102 (144-band)

        if monthly_profit <= 0:
            continue

        kpi_amount = monthly_profit * m.kpi_percent / 100
        total += kpi_amount
        breakdown.append({
            "master_name": m.name,
            "kpi_percent": m.kpi_percent,
            "monthly_profit": round(monthly_profit),
            "kpi_amount": round(kpi_amount)
        })

    return {"total": round(total), "breakdown": breakdown}


def calculate_monthly_ehson(db: Session, year: int, month: int,
                            company_id: int = None) -> dict:
    """Shu oy SOF FOYDASIDAN — admin belgilagan foizga ko'ra — Ehson (xayriya)
    miqdorini hisoblaydi. Usta KPI bilan bir xil mantiqda, lekin bitta,
    umumiy (butun korxona) foiz asosida — har bir alohida usta emas.

    MUHIM: "monthly_profit" — Ehson foizi 0 bo'lsa ham HAR DOIM to'g'ri
    hisoblanadi (chunki bu qiymat, Moliyadagi "Buyurtmalardan foyda"
    ko'rsatkichi uchun ham ishlatiladi — Ehson yoqilgan-yoqilmaganidan
    qat'i nazar)."""
    from models import Order, OrderStatus
    import crud as _crud

    percent = float(_crud.get_setting(db, "ehson_percent", "0",
                                      company_id=company_id) or 0)

    # MUHIM: o'chirilgan buyurtmalar ham hisobga olinadi — moliyaviy
    # tarix (shu jumladan Ehson hisobi) o'zgarmasligi kerak.
    _oq = db.query(Order).filter(
        Order.status == OrderStatus.READY,
        _tashkent_oyida(Order.completed_at, year, month)
    )
    if company_id is not None:      # M5
        _oq = _oq.filter(Order.company_id == company_id)
    orders = _oq.all()
    _hk_tayyorla(db, orders)             # kech89 (52-band): hisobot ichida — allaqachon keshda

    monthly_profit = 0.0
    for o in orders:
        try:
            profit_data = yakun_foydasi(db, o)       # kech102 (144-band): yakunlangan paytdagi
            monthly_profit += float(profit_data.get("foyda", 0))
        except Exception as e:
            try:
                _crud.log_error(db, str(e), endpoint=f"calculate_monthly_ehson:calculate_order_profit order#{o.id}")
            except Exception:
                pass
    # kech102 (144-band, QAROR "Qaytarish oyida"): shu oyda bo'lgan qaytarishlar
    monthly_profit += sum(_h144["foyda"] for _h144 in davr_qaytarishlari(
        db, *_tashkent_oy_oraligi(year, month),
        company_id=company_id))

    # Tayyor mahsulot to'g'ridan-to'g'ri sotuvi ham —
    # bu ham korxonaning haqiqiy foydasi, Ehson shu foydadan hisoblanadi
    from models import FinishedProductSale as _FPS
    # 2026-09-18 — TENANT: bu funksiya `get_monthly_report` ICHIDAN
    # chaqiriladi (ehson xarajati), shuning uchun filtrsiz qolgan bu
    # so'rov FAIL-2 ning bir qismi edi — A ning sotuv foydasi B ning
    # ehson hisobiga qo'shilardi.
    _fpsq2 = db.query(_FPS).filter(
        _tashkent_oyida(_FPS.sold_at, year, month)
    )
    if company_id is not None:
        _fpsq2 = _fpsq2.filter(_FPS.company_id == company_id)
    fp_sales = _fpsq2.all()
    monthly_profit += sum(float(s.total_amount or 0) - float(s.cost_amount or 0) for s in fp_sales)

    if monthly_profit <= 0:
        return {"percent": percent, "monthly_profit": round(monthly_profit), "ehson_amount": 0}

    ehson_amount = monthly_profit * percent / 100
    return {"percent": percent, "monthly_profit": round(monthly_profit), "ehson_amount": round(ehson_amount)}


def calculate_monthly_employee_pay(db: Session, year: int, month: int,
                                   daromad: float, sof_foyda_before: float,
                                   jami_metr: float, jami_dona: float,
                                   jami_blok: float, jami_qoplama_birlik: float = 0.0,
                                   company_id: int = None) -> dict:
    """Moslashuvchan hodimlar uchun oylik to'lovni hisoblaydi.
    daromad, sof_foyda_before — shu oy uchun (hodim xarajatlarigacha).
    jami_metr/dona/blok — shu oy ishlab chiqarilgan miqdorlar (hammasi).
    jami_qoplama_birlik — shu oy QOPLANGAN detallar: metr + dona (profil/panel metrda,
    donali dona bilan, bittalashtirib qo'shilgan) — qoplamachi bonusi uchun."""
    from models import Employee, PayType
    import crud as _crud

    # MUHIM (2026-09): hodim, FAQAT allaqachon ISHGA KIRGAN oylar uchun
    # hisoblanishi kerak — aks holda, masalan Sentyabrda yangi qo'shilgan
    # hodim, tizim tomonidan, "Iyul/Avgust uchun ham qarzdormiz" deb,
    # NOTO'G'RI hisoblanib qolar edi (garchi u hali ishga kirmagan bo'lsa
    # ham). Shu oyning OXIRGI kunigacha ishga kirgan hodimlarni olamiz.
    # kech105 (9 + 50-band): oy oxiri — TOSHKENT kalendari (`hire_date` — UTC vaqt, standart `utcnow`; Toshkent 1-kun
    # 00:00–05:00 da qo'shilgan hodim o'tgan oy oyligiga ham tushardi). Oxiri KIRMAYDI.
    _month_end = _tashkent_oy_oraligi(year, month)[1]
    # M5 (2026-09-18) — TENANT: B korxonaning xodimi A ning oylik
    # to'lov hisobiga tushmasligi uchun.
    _eq = db.query(Employee).filter(
        Employee.is_active == True,
        Employee.is_deleted.isnot(True),
        Employee.hire_date < _month_end
    )
    if company_id is not None:
        _eq = _eq.filter(Employee.company_id == company_id)
    employees = _eq.all()
    breakdown = []
    total = 0.0

    unit_map = {
        "metr": jami_metr, "dona": jami_dona, "blok": jami_blok,
    }

    # kech97 (111-band, O'LCHANGAN `work/probe116.py`): to'lov tarixi, oylik tuzatish va avans hodim boshiga ALOHIDA
    # so'ralardi (hodim boshiga 4 so'rov; tarix — 12 oy). Endi hammasi bir necha IN / GROUP BY so'rovi bilan, tanlash
    # qoidasi AYNAN: to'lov tarixi — `crud._kompensatsiya_tanla` (yagona), tarix yo'q — hodimning joriy qiymatlari;
    # tuzatish — hodimning BIRINCHI yozuvi (eng kichik id — asl `.first()`); avans — bazadagi SUM.
    from models import EmployeeCompensationHistory, EmployeeMonthlyAdjustment, EmployeeAdvance
    from sqlalchemy import func as _func_oy
    _eids = [e.id for e in employees]
    _tarix_oy, _tuzatish_oy, _avans_oy = {}, {}, {}
    for _b in _hk_bolaklar(_eids):
        _tq = db.query(EmployeeCompensationHistory).filter(EmployeeCompensationHistory.employee_id.in_(_b))
        if company_id is not None:      # ota (hodim) orqali — ro'yxat allaqachon korxonaniki
            _tq = _tq.join(Employee, Employee.id == EmployeeCompensationHistory.employee_id).filter(
                Employee.company_id == company_id)
        for _r in _tq.all():
            _tarix_oy.setdefault(_r.employee_id, []).append(_r)
        _aq = db.query(EmployeeMonthlyAdjustment).filter(EmployeeMonthlyAdjustment.employee_id.in_(_b),
                                                        EmployeeMonthlyAdjustment.year == year,
                                                        EmployeeMonthlyAdjustment.month == month)
        if company_id is not None:
            _aq = _aq.join(Employee, Employee.id == EmployeeMonthlyAdjustment.employee_id).filter(
                Employee.company_id == company_id)
        for _r in _aq.order_by(EmployeeMonthlyAdjustment.id).all():
            _tuzatish_oy.setdefault(_r.employee_id, _r)
        _vq = db.query(EmployeeAdvance.employee_id, _func_oy.sum(EmployeeAdvance.amount)).filter(
            EmployeeAdvance.employee_id.in_(_b), _tashkent_oyida(EmployeeAdvance.date, year, month))
        if company_id is not None:
            _vq = _vq.join(Employee, Employee.id == EmployeeAdvance.employee_id).filter(
                Employee.company_id == company_id)
        for _eid, _s in _vq.group_by(EmployeeAdvance.employee_id).all():
            _avans_oy[_eid] = float(_s or 0)

    for e in employees:
        amount = 0.0
        detail = ""

        # MUHIM: e.fixed_amount/e.pay_type kabi JORIY qiymatlar EMAS —
        # aynan shu (year, month) uchun O'SHA PAYTDA amal qilgan to'lov
        # parametrlari olinadi. Shu sababli, oylik keyinchalik oshirilsa
        # ham, o'tgan oylarning hisob-kitobi o'zgarib qolmaydi.
        comp = _crud._kompensatsiya_tanla(_tarix_oy.get(e.id, []), year, month)
        if comp is None:
            comp = _crud._kompensatsiya_joriy(e)
        c_pay_type = comp["pay_type"]
        c_fixed = comp["fixed_amount"]
        c_percent = comp["percent_value"]
        c_unit_rate = comp["per_unit_rate"]
        c_unit_type = comp["per_unit_type"]
        c_extra_monthly = comp["extra_monthly"]

        if c_pay_type == PayType.FIXED:
            amount = float(c_fixed or 0)
            detail = f"Doimiy oylik"

        elif c_pay_type == PayType.PERCENT_SALES:
            amount = daromad * float(c_percent or 0) / 100
            detail = f"Sotuv {fmt_num(daromad)} × {c_percent}%"

        elif c_pay_type == PayType.PERCENT_PROFIT:
            amount = max(0, sof_foyda_before) * float(c_percent or 0) / 100
            detail = f"Foyda {fmt_num(sof_foyda_before)} × {c_percent}%"

        elif c_pay_type == PayType.PER_UNIT:
            qty = unit_map.get(c_unit_type, 0)
            amount = qty * float(c_unit_rate or 0)
            detail = f"{qty:g} {c_unit_type} × {fmt_num(c_unit_rate)}"

        elif c_pay_type == PayType.FIXED_PLUS_COATING:
            base = float(c_fixed or 0)
            rate = float(c_unit_rate or 1000)
            bonus = jami_qoplama_birlik * rate
            amount = base + bonus
            detail = f"Oylik {fmt_num(base)} + {jami_qoplama_birlik:g} metr/dona × {fmt_num(rate)} = {fmt_num(bonus)}"

        # Ixtiyoriy qo'shimcha doimiy oylik — istalgan to'lov turiga qo'shiladi
        if c_extra_monthly:
            amount += float(c_extra_monthly)
            extra_txt = f"qo'shimcha oylik {fmt_num(c_extra_monthly)}"
            detail = f"{detail} + {extra_txt}" if detail else extra_txt

        # QO'LDA KAMAYTIRISH — masalan kelmagan kunlar uchun (admin real
        # vaziyatni bilgan holda kiritadi, avtomatik formula EMAS).
        # QO'LDA BONUS — masalan yaxshi ishlagani uchun qo'shimcha rag'bat.
        # MUHIM: bu — Moliya, Hisobotlar bilan BIR XIL manbadan (shu
        # funksiyadan) o'qiladi, shuning uchun barcha joyda avtomatik sinxron.
        adjustment = 0.0
        adjustment_reason = None
        bonus = 0.0
        bonus_reason_val = None
        adj = _tuzatish_oy.get(e.id)
        if adj:
            if float(adj.reduction_amount or 0) > 0:
                adjustment = float(adj.reduction_amount)
                adjustment_reason = adj.reason
                amount = max(0, amount - adjustment)
                adj_txt = f"− {fmt_num(adjustment)} (kamaytirish{': ' + adjustment_reason if adjustment_reason else ''})"
                detail = f"{detail} {adj_txt}" if detail else adj_txt
            if float(adj.bonus_amount or 0) > 0:
                bonus = float(adj.bonus_amount)
                bonus_reason_val = adj.bonus_reason
                amount = amount + bonus
                bonus_txt = f"+ {fmt_num(bonus)} (bonus{': ' + bonus_reason_val if bonus_reason_val else ''})"
                detail = f"{detail} {bonus_txt}" if detail else bonus_txt

        # MUHIM: avval faqat "amount > 0" bo'lsa ro'yxatga qo'shilardi —
        # bu, agar "kamaytirish" hodimning butun oyligini "0"gacha
        # tushirib yuborsa (masalan butun oy kelmagan bo'lsa), hodimni
        # RO'YXATDAN BUTUNLAY YO'QOTIB YUBORARDI, va "Bonus/Kamaytirish"
        # tugmalari qayta bosib bo'lmaydigan holga kelardi (chunki
        # hodimning o'zi ko'rinmay qolardi). Endi — agar adjustment yoki
        # bonus qo'llanilgan bo'lsa, "amount=0" bo'lsa ham hodim ro'yxatda
        # qoladi (shunda uni yana ko'rish/tuzatish mumkin bo'ladi).
        if amount > 0 or adjustment > 0 or bonus > 0:
            total += amount
            avans = _avans_oy.get(e.id, 0.0)
            breakdown.append({
                "employee_id": e.id,
                "name": e.name,
                "position": e.position,
                "pay_type": c_pay_type.value,
                "detail": detail,
                "amount": round(amount),
                "avans": round(avans),
                "qolgan": round(amount - avans),
                "adjustment": round(adjustment) if adjustment else 0,
                "adjustment_reason": adjustment_reason,
                "bonus": round(bonus) if bonus else 0,
                "bonus_reason": bonus_reason_val
            })

    return {"total": round(total), "breakdown": breakdown}


def hodim_oylik_xulosa(db: Session, employee_id: int, company_id: int) -> dict:
    """kech118 (D-1, G6-21 — egasi QARORI «Oylik ko'rinsin»): hodim panelidagi «Oyligim» — joriy (Toshkent) va o'tgan oy:
    hisoblangan (bonus va kamaytirish bilan), olingan (shu oyga yozilgan avans va to'lovlar), qolgan. Raqamlar — admin
    Hisobot / Moliya / «Kimga qarzmiz» bilan AYNAN bitta manbadan (`get_monthly_report` → `hodimlar_moslashuvchan_breakdown`,
    `calculate_monthly_employee_pay`). Hisob TAFSILOTI (korxona sotuvi / foydasi summasi) BERILMAYDI — faqat hodimning
    o'z raqamlari. Oyga hali ishga kirmagan (hisob ham, to'lov ham yo'q) o'tgan oy ko'rsatilmaydi."""
    OY = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]
    bugun = _tashkent_date()
    y, m = bugun.year, bugun.month
    oylar = []
    for i in range(2):
        rep = get_monthly_report(db, y, m, company_id=company_id)
        e = next((r for r in rep.get("hodimlar_moslashuvchan_breakdown", []) if r.get("employee_id") == employee_id), None)
        tolovlar = get_employee_advances_list(db, employee_id, y, m)
        if i == 0 or e is not None or tolovlar:
            hisob = float(e["amount"]) if e else 0.0
            olingan = float(e["avans"]) if e else float(round(sum(t["amount"] for t in tolovlar)))
            oylar.append({
                "yil": y, "oy": m, "nomi": f"{OY[m]} {y}", "joriy": i == 0,
                "hisoblangan": round(hisob),
                "olingan": round(olingan),
                "qolgan": round(float(e["qolgan"]) if e else hisob - olingan),
                "bonus": round(float(e.get("bonus") or 0)) if e else 0,
                "bonus_sababi": (e.get("bonus_reason") or None) if e else None,
                "kamaytirish": round(float(e.get("adjustment") or 0)) if e else 0,
                "kamaytirish_sababi": (e.get("adjustment_reason") or None) if e else None,
                "tolovlar": [{"sana": t["date"], "summa": round(float(t["amount"] or 0))} for t in tolovlar],
            })
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return {"oylar": oylar}


def get_employee_advances_total(db: Session, employee_id: int, year: int, month: int) -> float:
    """Hodimga shu OYda berilgan barcha avanslar yig'indisi."""
    from models import EmployeeAdvance
    from sqlalchemy import func as _func

    total = db.query(_func.sum(EmployeeAdvance.amount)).filter(
        EmployeeAdvance.employee_id == employee_id,
        _tashkent_oyida(EmployeeAdvance.date, year, month)
    ).scalar()
    return float(total or 0)


def get_employee_advances_list(db: Session, employee_id: int, year: int, month: int) -> list:
    """Hodimga shu OYda berilgan barcha avanslar ro'yxati (sana, summa, izoh bilan)."""
    from models import EmployeeAdvance

    rows = db.query(EmployeeAdvance).filter(
        EmployeeAdvance.employee_id == employee_id,
        _tashkent_oyida(EmployeeAdvance.date, year, month)
    ).order_by(EmployeeAdvance.date.desc()).all()
    return [{
        "id": r.id,
        "amount": float(r.amount or 0),
        "date": r.date.isoformat() if r.date else None,
        "notes": r.notes,
        "given_by": r.given_by
    } for r in rows]


def fmt_num(n):
    try:
        return f"{n:,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def get_order_item_unit_cost(db: Session, order, item, include_coating: bool = True,
                             muzlatilgan: bool = False) -> float:
    """Bitta detalning 1 birlik (metr/dona) TAN NARXI — penoplast + (agar
    include_coating=True bo'lsa) loy. Brak qiymatini hisoblash uchun —
    sotuv narxi emas, xomashyo qiymati.
    include_coating=False — faqat Penoplast (loy hali tortilmagan holat uchun).

    kech55 (5-bo'lim 34-band, O'LCHANGAN — `work/probe56.py`): muzlatilgan=True —
    xomashyo shu buyurtmada ISHLATILGAN paytdagi narxda (`_buyurtma_sarf_narxlari`,
    32-band qarori "ishlatilgan paytdagi narxda muzlatilsin" bilan bir xil manba);
    MRP mahsuloti — ishlab chiqarish suratidagi narxda (`unit_price_at_time`).
    Faqat QAYTGAN mahsulot tannarxi uchun (`crud.add_returned_to_stock`): aks holda
    narx oshgandan keyin qaytgan 2 m (5 000 so'm/m ga qilingan) 30 000 so'm tannarx
    bilan omborga tushib, sotuv / kamaytirishda foydani sun'iy kamaytirardi.
    Brak summasi va oldindan ko'rish — JORIY narx (13-band 2-qadam), muzlatilgan=False.
    Jurnali yo'q eski buyurtma / surat narxisiz qator — joriy narx (taxmin qilinmaydi)."""

    if getattr(item, 'finished_product_id', None):
        # FASA 4B: avval bu yerda `cost_price / produced_quantity` ishlatilardi
        # — bu sotish (`cost_price / joriy_qoldiq`) va buyurtmaga olish/qaytarish
        # (xomashyoning JONLI narxidan hisoblangan `_fp_stable_unit_cost`)dagi
        # formuladan farq qilardi, ya'ni bitta mahsulotning "1 birlik tan narxi"
        # UCH XIL joyda UCH XIL son bo'lardi. Endi hammasi BITTA manbadan —
        # xomashyoning joriy narxidan hisoblanadigan _fp_stable_unit_cost'dan.
        from models import FinishedProduct
        # M4 (2026-09-18) — TENANT: tan narx manbasi buyurtmaning O'Z
        # korxonasidagi mahsulot bo'lishi shart.
        _ucq = db.query(FinishedProduct).filter(FinishedProduct.id == item.finished_product_id)
        _uc_cid = getattr(order, 'company_id', None)
        if _uc_cid is not None:
            _ucq = _ucq.filter(FinishedProduct.company_id == _uc_cid)
        fp = _ucq.first()
        if fp:
            import crud as _crud_unitcost
            # kech103 (56-band): muzlatilgan (omborga qaytgan mahsulot tannarxi — 34-band) — detal OLINGAN paytdagi
            # birlik (`fp_unit_cost`); ilgari TM ning JORIY o'rtachasi (5 m: 44 909, olingani 38 000). Brak summasi
            # (muzlatilgan=False) — avvalgidek joriy (13-band 2-qadam).
            _c56 = _crud_unitcost._tm_detal_birligi(item) if muzlatilgan else None
            if _c56 is not None:
                return _c56
            unit_cost = _crud_unitcost._fp_stable_unit_cost(db, fp)
            if unit_cost > 0:
                return unit_cost
            # Orqaga moslik: xomashyo ma'lumoti yo'q (eski/oddiy) yozuvlar uchun
            base_qty = float(fp.produced_quantity if fp.produced_quantity is not None else (fp.quantity or 0))
            if base_qty > 0 and fp.cost_price:
                return float(fp.cost_price) / base_qty
        return 0.0

    _ucid = getattr(order, 'company_id', None) or getattr(item, 'company_id', None)
    # kech55 (34-band): muzlatilgan narxlar (faqat muzlatilgan=True da; aks holda bo'sh — joriy narx).
    _mz_narx = _buyurtma_sarf_narxlari(db, order) if (muzlatilgan and order is not None) else {}
    # kech54 (13-band, 5-qadam): MRP mahsuloti — retsept suratidagi xomashyo JORIY narxda
    # (brak yozilgan paytdagi narx); surat yo'q — 0 (brak baribir rad etiladi).
    if (getattr(item, 'category', None) or '').lower() == 'mrp_product':
        _mz_surat = {} if muzlatilgan else None
        _msarf = _mrp_birlik_sarfi(db, _ucid, order_item=item, qoplama=include_coating,
                                   surat_narxlari=_mz_surat)
        _mz_mrp = {k: v / m for k, (m, v) in (_mz_surat or {}).items() if m > 0}
        return round(_mrp_sarf_qiymati(db, _msarf, _ucid, narxlar=_mz_mrp)) if _msarf else 0.0
    default_p = get_default_penoplast(db, company_id=_ucid)
    pid = item.penoplast_id or (default_p.id if default_p else None)
    volume = _item_volume_m3(db, item, default_p,
                             penoplast_narxi=(_mz_narx.get(pid) if pid else None), company_id=_ucid)   # kech99

    peno_cost_total = 0.0
    if volume > 0 and pid:
        p = _peno_of(db, pid, _ucid)
        if p and p.volume_per_unit:
            blocks = volume / float(p.volume_per_unit)
            _blok_narx = _mz_narx.get(p.id)
            peno_cost_total = blocks * (float(_blok_narx) if _blok_narx is not None
                                        else float(p.price_per_unit or 0))

    qty_units = item.order_qty_normalized
    peno_cost_per_unit = (peno_cost_total / qty_units) if qty_units > 0 else 0.0

    loy_cost_per_unit = 0.0
    if include_coating and item.is_coated and order:
        # kech58 (K58-1, 43-band): brak summasidagi loy narxi — buyurtma loyi YECHILGAN
        # retseptdan (brak yechimi va buyurtma yechimi bilan BITTA manba).
        _qr58 = resolve_recipe(db, order=order, company_id=getattr(order, 'company_id', None))
        recipe_id = _qr58.id if _qr58 else None

        # kech54 (41-band): 1 birlik loyi — qoplama narxi ulushi bo'yicha (`_brak_loyi_birlikka`)
        loy_kg_per_unit = _brak_loyi_birlikka(order, item)
        if loy_kg_per_unit > 0:
            # 2026-09-21 — TENANT: korxona buyurtmaning O'ZIDAN olinadi.
            loy_info = get_loy_cost_per_kg(
                db, recipe_id, company_id=getattr(order, 'company_id', None),
                narxlar=_mz_narx or None)
            loy_cost_per_unit = loy_kg_per_unit * float(loy_info.get("cost_per_kg", 0))

    return round(peno_cost_per_unit + loy_cost_per_unit)
