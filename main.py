"""
PenoDecorPro ERP — Asosiy server
=================================
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Request, Depends, HTTPException, Form, UploadFile, File, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import init_database, get_db
import schemas
import crud
import services
import auth
from models import UserRole, Inventory, OrderStatus

# 2026-09-16: Dinamik Ishlab chiqarish (Production/MRP) moduli — ATAYLAB
# alohida fayllarda (production_models.py, production_routes.py va h.k.),
# main.py'ni yanada kattalashtirmaslik uchun. Bu import — yangi jadvallar
# (companies, product_types, boms, bom_items, production_orders) pastdagi
# init_database() chaqirilganda AVTOMATIK yaratilishi uchun SHART
# (Base.metadata barcha modellarni "ko'rishi" kerak).
import production_models
from production_routes import router as production_router
import production_service

import urllib.request
import json as _json

TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_COATING_ID = "8461987934"
# Webhook xavfsizligi — Telegram har bir xabarga shu "imzo"ni qo'shib yuboradi
# (agar ro'yxatdan o'tkazilgan bo'lsa). Agar env varda o'rnatilmagan bo'lsa,
# tizim ishlashda davom etadi, lekin imzo tekshiruvi o'chirilgan holda
# (eski xatti-harakat saqlanadi — hech narsa buzilmaydi).
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

def fmt_money(n) -> str:
    """1234567.5 -> '1 234 568'"""
    try:
        return f"{round(float(n)):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def _tenant_telegram(company_id=None):
    """Joriy korxonaning Telegram sozlamasini qaytaradi (Faza 3, 2-qadam).

    Qaytaradi: (token, [chat_id, ...])

    TARTIB:
      1) `company_id` berilsa — o'sha korxonaning sozlamasi;
      2) berilmasa — joriy so'rovning korxonasi (`tenant_context`);
      3) korxonada token sozlanmagan bo'lsa — MUHIT O'ZGARUVCHILARI
         (`TELEGRAM_BOT_TOKEN`, `BACKUP_TELEGRAM_CHAT_ID`).

    3-band ATAYLAB: birinchi korxona (tizim egasi) hech narsa
    sozlamasdan ham avvalgidek ishlashda davom etadi. Ikkinchi mijoz
    esa @BotFather dan o'z botini olib, sozlamalarga qo'yadi va o'z
    xabarlarini O'Z botidan oladi.
    """
    env_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    env_chats = os.environ.get("BACKUP_TELEGRAM_CHAT_ID", "").strip()

    cid = company_id
    _db = None
    try:
        from database import SessionLocal as _SL
        _db = _SL()
        if cid is None:
            try:
                import tenant_context as _tc
                cid = _tc.get_current_company(_db)
            except Exception:
                cid = None
        if cid is not None:
            import crud as _c
            t = (_c.get_setting(_db, "telegram_bot_token", "", company_id=cid) or "").strip()
            c = (_c.get_setting(_db, "telegram_chat_id", "", company_id=cid) or "").strip()
            if t:
                chats = [x.strip() for x in c.split(",") if x.strip()]
                return t, chats
    except Exception as e:
        print(f"⚠ Korxona Telegram sozlamasi o'qilmadi: {e}")
    finally:
        if _db is not None:
            try:
                _db.close()
            except Exception:
                pass

    return env_token, [x.strip() for x in env_chats.split(",") if x.strip()]


def _send_telegram(text: str, company_id=None):
    token, _tenant_chats = _tenant_telegram(company_id)
    if not token:
        print("⚠ Telegram tokeni yo'q (korxona sozlamasi ham, muhit o'zgaruvchisi ham)")
        return
    # MUHIM (2026-08-18): avval, bu funksiya, ESKIRGAN/NOTO'G'RI bo'lib
    # qolgan, qattiq yozilgan TELEGRAM_COATING_ID'ga yuborardi (Telegram
    # "403 Forbidden" xatosi bilan qaytarardi — bot bloklangan yoki chat
    # o'chirilgan edi). Endi, zaxira nusxa uchun ALLAQACHON TO'G'RI
    # sozlangan, ishlab turgan BACKUP_TELEGRAM_CHAT_ID'dan foydalanamiz —
    # shu bilan, shu funksiyaga bog'liq BARCHA (12 xil) bildirishnoma turi
    # birdaniga tuzatiladi.
    chat_ids = _tenant_chats or [TELEGRAM_COATING_ID]
    for chat_id in chat_ids:
        try:
            url  = f"https://api.telegram.org/bot{token}/sendMessage"
            data = _json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
            print(f"✓ Telegram xabar yuborildi ({chat_id})")
        except Exception as e:
            print(f"⚠ Telegram xabar yuborilmadi ({chat_id}): {e}")


def _send_telegram_to(chat_id: str, text: str, company_id=None):
    """Aniq bir chatga xabar (mijoz, usta, qoplamachi).
    Bot tokeni — korxonanikidan, bo'lmasa muhit o'zgaruvchisidan."""
    token, _ = _tenant_telegram(company_id)
    if not token:
        print("⚠ Telegram tokeni yo'q")
        return
    try:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = _json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        print(f"✓ Telegram xabar yuborildi: {chat_id}")
    except Exception as e:
        print(f"⚠ Mijozga Telegram xabar yuborilmadi: {e}")

def _send_telegram_document(chat_id: str, file_bytes: bytes, filename: str, caption: str = "",
                             content_type: str = "application/json", company_id=None):
    """Telegram orqali fayl (masalan zaxira nusxa yoki Yuk xati PDF) yuboradi.
    content_type — fayl turiga mos qiymat berilishi kerak (masalan PDF uchun
    "application/pdf"); standart qiymat (application/json) — eski, zaxira
    nusxa funksiyasi bilan mos bo'lishi uchun saqlangan."""
    token, _ = _tenant_telegram(company_id)
    if not token or not chat_id:
        print("⚠ Telegram tokeni yoki chat_id yo'q — fayl yuborilmadi")
        return False
    try:
        import urllib.request as _ur

        boundary = "PenoDecorProBoundary1234567890"
        body = bytearray()

        def add_field(name, value):
            body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())

        add_field("chat_id", chat_id)
        if caption:
            add_field("caption", caption)

        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'.encode())
        body.extend(file_bytes)
        body.extend(f'\r\n--{boundary}--\r\n'.encode())

        url = f"https://api.telegram.org/bot{token}/sendDocument"
        req = _ur.Request(url, data=bytes(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            _ur.urlopen(req, timeout=30)
        except _ur.HTTPError as http_err:
            error_body = http_err.read().decode('utf-8', errors='replace')
            print(f"⚠ Telegram fayl yuborilmadi — server javobi: {error_body}")
            return False
        print(f"✓ Telegram fayl yuborildi: {filename}")
        return True
    except Exception as e:
        print(f"⚠ Telegram fayl yuborilmadi: {e}")
        return False


def _master_bot_keyboard(db, master=None) -> dict:
    """Usta boti uchun klaviatura — '🎁 Sovg'alar' tugmasi FAQAT faol
    sovg'a davri BOR va shu usta o'sha davrda ISHTIROK ETSA ko'rinadi
    (2026-09-12; ustalar tanlab olinishi qo'shildi 2026-09-12 kech)."""
    try:
        # M5: davr/ishtirok ustaning O'Z korxonasi ichida tekshiriladi.
        # (Telegram orqali topish usuli o'zgartirilmadi — F19.)
        show_gifts_btn = bool(master) and crud.master_in_active_gift_period(
            db, master.id, company_id=getattr(master, "company_id", None))
    except Exception:
        show_gifts_btn = False
    if show_gifts_btn:
        rows = [[{"text": "💰 Bonuslarim"}, {"text": "🎁 Sovg'alar"}], [{"text": "🪪 Mening ID raqamim"}]]
    else:
        rows = [[{"text": "💰 Bonuslarim"}, {"text": "🪪 Mening ID raqamim"}]]
    return {"keyboard": rows, "resize_keyboard": True, "persistent": True}


def _send_delivery_pdf_to_customer(db, delivery_id: int):
    """Yetkazish (delivery) uchun Yuk xati (nakladnoy) PDF faylini
    MUNTAZAM (har bir yetkazishda, istisnosiz) IKKITA mumkin bo'lgan
    qabul qiluvchiga yuboradi:

      1) Mijoz — agar loyihada Telegram ID ko'rsatilgan bo'lsa
         ("tg_id=..." — Loyihalar sahifasida kiritiladi).
      2) Usta — agar buyurtmaga usta biriktirilgan bo'lsa VA o'sha
         ustaning Telegram ID'si (botga yozib, administratorga
         ro'yxatdan o'tkazgan bo'lsa — Master.telegram_id) mavjud bo'lsa.

    MUHIM: bu ikkovi BUTUNLAY MUSTAQIL, bir-biriga hech qanday bog'liqligi
    yo'q — loyihaning "Mijoz Telegram ID"si (projects.notes ustunida) va
    ustaning telegram_id'si (masters.telegram_id ustunida) — ikki xil
    jadvalning ikki xil ustuni, hech qachon aralashib/to'qnashib qolmaydi.
    Ikkalasi ham yo'q bo'lsa — jimgina hech narsa qilmaydi (ixtiyoriy).

    ZAXIRA YO'L (2026-09): PDF fayl sifatida yuborish HAR SAFAR, muntazam
    ravishda urinib ko'riladi (bu — asosiy, standart yo'l). Faqat AGAR
    biror TEXNIK sabab bilan (masalan PDF kutubxonasi xato bersa, fayl
    juda katta bo'lsa, Telegram vaqtincha javob bermasa) muvaffaqiyatsiz
    bo'lsa — o'sha bitta qabul qiluvchi uchun (boshqasiga ta'sir qilmasdan)
    o'rniga xuddi shu ma'lumot bilan ODDIY MATN xabar yuboriladi, shunda
    hech kim butunlay xabarsiz qolmaydi."""
    try:
        # Ichki yordamchi: tenant tekshiruvi CHAQIRUVCHI endpointda
        # allaqachon bajarilgan (u yerda get_delivery company_id bilan
        # chaqiriladi). Bu yerda current_user yo'q.
        d = crud.get_delivery(db, delivery_id)
        if not d or not d.order:
            return

        recipients = []  # [(tg_id, rol)]

        project = d.order.project
        if project and project.notes and 'tg_id=' in project.notes:
            c_tg_id = project.notes.split('tg_id=')[1].split(',')[0].strip()
            if c_tg_id and c_tg_id.lstrip('-').isdigit():
                recipients.append((c_tg_id, "mijoz"))

        master = d.order.master
        if master:
            m_tg_id = getattr(master, 'telegram_id', None)
            m_tg_id = str(m_tg_id).strip() if m_tg_id else ''
            if m_tg_id and m_tg_id.lstrip('-').isdigit():
                recipients.append((m_tg_id, "usta"))

        if not recipients:
            return

        client = project.client_name if project else "—"
        lines = []
        for di in d.items:
            nm = di.order_item.name if di.order_item else "—"
            lines.append(f"• {nm}: {di.quantity:g} {di.unit}")

        # PDF — BIR MARTA generatsiya qilinadi, ikkala qabul qiluvchiga ham
        # (kerak bo'lsa) shu bitta fayl yuboriladi (ortiqcha ish qilinmaydi).
        pdf_bytes = None
        try:
            import delivery_pdf
            pdf_bytes = delivery_pdf.generate_delivery_pdf(d, db)
        except Exception as e:
            print(f"⚠ Yuk xati PDF generatsiya xatosi — matn bilan almashtiramiz: {e}")
            try:
                crud.log_error(db, str(e), endpoint="_send_delivery_pdf_to_customer:pdf")
            except Exception:
                pass

        filename = f"nakladnoy_{d.delivery_number.replace('/', '_')}.pdf"
        caption = (
            f"📄 Yuk xati — {d.delivery_number}\n"
            f"👤 Mijoz: {client}\n"
            f"📋 Buyurtma: {d.order.order_number}\n"
            f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        text_msg = (
            f"📦 *Yuk xati* — {d.delivery_number}\n\n"
            f"👤 Mijoz: {client}\n"
            f"📋 Buyurtma: {d.order.order_number}\n\n"
            + "\n".join(lines)
            + "\n\n⚠️ Texnik sabab bilan PDF fayl yuborib bo'lmadi — shuning "
              "uchun ma'lumot matn ko'rinishida yuborildi.\n"
            + f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        for tg_id, role in recipients:
            sent = False
            if pdf_bytes is not None:
                sent = _send_telegram_document(tg_id, pdf_bytes, filename, caption, content_type="application/pdf")
            if not sent:
                _send_telegram_to(tg_id, text_msg)
    except Exception as e:
        print(f"⚠ Yuk xati (PDF ham, matn ham) yuborilmadi: {e}")
        try:
            crud.log_error(db, str(e), endpoint="_send_delivery_pdf_to_customer")
        except Exception:
            pass


init_database()


def _seed_default_company():
    """2026-09-16: yangi Production moduli uchun — SaaS'gacha ishlatiladigan
    YAGONA korxona yozuvini (id=1) bir marta yaratib qo'yadi. Xatoni
    boshqa init funksiyalari kabi yutib yuboradi — agar biror sabab bilan
    ishlamasa, ilovaning QOLGAN qismi baribir ishlashda davom etishi kerak."""
    try:
        from database import SessionLocal as _SL
        from production_models import Company as _Company
        _db = _SL()
        try:
            if not _db.query(_Company).filter(_Company.id == 1).first():
                _db.add(_Company(id=1, name="PenodecorPro", allow_negative_stock=False))
                _db.commit()
                print("✅ Production moduli uchun asosiy Company (id=1) yaratildi")
        finally:
            _db.close()
    except Exception as e:
        print(f"⚠️ Company (id=1) seed qilishda xato (o'tkazib yuborildi): {e}")


_seed_default_company()


def _migrate_recipe_name_column():
    """ESKI QOLDIQ TUZATISH: bazada "recipes.name" ustuni, hozir kodda
    umuman mavjud bo'lmagan "recipetype" maxsus (enum) turi sifatida
    qolib ketgan edi (eski, allaqachon o'zgartirilgan versiyadan qolgan).
    Buni oddiy matn (VARCHAR) turiga o'tkazadi — aks holda retsept
    saqlashda "column is of type recipetype but expression is of type
    character varying" xatosi chiqadi."""
    from sqlalchemy import text
    try:
        from database import engine
    except ImportError:
        from database import SessionLocal
        engine = SessionLocal().get_bind()
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE recipes ALTER COLUMN name TYPE VARCHAR(100) USING name::text"
            ))
            conn.commit()
            print("✓ recipes.name ustuni VARCHAR turiga o'tkazildi")
    except Exception as e:
        msg = str(e)
        if 'does not exist' not in msg and 'already' not in msg.lower():
            print(f"⚠ recipes.name migratsiyasi: {e}")


def _migrate_payment_columns():
    """Mavjud bazaga to'lov ustunlarini qo'shadi (agar yo'q bo'lsa)."""
    from sqlalchemy import text, inspect
    try:
        from database import engine
    except ImportError:
        from database import SessionLocal
        engine = SessionLocal().get_bind()

    try:
        inspector = inspect(engine)
        cols = [c['name'] for c in inspector.get_columns('orders')]

        migrations = []
        if 'agreed_amount' not in cols:
            migrations.append("ALTER TABLE orders ADD COLUMN agreed_amount NUMERIC(12,2) DEFAULT 0")
        if 'payment_status' not in cols:
            migrations.append("ALTER TABLE orders ADD COLUMN payment_status VARCHAR(20) DEFAULT 'UNPAID'")
        if 'is_archived' not in cols:
            migrations.append("ALTER TABLE orders ADD COLUMN is_archived BOOLEAN DEFAULT FALSE")
        if 'closed_at' not in cols:
            migrations.append("ALTER TABLE orders ADD COLUMN closed_at TIMESTAMP")

        # Master — kpi_percent ustuni
        if 'masters' in inspector.get_table_names():
            master_cols = [c['name'] for c in inspector.get_columns('masters')]
            if 'kpi_percent' not in master_cols:
                migrations.append("ALTER TABLE masters ADD COLUMN kpi_percent FLOAT DEFAULT 0")

        # MonthlyExpense — soliqlar ustuni
        if 'monthly_expenses' in inspector.get_table_names():
            me_cols = [c['name'] for c in inspector.get_columns('monthly_expenses')]
            if 'soliqlar' not in me_cols:
                migrations.append("ALTER TABLE monthly_expenses ADD COLUMN soliqlar NUMERIC(12,2) DEFAULT 0")

        # RecurringObligation — created_at ustuni (2026-09: yangi qo'shilgan
        # majburiyat, undan OLDINGI oylar uchun "qarz" bo'lib chiqmasligi
        # uchun). Mavjud (eski) yozuvlarga, "hozirgi vaqt" emas, balki eng
        # ESKI mumkin bo'lgan sana (2020-01-01) qo'yiladi — shunda, ALLAQACHON
        # mavjud bo'lgan majburiyatlar, avvalgidek, barcha oylar uchun to'g'ri
        # hisoblanaveradi (faqat, YANGI qo'shiladiganlar cheklanadi).
        if 'recurring_obligations' in inspector.get_table_names():
            ro_cols = [c['name'] for c in inspector.get_columns('recurring_obligations')]
            if 'created_at' not in ro_cols:
                migrations.append("ALTER TABLE recurring_obligations ADD COLUMN created_at TIMESTAMP DEFAULT '2020-01-01'")

        # Inventory — category ustuni + avtomatik taxmin
        inv_cols_pre = [c['name'] for c in inspector.get_columns('inventory')]
        if 'category' not in inv_cols_pre:
            migrations.append("ALTER TABLE inventory ADD COLUMN category VARCHAR(50)")

        # InventoryPurchase — supplier ustunlari
        if 'inventory_purchases' in inspector.get_table_names():
            ip_cols = [c['name'] for c in inspector.get_columns('inventory_purchases')]
            if 'supplier_id' not in ip_cols:
                migrations.append("ALTER TABLE inventory_purchases ADD COLUMN supplier_id INTEGER")
            if 'is_credit' not in ip_cols:
                migrations.append("ALTER TABLE inventory_purchases ADD COLUMN is_credit BOOLEAN DEFAULT FALSE")
            if 'category' not in ip_cols:
                migrations.append("ALTER TABLE inventory_purchases ADD COLUMN category VARCHAR(50)")

        # Delivery — transport ustunlari
        if 'deliveries' in inspector.get_table_names():
            dlv_cols = [c['name'] for c in inspector.get_columns('deliveries')]
            if 'transport_carrier' not in dlv_cols:
                migrations.append("ALTER TABLE deliveries ADD COLUMN transport_carrier VARCHAR(150)")
            if 'transport_cost' not in dlv_cols:
                migrations.append("ALTER TABLE deliveries ADD COLUMN transport_cost NUMERIC(12,2) DEFAULT 0")
            if 'transport_payer' not in dlv_cols:
                migrations.append("ALTER TABLE deliveries ADD COLUMN transport_payer VARCHAR(20) DEFAULT 'none'")

        # FinishedProduct — production status va loy ustunlari
        if 'finished_products' in inspector.get_table_names():
            fp_cols = [c['name'] for c in inspector.get_columns('finished_products')]
            if 'planned_loy_kg' not in fp_cols:
                migrations.append("ALTER TABLE finished_products ADD COLUMN planned_loy_kg FLOAT DEFAULT 0")
            if 'actual_loy_kg' not in fp_cols:
                migrations.append("ALTER TABLE finished_products ADD COLUMN actual_loy_kg FLOAT")
            if 'production_status' not in fp_cols:
                migrations.append("ALTER TABLE finished_products ADD COLUMN production_status VARCHAR(20) DEFAULT 'READY'")
            if 'finished_production_at' not in fp_cols:
                migrations.append("ALTER TABLE finished_products ADD COLUMN finished_production_at TIMESTAMP")
            if 'unit_volume_m3' not in fp_cols:
                migrations.append("ALTER TABLE finished_products ADD COLUMN unit_volume_m3 FLOAT")
            if 'unit_loy_kg' not in fp_cols:
                migrations.append("ALTER TABLE finished_products ADD COLUMN unit_loy_kg FLOAT")
            # Eski loy_kg ustuni bo'lsa — planned_loy_kg ga ko'chiramiz
            if 'loy_kg' in fp_cols and 'planned_loy_kg' in fp_cols:
                migrations.append("UPDATE finished_products SET planned_loy_kg = loy_kg WHERE planned_loy_kg = 0 AND loy_kg > 0")

        # Inventory — penoplast ustunlari
        inv_cols = [c['name'] for c in inspector.get_columns('inventory')]
        if 'is_penoplast' not in inv_cols:
            migrations.append("ALTER TABLE inventory ADD COLUMN is_penoplast BOOLEAN DEFAULT FALSE")
        if 'is_default_penoplast' not in inv_cols:
            migrations.append("ALTER TABLE inventory ADD COLUMN is_default_penoplast BOOLEAN DEFAULT FALSE")

        # OrderItem — plotnost ustunlari
        oi_cols = [c['name'] for c in inspector.get_columns('order_items')]
        if 'penoplast_id' not in oi_cols:
            migrations.append("ALTER TABLE order_items ADD COLUMN penoplast_id INTEGER")
        if 'price_per_m3' not in oi_cols:
            migrations.append("ALTER TABLE order_items ADD COLUMN price_per_m3 NUMERIC(12,2)")
        if 'finished_product_id' not in oi_cols:
            migrations.append("ALTER TABLE order_items ADD COLUMN finished_product_id INTEGER")
        if 'unit_price_for_volume' not in oi_cols:
            migrations.append("ALTER TABLE order_items ADD COLUMN unit_price_for_volume NUMERIC(12,2)")

        ord_cols = [c['name'] for c in inspector.get_columns('orders')]
        if 'actual_loy_kg' not in ord_cols:
            migrations.append("ALTER TABLE orders ADD COLUMN actual_loy_kg FLOAT")
        if 'base_price' not in ord_cols:
            migrations.append("ALTER TABLE orders ADD COLUMN base_price NUMERIC(12,2)")
        if 'planned_loy_kg' not in ord_cols:
            migrations.append("ALTER TABLE orders ADD COLUMN planned_loy_kg FLOAT")

        fps_cols = [c['name'] for c in inspector.get_columns('finished_product_sales')]
        if 'sale_group_id' not in fps_cols:
            migrations.append("ALTER TABLE finished_product_sales ADD COLUMN sale_group_id VARCHAR(40)")
        if 'original_total' not in fps_cols:
            migrations.append("ALTER TABLE finished_product_sales ADD COLUMN original_total NUMERIC(12,2)")
        if 'group_discount_percent' not in fps_cols:
            migrations.append("ALTER TABLE finished_product_sales ADD COLUMN group_discount_percent FLOAT")

        emp_cols = [c['name'] for c in inspector.get_columns('employees')]
        if 'extra_monthly' not in emp_cols:
            migrations.append("ALTER TABLE employees ADD COLUMN extra_monthly NUMERIC(12,2)")

        et_cols = [c['name'] for c in inspector.get_columns('expense_transactions')]
        if 'production_type' not in et_cols:
            migrations.append("ALTER TABLE expense_transactions ADD COLUMN production_type VARCHAR(20)")

        te_cols = [c['name'] for c in inspector.get_columns('transport_expenses')]
        if 'production_type' not in te_cols:
            migrations.append("ALTER TABLE transport_expenses ADD COLUMN production_type VARCHAR(20)")

        fp_cols = [c['name'] for c in inspector.get_columns('finished_products')]
        if 'produced_quantity' not in fp_cols:
            migrations.append("ALTER TABLE finished_products ADD COLUMN produced_quantity FLOAT")
        if 'price_per_m3' not in fp_cols:
            migrations.append("ALTER TABLE finished_products ADD COLUMN price_per_m3 FLOAT")
        if 'bazalt_item_id' not in fp_cols:
            migrations.append("ALTER TABLE finished_products ADD COLUMN bazalt_item_id INTEGER")
        if 'unit_loy_kg' not in fp_cols:
            migrations.append("ALTER TABLE finished_products ADD COLUMN unit_loy_kg FLOAT")
        if 'unit_volume_m3' not in fp_cols:
            migrations.append("ALTER TABLE finished_products ADD COLUMN unit_volume_m3 FLOAT")

        # finished_product_sales.finished_product_id — NULL bo'la olishi kerak
        # (mahsulot o'chirilganda sotuv yozuvi uziladi, tarix saqlanadi).
        migrations.append("ALTER TABLE finished_product_sales ALTER COLUMN finished_product_id DROP NOT NULL")
        migrations.append("ALTER TABLE finished_product_losses ALTER COLUMN finished_product_id DROP NOT NULL")
        # MUHIM: bu backfill — ustun YANGI yaratilganidan qat'iy nazar, HAR
        # DOIM tekshiriladi (chunki ustun avvalroq qo'shilgan, lekin
        # to'ldirilmagan bo'lishi mumkin). Eski, "Sotuvga tayyor" yozuvlar
        # uchun, hozirgi qoldiqni "asl ishlab chiqarilgan" deb belgilaymiz —
        # bu nuqtadan boshlab, hodim haqi endi yana kamayib ketmaydi.
        # 2026-09-19 — TUZATISH: bu so'rov har ishga tushishda yiqilardi.
        # `production_status` — PostgreSQL enum va unda qiymat KATTA harf
        # bilan ('READY') saqlanadi; bu yerda 'ready' yozilgani uchun
        # "invalid input value for enum productionstatus" xatosi chiqardi.
        # Yiqilgan so'rov tranzaksiyani buzardi va KEYINGI IKKI migratsiya
        # ham umuman bajarilmay qolardi (pastdagi rollback tuzatishiga qarang).
        migrations.append(
            "UPDATE finished_products SET produced_quantity = quantity "
            "WHERE produced_quantity IS NULL AND production_status = 'READY'"
        )

        emp_cols2 = [c['name'] for c in inspector.get_columns('employees')]
        if 'production_type' not in emp_cols2:
            migrations.append("ALTER TABLE employees ADD COLUMN production_type VARCHAR(20)")

        ir_cols = [c['name'] for c in inspector.get_columns('inventory_receipts')]
        if 'production_type' not in ir_cols:
            migrations.append("ALTER TABLE inventory_receipts ADD COLUMN production_type VARCHAR(20)")

        if 'employee_monthly_adjustments' in inspector.get_table_names():
            ema_cols = [c['name'] for c in inspector.get_columns('employee_monthly_adjustments')]
            if 'bonus_amount' not in ema_cols:
                migrations.append("ALTER TABLE employee_monthly_adjustments ADD COLUMN bonus_amount NUMERIC(12,2) DEFAULT 0")
            if 'bonus_reason' not in ema_cols:
                migrations.append("ALTER TABLE employee_monthly_adjustments ADD COLUMN bonus_reason TEXT")

        # Bir martalik: "Boshqa" kategoriyasidagi mavjud materiallarni
        # "Bazalt"ga o'tkazamiz (chunki bu bo'lim aslida faqat Bazalt bilan
        # bog'liq materiallar uchun ishlatilgan edi — aniqroq nom).
        migrations.append("UPDATE inventory SET category = 'Bazalt' WHERE category = 'Boshqa'")

        # return_items — endi ikkita manbadan brak yozish mumkin: buyurtmadan
        # (order_id) YOKI tayyor mahsulot ishlab chiqarishdan (finished_product_id).
        # Shuning uchun order_id endi MAJBURIY emas, va yangi ustun qo'shiladi.
        ri_cols = [c['name'] for c in inspector.get_columns('return_items')]
        if 'finished_product_id' not in ri_cols:
            migrations.append("ALTER TABLE return_items ADD COLUMN finished_product_id INTEGER")
        migrations.append("ALTER TABLE return_items ALTER COLUMN order_id DROP NOT NULL")

        if migrations:
            with engine.connect() as conn:
                for sql in migrations:
                    try:
                        conn.execute(text(sql))
                        conn.commit()
                        print(f"✓ Migratsiya: {sql[:60]}...")
                    except Exception as e:
                        # 2026-09-19 — MUHIM TUZATISH: ilgari bu yerda
                        # `rollback()` yo'q edi. PostgreSQL'da bitta so'rov
                        # yiqilsa tranzaksiya "aborted" holatiga o'tadi va
                        # SHU ULANISHDAGI keyingi BARCHA so'rovlar
                        # "current transaction is aborted" bilan rad etiladi.
                        # Ya'ni bitta xato butun ro'yxatning qolganini
                        # o'ldirardi — jonli logda aynan shu ko'rindi:
                        # `return_items.order_id DROP NOT NULL` hech qachon
                        # bajarilmagan edi.
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        print(f"⚠ Migratsiya o'tkazib yuborildi: {e}")

        # PostgreSQL enum ga yangi qiymatlarni qo'shish
        enum_additions = [
            ("orderstatus", "DRAFT"),
            ("paymentstatus", "UNPAID"),
            ("paymentstatus", "PARTIAL"),
            ("paymentstatus", "PAID"),
            ("paymenttype", "ZAKLAT"),
            ("paymenttype", "PARTIAL"),
            ("paymenttype", "FINAL"),
            ("paymentmethod", "CASH"),
            ("paymentmethod", "CARD"),
            ("paymentmethod", "TRANSFER"),
            ("stocksource", "PRODUCED"),
            ("stocksource", "RETURNED"),
            ("productionstatus", "IN_PROGRESS"),
            ("productionstatus", "READY"),
            ("paytype", "FIXED"),
            ("paytype", "PERCENT_SALES"),
            ("paytype", "PERCENT_PROFIT"),
            ("paytype", "PER_UNIT"),
            ("paytype", "FIXED_PLUS_COATING"),
            ("userrole", "WAREHOUSE"),
        ]
        for enum_name, value in enum_additions:
            try:
                with engine.connect() as conn:
                    # Enum mavjudligini tekshiramiz
                    exists = conn.execute(text(
                        "SELECT 1 FROM pg_type WHERE typname = :n"
                    ), {"n": enum_name}).scalar()
                    if not exists:
                        continue
                    conn.execute(text(
                        f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"
                    ))
                    conn.commit()
                    print(f"✓ Enum {enum_name} += {value}")
            except Exception as e:
                msg = str(e)
                if 'already exists' not in msg and 'does not exist' not in msg:
                    print(f"⚠ Enum {enum_name}.{value}: {e}")

        # agreed_amount bo'sh bo'lganlarni total_amount ga tenglashtiramiz
        with engine.connect() as conn:
            try:
                conn.execute(text(
                    "UPDATE orders SET agreed_amount = total_amount "
                    "WHERE agreed_amount IS NULL OR agreed_amount = 0"
                ))
                conn.commit()
            except Exception as e:
                # 2026-09-19: xatodan keyin ulanishni tozalaymiz — aks holda
                # PostgreSQL tranzaksiyani "aborted" holatiga o'tkazadi va shu
                # ulanishdagi KEYINGI migratsiyalar ham bajarilmay qoladi.
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    from database import SessionLocal as _SL
                    _ldb = _SL()
                    crud.log_error(_ldb, str(e), endpoint="_migrate_payment_columns")
                    _ldb.close()
                except Exception:
                    pass

            # Mavjud xomashyolarga kategoriya taxmin qilib qo'yamiz
            try:
                conn.execute(text("""
                    UPDATE inventory SET category = CASE
                        WHEN is_penoplast = TRUE OR LOWER(item_name) LIKE '%penoplast%' THEN 'Penoplast'
                        WHEN LOWER(item_name) LIKE '%akril%' OR LOWER(item_name) LIKE '%pva%'
                             OR LOWER(item_name) LIKE '%zagustitel%' OR LOWER(item_name) LIKE '%penogasitel%'
                             OR LOWER(item_name) LIKE '%texanol%' OR LOWER(item_name) LIKE '%biosid%'
                             OR LOWER(item_name) LIKE '%hpmc%' THEN 'Kimyoviy qo''shimchalar'
                        WHEN LOWER(item_name) LIKE '%qum%' OR LOWER(item_name) LIKE '%kroshka%'
                             OR LOWER(item_name) LIKE '%mel%' OR LOWER(item_name) LIKE '%kvars%'
                             OR LOWER(item_name) LIKE '%mikrokalsit%' OR LOWER(item_name) LIKE '%mikroklasit%' THEN 'Qattiq qotishmalar'
                        ELSE 'Boshqa'
                    END
                    WHERE category IS NULL
                """))
                conn.commit()
            except Exception as e:
                # 2026-09-19: xatodan keyin ulanishni tozalaymiz — aks holda
                # PostgreSQL tranzaksiyani "aborted" holatiga o'tkazadi va shu
                # ulanishdagi KEYINGI migratsiyalar ham bajarilmay qoladi.
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    from database import SessionLocal as _SL
                    _ldb = _SL()
                    crud.log_error(_ldb, str(e), endpoint="_migrate_payment_columns")
                    _ldb.close()
                except Exception:
                    pass

            # Eski kategoriya nomlarini yangi nomlarga o'tkazamiz (oldingi deploydan qolgan bo'lsa)
            try:
                conn.execute(text("UPDATE inventory SET category = 'Qattiq qotishmalar' WHERE category = 'Qumlar'"))
                conn.execute(text("""
                    UPDATE inventory SET category = CASE
                        WHEN LOWER(item_name) LIKE '%akril%' OR LOWER(item_name) LIKE '%pva%'
                             OR LOWER(item_name) LIKE '%zagustitel%' OR LOWER(item_name) LIKE '%penogasitel%' THEN 'Kimyoviy qo''shimchalar'
                        ELSE 'Qattiq qotishmalar'
                    END
                    WHERE category = 'Kimyoviy moddalar'
                """))
                conn.execute(text("UPDATE inventory_purchases SET category = 'Qattiq qotishmalar' WHERE category = 'Qumlar'"))
                conn.execute(text("""
                    UPDATE inventory_purchases SET category = CASE
                        WHEN LOWER(item_name) LIKE '%akril%' OR LOWER(item_name) LIKE '%pva%'
                             OR LOWER(item_name) LIKE '%zagustitel%' OR LOWER(item_name) LIKE '%penogasitel%' THEN 'Kimyoviy qo''shimchalar'
                        ELSE 'Qattiq qotishmalar'
                    END
                    WHERE category = 'Kimyoviy moddalar'
                """))

                # "Boshqa"da qolib ketganlarni yangi kalit so'zlar bo'yicha qayta tekshiramiz
                # (masalan Texanol/Biosid/HPMC/Mikrokalsit — fix qo'shilishidan oldin "Boshqa" bo'lib qolgan bo'lishi mumkin)
                conn.execute(text("""
                    UPDATE inventory SET category = 'Kimyoviy qo''shimchalar'
                    WHERE category = 'Boshqa' AND (
                        LOWER(item_name) LIKE '%texanol%' OR LOWER(item_name) LIKE '%biosid%'
                        OR LOWER(item_name) LIKE '%hpmc%' OR LOWER(item_name) LIKE '%akril%'
                        OR LOWER(item_name) LIKE '%pva%' OR LOWER(item_name) LIKE '%zagustitel%'
                        OR LOWER(item_name) LIKE '%penogasitel%'
                    )
                """))
                conn.execute(text("""
                    UPDATE inventory SET category = 'Qattiq qotishmalar'
                    WHERE category = 'Boshqa' AND (
                        LOWER(item_name) LIKE '%mikrokalsit%' OR LOWER(item_name) LIKE '%mikroklasit%'
                        OR LOWER(item_name) LIKE '%qum%' OR LOWER(item_name) LIKE '%kroshka%'
                        OR LOWER(item_name) LIKE '%mel%' OR LOWER(item_name) LIKE '%kvars%'
                    )
                """))
                conn.execute(text("""
                    UPDATE inventory_purchases SET category = 'Kimyoviy qo''shimchalar'
                    WHERE category = 'Boshqa' AND (
                        LOWER(item_name) LIKE '%texanol%' OR LOWER(item_name) LIKE '%biosid%'
                        OR LOWER(item_name) LIKE '%hpmc%' OR LOWER(item_name) LIKE '%akril%'
                        OR LOWER(item_name) LIKE '%pva%' OR LOWER(item_name) LIKE '%zagustitel%'
                        OR LOWER(item_name) LIKE '%penogasitel%'
                    )
                """))
                conn.execute(text("""
                    UPDATE inventory_purchases SET category = 'Qattiq qotishmalar'
                    WHERE category = 'Boshqa' AND (
                        LOWER(item_name) LIKE '%mikrokalsit%' OR LOWER(item_name) LIKE '%mikroklasit%'
                        OR LOWER(item_name) LIKE '%qum%' OR LOWER(item_name) LIKE '%kroshka%'
                        OR LOWER(item_name) LIKE '%mel%' OR LOWER(item_name) LIKE '%kvars%'
                    )
                """))
                conn.commit()
            except Exception as e:
                # 2026-09-19: xatodan keyin ulanishni tozalaymiz — aks holda
                # PostgreSQL tranzaksiyani "aborted" holatiga o'tkazadi va shu
                # ulanishdagi KEYINGI migratsiyalar ham bajarilmay qoladi.
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    from database import SessionLocal as _SL
                    _ldb = _SL()
                    crud.log_error(_ldb, str(e), endpoint="_migrate_payment_columns")
                    _ldb.close()
                except Exception:
                    pass

            # Panel detallar birligini metrga o'zgartiramiz (eski yozuvlar)
            try:
                conn.execute(text("""
                    UPDATE delivery_items SET unit = 'metr'
                    WHERE order_item_id IN (
                        SELECT id FROM order_items WHERE LOWER(category) = 'panel'
                    ) AND unit != 'metr'
                """))
                conn.commit()
            except Exception as e:
                # 2026-09-19: xatodan keyin ulanishni tozalaymiz — aks holda
                # PostgreSQL tranzaksiyani "aborted" holatiga o'tkazadi va shu
                # ulanishdagi KEYINGI migratsiyalar ham bajarilmay qoladi.
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    from database import SessionLocal as _SL
                    _ldb = _SL()
                    crud.log_error(_ldb, str(e), endpoint="_migrate_payment_columns")
                    _ldb.close()
                except Exception:
                    pass

            try:
                conn.execute(text("""
                    UPDATE finished_products SET unit = 'metr'
                    WHERE LOWER(category) = 'panel' AND unit != 'metr'
                """))
                conn.commit()
            except Exception as e:
                # 2026-09-19: xatodan keyin ulanishni tozalaymiz — aks holda
                # PostgreSQL tranzaksiyani "aborted" holatiga o'tkazadi va shu
                # ulanishdagi KEYINGI migratsiyalar ham bajarilmay qoladi.
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    from database import SessionLocal as _SL
                    _ldb = _SL()
                    crud.log_error(_ldb, str(e), endpoint="_migrate_payment_columns")
                    _ldb.close()
                except Exception:
                    pass

            # Mavjud "Penoplast" nomli pozitsiyalarni belgilaymiz
            try:
                conn.execute(text(
                    "UPDATE inventory SET is_penoplast = TRUE "
                    "WHERE LOWER(item_name) LIKE '%penoplast%' AND is_penoplast = FALSE"
                ))
                conn.commit()
            except Exception as e:
                # 2026-09-19: xatodan keyin ulanishni tozalaymiz — aks holda
                # PostgreSQL tranzaksiyani "aborted" holatiga o'tkazadi va shu
                # ulanishdagi KEYINGI migratsiyalar ham bajarilmay qoladi.
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    from database import SessionLocal as _SL
                    _ldb = _SL()
                    crud.log_error(_ldb, str(e), endpoint="_migrate_payment_columns")
                    _ldb.close()
                except Exception:
                    pass

            # Agar asosiy plotnost yo'q bo'lsa — birinchisini asosiy qilamiz
            try:
                r = conn.execute(text(
                    "SELECT COUNT(*) FROM inventory WHERE is_default_penoplast = TRUE"
                )).scalar()
                if not r:
                    conn.execute(text(
                        "UPDATE inventory SET is_default_penoplast = TRUE "
                        "WHERE id = (SELECT id FROM inventory WHERE is_penoplast = TRUE LIMIT 1)"
                    ))
                    conn.commit()
            except Exception as e:
                # 2026-09-19: xatodan keyin ulanishni tozalaymiz — aks holda
                # PostgreSQL tranzaksiyani "aborted" holatiga o'tkazadi va shu
                # ulanishdagi KEYINGI migratsiyalar ham bajarilmay qoladi.
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    from database import SessionLocal as _SL
                    _ldb = _SL()
                    crud.log_error(_ldb, str(e), endpoint="_migrate_payment_columns")
                    _ldb.close()
                except Exception:
                    pass
    except Exception as e:
        print(f"⚠ Migratsiya xatosi: {e}")


def _migrate_drop_company_id_defaults():
    """M8/F1 (2026-09-18) — VAQTINCHALIK `DEFAULT 1` ni olib tashlaydi.

    SaaS migratsiyasi boshlanganda 25 ta jadvalning `company_id` ustuniga
    vaqtinchalik `DEFAULT 1` qo'yilgan edi — shunda eski kod (hali
    `company_id` uzatmaydigan) ishlashda davom etardi. Endi barcha yozish
    yo'llari tenantni ANIQ beradi, shuning uchun bu default KERAK EMAS va
    XAVFLI: u unutilgan `company_id` ni jimgina 1-korxonaga yozib qo'yadi,
    ya'ni ma'lumot sizib chiqadi va hech qanday xato chiqmaydi. M4–M8
    davomida aynan shu naqsh BESH marta takrorlandi.

    Default olib tashlangach, unutilgan `company_id` darhol NOT NULL
    xatosi beradi — jim sizish o'rniga baland, ko'rinadigan nosozlik.

    XAVFSIZLIK QOIDALARI:
      • Faqat PostgreSQL'da ishlaydi (SQLite ALTER COLUMN ni qo'llamaydi).
      • AVVAL tekshiradi: birorta jadvalda `company_id IS NULL` bo'lsa yoki
        `companies` da mavjud bo'lmagan korxonaga ishora qilsa — HECH NARSA
        o'zgartirmaydi va sababini yozadi.
      • DDL faqat DEFAULT ni olib tashlaydi: qatorlar, qiymatlar va
        NOT NULL cheklovi TEGILMAYDI.
      • Idempotent: qayta-qayta ishga tushsa ham zarar yo'q.
    """
    TABLES = [
        "users", "masters", "master_gifts", "gift_periods", "inventory",
        "recipes", "projects", "orders", "order_items", "return_items",
        "inventory_movements", "inventory_receipts", "employees",
        "cash_transactions", "company_settings", "activity_logs",
        "login_history", "recurring_obligations", "suppliers",
        "transport_expenses", "finished_products", "finished_product_sales",
        "finished_product_losses", "expense_transactions", "monthly_expenses",
    ]
    # MUHIM (2026-09-19, Railway logidan aniqlangan): `text` bu faylning
    # global nomlar fazosida YO'Q. U import qilinmagani uchun bu migratsiya
    # har ishga tushishda jimgina "name 'text' is not defined" xatosi bilan
    # o'tkazib yuborilgan — ya'ni HECH QACHON bajarilmagan.
    from sqlalchemy import text
    try:
        from database import engine
        if engine.dialect.name != "postgresql":
            return   # SQLite (lokal sinov) — o'tkazib yuboriladi

        with engine.connect() as conn:
            # --- 1) Hozirgi holat: qaysi jadvalda default bor ---
            rows = conn.execute(text(
                "SELECT table_name, column_default FROM information_schema.columns "
                "WHERE table_schema='public' AND column_name='company_id' "
                "AND column_default IS NOT NULL"
            )).fetchall()
            bor = {r[0] for r in rows}
            if not bor:
                return   # allaqachon tozalangan — jim chiqamiz

            # --- 2) XAVFSIZLIK TEKSHIRUVI (DDL dan OLDIN) ---
            muammo = []
            for t in TABLES:
                if t not in bor:
                    continue
                n_null = conn.execute(text(
                    f"SELECT COUNT(*) FROM {t} WHERE company_id IS NULL")).scalar()
                if n_null:
                    muammo.append(f"{t}: {n_null} ta NULL company_id")
                n_yetim = conn.execute(text(
                    f"SELECT COUNT(*) FROM {t} c WHERE NOT EXISTS "
                    f"(SELECT 1 FROM companies k WHERE k.id = c.company_id)")).scalar()
                if n_yetim:
                    muammo.append(f"{t}: {n_yetim} ta yetim company_id")
            if muammo:
                print("⛔ DEFAULT 1 olib tashlanmadi — avval quyidagilar tuzatilsin:")
                for m in muammo:
                    print(f"   • {m}")
                return

            # --- 3) Qator sonlarini yozib olamiz (DDL ularga tegmasligi shart) ---
            oldin = {t: conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                     for t in TABLES if t in bor}

            # --- 4) DDL: faqat DEFAULT olib tashlanadi ---
            ozgardi = []
            for t in sorted(bor):
                if t not in TABLES:
                    continue   # ro'yxatda yo'q jadvalga TEGMAYMIZ
                conn.execute(text(f"ALTER TABLE {t} ALTER COLUMN company_id DROP DEFAULT"))
                ozgardi.append(t)
            conn.commit()

            # --- 5) Tekshirish: default yo'q, qatorlar o'zgarmagan ---
            qolgan = conn.execute(text(
                "SELECT table_name FROM information_schema.columns "
                "WHERE table_schema='public' AND column_name='company_id' "
                "AND column_default IS NOT NULL"
            )).fetchall()
            keyin = {t: conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                     for t in oldin}
            farq = {t: (oldin[t], keyin[t]) for t in oldin if oldin[t] != keyin[t]}

            print(f"✓ company_id DEFAULT olib tashlandi: {len(ozgardi)} ta jadval")
            if qolgan:
                print(f"⚠ Hamon default bor: {[r[0] for r in qolgan]}")
            if farq:
                print(f"⛔ QATOR SONI O'ZGARDI (kutilmagan!): {farq}")
    except Exception as e:
        print(f"⚠ company_id DEFAULT migratsiyasi o'tkazib yuborildi: {e}")


_migrate_recipe_name_column()
_migrate_payment_columns()
def _migrate_faza3_columns():
    """Faza 3 (2026-09-19) — uchta yangi ustun. Xavfsiz va idempotent.

      1) `error_logs.company_id`  — xatolarni korxonaga bog'lash uchun.
         NULL = platforma xatosi (fon vazifasi, login oldidagi xato).
         Eski yozuvlar NULL bo'lib qoladi: ularni korxonalarga taqsimlab
         bo'lmaydi (`performed_by` bo'sh edi), shuning uchun ular
         platforma xatosi sifatida qoladi — bu ATAYLAB.
      2) `gift_period_tiers.company_id` — model qo'riqchisi ota yozuvda
         shu ustunni qidiradi; backfill `gift_periods` dan olinadi.
      3) `users.is_platform_admin` — SaaS egasi bayrog'i. Backfill:
         ENG ESKI admin (eng kichik id) platforma admini deb belgilanadi,
         aks holda hech kim platforma amallarini bajara olmay qolardi.
    """
    from sqlalchemy import text   # yuqoridagi bilan bir xil sabab
    try:
        from database import engine
        if engine.dialect.name != "postgresql":
            return
        with engine.connect() as conn:
            def has_col(t, c):
                return conn.execute(text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
                ), {"t": t, "c": c}).first() is not None

            if not has_col("error_logs", "company_id"):
                conn.execute(text(
                    "ALTER TABLE error_logs ADD COLUMN company_id INTEGER "
                    "REFERENCES companies(id)"))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_error_logs_company_id "
                    "ON error_logs (company_id)"))
                conn.commit()
                print("✓ error_logs.company_id qo'shildi")

            if not has_col("gift_period_tiers", "company_id"):
                conn.execute(text(
                    "ALTER TABLE gift_period_tiers ADD COLUMN company_id INTEGER "
                    "REFERENCES companies(id)"))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_gift_period_tiers_company_id "
                    "ON gift_period_tiers (company_id)"))
                conn.commit()
                print("✓ gift_period_tiers.company_id qo'shildi")

            # TO'LDIRISH — ustun qo'shish bilan BIR BLOKDA emas, ALOHIDA va
            # IDEMPOTENT. Sabab (2026-09-19, jonli sinovda aniqlangan):
            # ustun qo'shilgan, lekin to'ldirish ishlamay qolgan edi va
            # qiymatlar NULL bo'lib qoldi. Global filtr esa NULL larni
            # kesib tashlaydi — natijada A korxonaning 7 ta sovg'a darajasi
            # interfeysdan butunlay yo'qoldi. Endi har ishga tushishda
            # to'ldirilmaganlari qayta to'ldiriladi.
            if has_col("gift_period_tiers", "company_id"):
                n_null = conn.execute(text(
                    "SELECT COUNT(*) FROM gift_period_tiers WHERE company_id IS NULL")).scalar()
                if n_null:
                    conn.execute(text(
                        "UPDATE gift_period_tiers t SET company_id = "
                        "(SELECT p.company_id FROM gift_periods p WHERE p.id = t.period_id) "
                        "WHERE t.company_id IS NULL"))
                    conn.commit()
                    qoldi = conn.execute(text(
                        "SELECT COUNT(*) FROM gift_period_tiers WHERE company_id IS NULL")).scalar()
                    print(f"✓ gift_period_tiers to'ldirildi: {n_null} ta, qolgani: {qoldi}")

            if not has_col("users", "is_platform_admin"):
                conn.execute(text(
                    "ALTER TABLE users ADD COLUMN is_platform_admin BOOLEAN "
                    "NOT NULL DEFAULT false"))
                conn.commit()
                print("✓ users.is_platform_admin qo'shildi")

            # PLATFORMA ADMINI — ham ALOHIDA va IDEMPOTENT.
            # Birinchi urinishda rol `'ADMIN'` deb qidirilgan edi, bazada
            # esa u kichik harf bilan (`'admin'`) saqlanadi — shu sababli
            # hech kim platforma admini bo'lmay qoldi va tizim egasining
            # o'zi ham platforma amallariga kira olmadi. Endi solishtirish
            # harf registriga bog'liq emas.
            # --- Korxona brendi: slogan, phone, address, logo_path ---
            for _ust, _tur in (("slogan", "VARCHAR(150)"),
                               ("phone", "VARCHAR(60)"),
                               ("address", "VARCHAR(200)"),
                               ("logo_path", "VARCHAR(255)")):
                if not has_col("companies", _ust):
                    try:
                        conn.execute(text(
                            f"ALTER TABLE companies ADD COLUMN {_ust} {_tur}"))
                        conn.commit()
                        print(f"✓ companies.{_ust} qo'shildi")
                    except Exception as _e:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        print(f"⚠ companies.{_ust} qo'shilmadi: {_e}")

            # Eng eski korxona (platforma egasi) uchun HOZIRGI brendni
            # biriktiramiz — logotip, shior, manzil, telefon. Aks holda
            # uning hujjatlari bu maydonlarsiz qolardi, chunki endi
            # zaxira qiymatlar faqat korxona noma'lum bo'lganda
            # ishlatiladi.
            # 2026-09-20 — TUZATISH: ilgari shart `logo_path IS NOT NULL`
            # edi. Oldingi deployda logotip allaqachon qo'yilgani uchun
            # shior/manzil/telefon to'ldirilmay qolgan va yuk xati
            # yiqilgan edi. Endi har bir maydon ALOHIDA to'ldiriladi
            # (faqat bo'sh bo'lsa) — amal idempotent.
            try:
                eng_eski = conn.execute(text(
                    "SELECT id FROM companies ORDER BY id LIMIT 1")).scalar()
                if eng_eski:
                    n_t = conn.execute(text(
                        "UPDATE companies SET "
                        "  logo_path = COALESCE(logo_path, 'static/logo_transparent.png'), "
                        "  slogan    = COALESCE(slogan, 'Fasad bezaklari'), "
                        "  address   = COALESCE(address, 'Andijon'), "
                        "  phone     = COALESCE(phone, '+998 97 999 57 57') "
                        "WHERE id = :i AND (logo_path IS NULL OR slogan IS NULL "
                        "                   OR address IS NULL OR phone IS NULL)"
                    ), {"i": eng_eski}).rowcount
                    conn.commit()
                    if n_t:
                        print(f"✓ Eng eski korxona (#{eng_eski}) brendi to'ldirildi")
            except Exception as _e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                print(f"⚠ logo_path biriktirilmadi: {_e}")

            # --- login_history.company_id: NOT NULL -> NULL ruxsat ---
            # 2026-09-20: noma'lum foydalanuvchi nomi bilan kirishga
            # urinilganda korxona aniqlanmaydi. `DEFAULT 1` olib
            # tashlangach `/login` 500 qaytara boshlagan edi.
            try:
                nn = conn.execute(text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name='login_history' "
                    "  AND column_name='company_id'")).scalar()
                if nn == "NO":
                    conn.execute(text(
                        "ALTER TABLE login_history ALTER COLUMN company_id DROP NOT NULL"))
                    conn.commit()
                    print("✓ login_history.company_id endi NULL qabul qiladi")
            except Exception as _e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                print(f"⚠ login_history.company_id o'zgartirilmadi: {_e}")

            # --- Master.telegram_id: global unique -> (company_id, telegram_id) ---
            # Ilgari bitta Telegram hisobi butun tizimda FAQAT BITTA usta
            # bo'la olardi — SaaS uchun to'g'ri emas.
            try:
                eski = conn.execute(text(
                    "SELECT conname FROM pg_constraint c "
                    "JOIN pg_class t ON t.oid = c.conrelid "
                    "WHERE t.relname = 'masters' AND c.contype = 'u' "
                    "  AND pg_get_constraintdef(c.oid) = 'UNIQUE (telegram_id)'"
                )).fetchall()
                for (cname,) in eski:
                    conn.execute(text(f'ALTER TABLE masters DROP CONSTRAINT "{cname}"'))
                    print(f"✓ masters: eski global cheklov olib tashlandi ({cname})")
                yangi = conn.execute(text(
                    "SELECT 1 FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
                    "WHERE t.relname='masters' AND c.conname='uq_master_company_telegram'"
                )).first()
                if not yangi:
                    # Avval takrorlanish bor-yo'qligini tekshiramiz
                    dub = conn.execute(text(
                        "SELECT COUNT(*) FROM (SELECT company_id, telegram_id FROM masters "
                        "WHERE telegram_id IS NOT NULL GROUP BY company_id, telegram_id "
                        "HAVING COUNT(*) > 1) x")).scalar()
                    if dub:
                        print(f"⛔ masters: {dub} ta takrorlanuvchi (company_id, telegram_id) — "
                              f"cheklov qo'shilmadi")
                    else:
                        conn.execute(text(
                            "ALTER TABLE masters ADD CONSTRAINT uq_master_company_telegram "
                            "UNIQUE (company_id, telegram_id)"))
                        print("✓ masters: (company_id, telegram_id) cheklovi qo'shildi")
                conn.commit()
            except Exception as _e:
                print(f"⚠ masters.telegram_id cheklovi o'zgartirilmadi: {_e}")

            # --- User.telegram_id: global unique -> (company_id, telegram_id) ---
            # `Master` bilan bir xil sabab (Faza 5).
            try:
                eski_u = conn.execute(text(
                    "SELECT conname FROM pg_constraint c "
                    "JOIN pg_class t ON t.oid = c.conrelid "
                    "WHERE t.relname = 'users' AND c.contype = 'u' "
                    "  AND pg_get_constraintdef(c.oid) = 'UNIQUE (telegram_id)'"
                )).fetchall()
                for (cname,) in eski_u:
                    conn.execute(text(f'ALTER TABLE users DROP CONSTRAINT "{cname}"'))
                    print(f"✓ users: eski global cheklov olib tashlandi ({cname})")
                yangi_u = conn.execute(text(
                    "SELECT 1 FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
                    "WHERE t.relname='users' AND c.conname='uq_user_company_telegram'"
                )).first()
                if not yangi_u:
                    dub_u = conn.execute(text(
                        "SELECT COUNT(*) FROM (SELECT company_id, telegram_id FROM users "
                        "WHERE telegram_id IS NOT NULL GROUP BY company_id, telegram_id "
                        "HAVING COUNT(*) > 1) x")).scalar()
                    if dub_u:
                        print(f"⛔ users: {dub_u} ta takrorlanuvchi (company_id, telegram_id) — "
                              f"cheklov qo'shilmadi")
                    else:
                        conn.execute(text(
                            "ALTER TABLE users ADD CONSTRAINT uq_user_company_telegram "
                            "UNIQUE (company_id, telegram_id)"))
                        print("✓ users: (company_id, telegram_id) cheklovi qo'shildi")
                conn.commit()
            except Exception as _e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                print(f"⚠ users.telegram_id cheklovi o'zgartirilmadi: {_e}")

            if has_col("users", "is_platform_admin"):
                bor = conn.execute(text(
                    "SELECT COUNT(*) FROM users WHERE is_platform_admin = true")).scalar()
                if not bor:
                    conn.execute(text(
                        "UPDATE users SET is_platform_admin = true WHERE id = "
                        "(SELECT id FROM users WHERE lower(role::text) = 'admin' "
                        " ORDER BY id LIMIT 1)"))
                    conn.commit()
                    who = conn.execute(text(
                        "SELECT username FROM users WHERE is_platform_admin = true")).fetchall()
                    print(f"✓ Platforma admini belgilandi: {[w[0] for w in who]}")
    except Exception as e:
        print(f"⚠ Faza 3 migratsiyasi o'tkazib yuborildi: {e}")


def _migrate_float_to_numeric():
    """Bosqich 1 (2026-09-20) — to'rtta pul maydoni `Float` dan
    `Numeric(12,2)` ga o'tkaziladi.

    Nega: `Float` ikkilik kasr bo'lgani uchun pulda yaxlitlash xatosini
    ASTA-SEKIN TO'PLAYDI (klassik 0.1 + 0.2 != 0.3). Loyihadagi boshqa
    38 ta pul maydoni allaqachon `Numeric` — shu to'rttasi qolib ketgan.

    Nega HOZIR: bu jadvallarda ma'lumot deyarli yo'q, ya'ni migratsiya
    bir daqiqalik ish. Keyinroq tarixiy qiymatlarni qayta hisoblash
    kerak bo'lardi.

    Idempotent: ustun turi allaqachon `numeric` bo'lsa, tegilmaydi.
    Xavfsiz: o'zgartirishdan OLDIN eng katta qiymat tekshiriladi —
    Numeric(12,2) ga sig'masa, o'sha ustun O'TKAZIB YUBORILADI (xato
    bilan yiqilmaydi) va logda aniq ogohlantirish chiqadi.
    """
    from sqlalchemy import text
    MAYDONLAR = [
        ("gift_period_tiers", "threshold_amount"),
        ("master_gift_period_redemptions", "sales_amount"),
        ("master_gift_period_redemptions", "profit_amount"),
        ("finished_products", "price_per_m3"),
    ]
    CHEK = 10_000_000_000          # Numeric(12,2) chegarasi
    try:
        from database import engine
        if engine.dialect.name != "postgresql":
            return
        with engine.connect() as conn:
            for jadval, ustun in MAYDONLAR:
                try:
                    tur = conn.execute(text(
                        "SELECT data_type FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
                    ), {"t": jadval, "c": ustun}).scalar()

                    if tur is None:
                        print(f"• {jadval}.{ustun}: ustun yo'q, o'tkazildi")
                        continue
                    if tur == "numeric":
                        continue          # allaqachon to'g'ri

                    # Sig'masa — tegmaymiz
                    katta = conn.execute(text(
                        f"SELECT COUNT(*) FROM {jadval} "
                        f"WHERE {ustun} IS NOT NULL AND ABS({ustun}) >= {CHEK}"
                    )).scalar() or 0
                    if katta:
                        print(f"⚠ {jadval}.{ustun}: {katta} ta qiymat Numeric(12,2) ga "
                              f"sig'maydi — O'TKAZIB YUBORILDI, qo'lda ko'rish kerak")
                        continue

                    # Nechta qiymat yaxlitlanadi — logda ko'rinib tursin
                    yax = conn.execute(text(
                        f"SELECT COUNT(*) FROM {jadval} WHERE {ustun} IS NOT NULL "
                        f"AND ROUND({ustun}::numeric, 2) <> {ustun}::numeric"
                    )).scalar() or 0

                    conn.execute(text(
                        f"ALTER TABLE {jadval} ALTER COLUMN {ustun} "
                        f"TYPE NUMERIC(12,2) USING ROUND({ustun}::numeric, 2)"
                    ))
                    conn.commit()
                    print(f"✓ {jadval}.{ustun}: {tur} -> numeric(12,2)"
                          + (f" ({yax} ta qiymat tiyingacha yaxlitlandi)" if yax else ""))
                except Exception as e:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    print(f"⚠ {jadval}.{ustun} o'tkazilmadi: {e}")
    except Exception as e:
        print(f"⚠ Float->Numeric migratsiyasi o'tkazib yuborildi: {e}")


def _migrate_fp_product_type():
    """Bosqich 3, 10-band (2026-09-20) — `finished_products.product_type_id`.

    Nima uchun: tayyor mahsulot qaysi mahsulot TURIDAN ekani hech qayerda
    saqlanmasdi. MRP ishlab chiqarish buyurtmasi buni BILARDI
    (`production_orders.product_type_id`), lekin yaratgan tayyor mahsulotiga
    yozmasdi. 12-band (liniya bo'yicha moliya) aynan shu ustunga tayanadi.

    Uch qadam, har biri ALOHIDA va IDEMPOTENT:
      A) ustun + indeks + chet el kaliti (yo'q bo'lsa);
      B) SANAB CHIQADI — nechta yozuv to'ldiriladi, hech narsa o'zgartirmay;
      C) TO'LDIRADI — faqat `production_orders` orqali, ya'ni ANIQ bog'lam
         bo'yicha. Taxmin (nom bo'yicha moslashtirish va h.k.) QILINMAYDI.

    Eski, qattiq kodlangan turkumlar (profil/panel/dona/blok) uchun
    hali `ProductType` yozuvi yo'q — ular NULL bo'lib
    qoladi. Bu ATAYLAB: ularni 11-band ko'chiradi.
    """
    from sqlalchemy import text   # main.py da modul darajasida import YO'Q
    try:
        from database import engine
        if engine.dialect.name != "postgresql":
            return
        with engine.connect() as conn:
            bor = conn.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='finished_products' "
                "AND column_name='product_type_id'")).first() is not None

            # ── A. Ustun ──────────────────────────────────────────
            if not bor:
                conn.execute(text(
                    "ALTER TABLE finished_products ADD COLUMN product_type_id "
                    "INTEGER REFERENCES product_types(id)"))
                conn.commit()
                print("✓ finished_products.product_type_id qo'shildi")
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_finished_products_product_type_id "
                "ON finished_products (product_type_id)"))
            conn.commit()

            # ── A2. CHET EL KALITI — ALOHIDA, chunki ustunni ko'pincha
            # `sync_missing_columns()` birinchi bo'lib qo'shadi va u
            # faqat `ALTER TABLE ... ADD COLUMN <tur>` yozadi, REFERENCES
            # QO'SHMAYDI. Natijada yuqoridagi shart o'tib ketadi va
            # kalit umuman yaratilmay qolardi (haqiqiy PostgreSQL'da
            # 2026-09-20 da shunday chiqdi). Shuning uchun kalit har
            # doim alohida, o'z shartida tekshiriladi.
            for jadval, ustun in (("finished_products", "product_type_id"),
                                  ("order_items", "product_type_id")):
                kalit = f"{jadval}_{ustun}_fkey"
                bor_kalit = conn.execute(text(
                    "SELECT 1 FROM pg_constraint c "
                    "JOIN pg_class t ON t.oid = c.conrelid "
                    "WHERE t.relname = :j AND c.contype = 'f' "
                    "  AND c.conname = :k"), {"j": jadval, "k": kalit}).first()
                if bor_kalit:
                    continue
                # Yetim qiymat bo'lsa kalit yaratilmaydi — avval SANAYMIZ
                yetim = conn.execute(text(
                    f"SELECT COUNT(*) FROM {jadval} x "
                    f"LEFT JOIN product_types t ON t.id = x.{ustun} "
                    f"WHERE x.{ustun} IS NOT NULL AND t.id IS NULL")).scalar() or 0
                if yetim:
                    print(f"⚠ {jadval}.{ustun}: {yetim} ta yetim qiymat — "
                          f"chet el kaliti QO'YILMADI")
                    continue
                try:
                    conn.execute(text(
                        f"ALTER TABLE {jadval} ADD CONSTRAINT {kalit} "
                        f"FOREIGN KEY ({ustun}) REFERENCES product_types(id)"))
                    conn.commit()
                    print(f"✓ {kalit} chet el kaliti qo'shildi")
                except Exception as _fe:
                    conn.rollback()
                    print(f"⚠ {kalit} qo'shilmadi: {_fe}")
                conn.execute(text(
                    f"CREATE INDEX IF NOT EXISTS ix_{jadval}_{ustun} "
                    f"ON {jadval} ({ustun})"))
                conn.commit()

            # ── B. AVVAL FAQAT SANAYDI ────────────────────────────
            # Qoida (2026-09-20): ma'lumotni o'zgartiradigan migratsiya
            # avval nechta yozuvga tegishini logda ko'rsatadi.
            nomzod = conn.execute(text(
                "SELECT COUNT(*) FROM finished_products f "
                "JOIN production_orders p ON p.finished_product_id = f.id "
                "WHERE f.product_type_id IS NULL "
                "  AND p.product_type_id IS NOT NULL")).scalar() or 0
            jami_null = conn.execute(text(
                "SELECT COUNT(*) FROM finished_products "
                "WHERE product_type_id IS NULL")).scalar() or 0
            print(f"• FP turi: to'ldiriladi {nomzod} ta, "
                  f"NULL qoladi {jami_null - nomzod} ta (eski turkumlar — ataylab)")

            # ── C. TO'LDIRISH ─────────────────────────────────────
            if nomzod:
                conn.execute(text(
                    "UPDATE finished_products f SET product_type_id = p.product_type_id "
                    "FROM production_orders p "
                    "WHERE p.finished_product_id = f.id "
                    "  AND f.product_type_id IS NULL "
                    "  AND p.product_type_id IS NOT NULL"))
                conn.commit()
                qoldi = conn.execute(text(
                    "SELECT COUNT(*) FROM finished_products f "
                    "JOIN production_orders p ON p.finished_product_id = f.id "
                    "WHERE f.product_type_id IS NULL "
                    "  AND p.product_type_id IS NOT NULL")).scalar() or 0
                print(f"✓ FP turi to'ldirildi: {nomzod} ta, qolgani {qoldi} ta")

            # ── D. Nazorat: boshqa korxonaning turiga ishora qilyaptimi? ──
            # Tenant xavfsizligi — bog'lam noto'g'ri korxonaga ketmasligi
            # kerak. Faqat XABAR beradi, hech narsa o'zgartirmaydi.
            chalkash = conn.execute(text(
                "SELECT COUNT(*) FROM finished_products f "
                "JOIN product_types t ON t.id = f.product_type_id "
                "WHERE f.company_id IS DISTINCT FROM t.company_id")).scalar() or 0
            if chalkash:
                print(f"⚠ FP turi: {chalkash} ta yozuv BOSHQA korxonaning turiga ishora qilyapti!")
    except Exception as e:
        try:
            from database import engine as _e
            with _e.connect() as c:
                c.rollback()
        except Exception:
            pass
        print(f"⚠ FP product_type migratsiyasi o'tkazib yuborildi: {e}")


_migrate_drop_company_id_defaults()
_migrate_faza3_columns()
_migrate_float_to_numeric()
_migrate_fp_product_type()

from database import SessionLocal
_db = SessionLocal()
try:
    auth.create_default_admin(_db)
finally:
    _db.close()

# Bir martalik (lekin xavfsiz — qayta-qayta chaqirilsa ham hech narsa
# buzmaydigan) migratsiya: to'lov tarixi yozuvi hali yo'q hodimlarga
# boshlang'ich tarix yaratadi (2026-09-06, oylik versiyalash tizimi).
try:
    _db2 = SessionLocal()
    try:
        crud.backfill_employee_compensation_history(_db2)
    finally:
        _db2.close()
except Exception as e:
    print(f"⚠ Hodim to'lov tarixi backfill xatosi: {e}")

app = FastAPI(title="PenoDecorPro ERP", description="Ishlab chiqarish boshqaruv tizimi", version="1.0.0", debug=False)

# 2026-09-16: yangi, dinamik Production/MRP moduli — /api/production/... yo'llari
app.include_router(production_router)

# 2026-09-18: VAQTINCHALIK — SaaS ko'p-tenantlilik migratsiyasi (/api/saas-migration/...).
# Faqat ADMIN kira oladi, standart holatda DRY-RUN (sinov) rejimida ishlaydi.
# Migratsiya to'liq tugagach, bu 2 qator VA saas_migration.py fayli olib tashlanadi.
try:
    from saas_migration import router as saas_migration_router
    if saas_migration_router is not None:
        app.include_router(saas_migration_router)
except Exception as _e:
    print(f"⚠ SaaS migratsiya moduli yuklanmadi (o'tkazib yuborildi): {_e}")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Har bir javobga asosiy xavfsizlik sarlavhalarini qo'shadi.
    MUHIM: Content-Security-Policy ATAYLAB qo'shilmagan — ilova
    sahifalarida ko'p "inline" (to'g'ridan-to'g'ri HTML ichidagi)
    JavaScript va CSS ishlatiladi, qat'iy CSP bularni bloklab, butun
    interfeysni ishlamay qo'yishi mumkin edi. Bu 3 tasi esa — xavfsiz,
    mavjud funksionallikka ta'sir qilmaydi."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(Exception)
async def global_error_logger(request: Request, exc: Exception):
    """Kutilmagan (unhandled) xatolarni avtomatik yozib boradi va foydalanuvchiga
    tushunarli xato qaytaradi. HTTPException (masalan 404/403/409) — bu yerga
    kelmaydi, ular FastAPI'ning o'z ichki mexanizmi orqali to'g'ri ishlanadi."""
    import traceback
    try:
        log_db = SessionLocal()
        try:
            # Faza 3: xatoni KORXONAGA bog'laymiz. Sessiya tokenidan
            # foydalanuvchi aniqlansa — uning korxonasi; aniqlanmasa
            # (fon vazifasi, login oldidagi xato) NULL qoladi va bu
            # PLATFORMA xatosi hisoblanadi.
            _cid, _who = None, None
            try:
                _tok = request.cookies.get("session_token")
                if _tok:
                    _sess = auth.get_session(log_db, _tok)
                    if _sess:
                        from models import User as _U_err
                        _u = log_db.query(_U_err).filter(
                            _U_err.id == _sess["user_id"]).first()
                        if _u is not None:
                            _cid = getattr(_u, "company_id", None)
                            _who = getattr(_u, "full_name", None) or getattr(_u, "username", None)
            except Exception:
                _cid, _who = None, None
            crud.log_error(
                log_db, error_message=str(exc), stack_trace=traceback.format_exc(),
                endpoint=str(request.url.path), method=request.method,
                performed_by=_who, company_id=_cid
            )
        finally:
            log_db.close()
    except Exception:
        pass  # Log yozishning o'zi xato bersa — asosiy oqimni to'xtatmaymiz
    return JSONResponse(status_code=500, content={"detail": "Serverda kutilmagan xato yuz berdi"})


# 2026-09-17 (audit topilmasi — haqiqiy xato): seans tugagan yoki umuman
# kirilmagan holda HIMOYALANGAN SAHIFA (masalan /users, /dashboard) ochilsa,
# FastAPI'ning standart xatti-harakati — xom JSON matn qaytarish edi
# (`{"detail": "Iltimos, tizimga kiring"}`), foydalanuvchi esa "sayt
# buzilibdimi?" deb chalkashib qolishi mumkin edi. Endi bunday holatda —
# FAQAT sahifa (HTML) so'rovlari uchun — chiroyli /login sahifasiga
# yo'naltiriladi. API so'rovlari (/api/...) uchun xatti-harakat
# O'ZGARTIRILMAYDI — ular hamon aniq JSON xato qaytarib olishi kerak
# (frontend shu javobni o'qib, o'ziga yarasha ko'rsatadi).
# 2026-09-18 — M4. Korxonalararo bog'lanish urinishi (`models._tenant_guard`)
# `TenantMismatchError` beradi. Himoya O'ZGARMAYDI — tranzaksiya avvalgidek
# to'liq bekor qilinadi (rollback) va bazaga hech narsa yozilmaydi. Faqat
# foydalanuvchiga qaytariladigan javob to'g'rilanadi: ilgari bu xato
# yuqoridagi umumiy `Exception` ishlovchisiga tushib, xom 500 "Serverda
# kutilmagan xato yuz berdi" ko'rinardi. Endi — mavjud API konvensiyasiga
# mos 409 va tushunarli xabar.
from models import TenantMismatchError as _TenantMismatchError


@app.exception_handler(_TenantMismatchError)
async def tenant_mismatch_handler(request: Request, exc: _TenantMismatchError):
    return JSONResponse(
        status_code=409,
        content={"detail": "Boshqa korxonaning ma'lumoti bilan bog'lab bo'lmaydi. "
                           "Amal bekor qilindi."},
    )


from starlette.exceptions import HTTPException as _StarletteHTTPException


@app.exception_handler(_StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: _StarletteHTTPException):
    if exc.status_code == 401 and not request.url.path.startswith("/api/"):
        return RedirectResponse(url="/login", status_code=302)
    # Boshqa barcha holatlar uchun — FastAPI'ning standart javobi bilan bir xil
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)


# ============================================================
# Korxona nomi — interfeysda ko'rsatish uchun (Faza 5)
# ============================================================
# NEGA KERAK: sarlavhada "PenoDecorPro · Andijon" QATTIQ yozilgan edi.
# SaaS da bu noto'g'ri — ikkinchi mijoz o'z ERP sida boshqa korxonaning
# nomini ko'rib turardi. Endi nom bazadan olinadi.
#
# Har sahifada bazaga so'rov yubormaslik uchun kichik keshda saqlanadi;
# nom o'zgartirilganda kesh tozalanadi.
_company_name_cache = {}


def company_name_of(company_id):
    """Korxona nomini qaytaradi (keshdan yoki bazadan)."""
    if company_id is None:
        return None
    if company_id in _company_name_cache:
        return _company_name_cache[company_id]
    try:
        from database import SessionLocal as _SL
        from production_models import Company as _Co
        _d = _SL()
        try:
            row = _d.query(_Co).filter(_Co.id == company_id).first()
            nom = row.name if row else None
        finally:
            _d.close()
    except Exception:
        nom = None
    _company_name_cache[company_id] = nom
    return nom


def _clear_company_name_cache(company_id=None):
    if company_id is None:
        _company_name_cache.clear()
    else:
        _company_name_cache.pop(company_id, None)


def company_logo_of(company_id):
    """Korxona logotipining yo'li (interfeys uchun). Yo'q bo'lsa None."""
    if company_id is None:
        return None
    try:
        import os as _os
        from database import SessionLocal as _SL
        from production_models import Company as _Co
        _d = _SL()
        try:
            row = _d.query(_Co).filter(_Co.id == company_id).first()
            yol = (getattr(row, "logo_path", None) or "").strip() if row else ""
        finally:
            _d.close()
        if not yol:
            return None
        tola = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), yol)
        return yol if _os.path.exists(tola) else None
    except Exception:
        return None


templates.env.globals["company_name_of"] = company_name_of
# ============================================================
# Ixtiyoriy mahsulot kategoriyalari (Faza 5)
# ============================================================
# Dasturda "Loy sotish" va "Blok" — PenoDecorPro ning o'ziga xos
# yo'nalishlari. Boshqa korxona ularni
# ishlab chiqarmasligi mumkin, lekin interfeysda ular baribir
# ko'rinardi va yangi mijozni chalkashtirardi.
#
# Endi har korxona o'ziga keraklisini tanlaydi. Sozlama bo'sh bo'lsa —
# HAMMASI ko'rinadi, ya'ni mavjud korxonada hech narsa o'zgarmaydi.
# Yangi korxona yaratilganda esa faqat asosiy turlar yoqiladi.
IXTIYORIY_KATEGORIYALAR = [
    # 11.2a (2026-09-20): `termopanel` BUTUNLAY olib tashlandi — kodi
    # ham, interfeysi ham qolmadi, shuning uchun ro'yxatda ham yo'q.
    # 11.2b (2026-09-20): `gips` ham xuddi shunday BUTUNLAY olib
    # tashlandi — kerak bo'lsa MRP dan o'z retsepti bilan yaratiladi.
    ("loy_sotish", "🪣 Loy sotish"),
    # Bosqich 3, 11.1-band (2026-09-20) — `blok` ESKIRGAN turkumga o'tdi.
    # Endi uning o'rniga MRP dan o'z mahsulot turingizni yaratasiz:
    # retseptda "1 metr uchun necha blok penoplast" deb yozasiz, qoplama
    # koeffitsiyentini ham o'zingiz belgilaysiz. Eski `blok` kodi
    # O'CHIRILMADI — mavjud yozuvlar avvalgidek ko'rinadi va hisoblanadi.
    ("blok", "🧊 Blok (eskirgan — MRP dan foydalaning)"),
]
_ASOSIY_KATEGORIYALAR = ["profil", "panel", "dona"]

# Hech qachon sozlanmagan korxonada ixtiyoriy turlarning HAMMASI yoqiq
# bo'ladi (eski xatti-harakat saqlanadi). Lekin ESKIRGAN turlar bundan
# MUSTASNO — ular faqat ATAYLAB yoqilganda ko'rinadi. Aks holda `blok`
# ni ixtiyoriy qilishning ma'nosi qolmasdi: u baribir hammaga
# ko'rinaverardi.
_ESKIRGAN_KATEGORIYALAR = {"blok"}


_kategoriya_cache = {}


def _clear_category_cache(company_id=None):
    if company_id is None:
        _kategoriya_cache.clear()
    else:
        _kategoriya_cache.pop(company_id, None)


def enabled_categories_of(company_id):
    """Korxonada yoqilgan ixtiyoriy kategoriyalar to'plami.

    Bitta sahifa renderida bu funksiya 10+ marta chaqiriladi, shuning
    uchun natija keshda saqlanadi; sozlama o'zgarganda kesh tozalanadi.
    """
    if company_id is None:
        return {k for k, _ in IXTIYORIY_KATEGORIYALAR
                if k not in _ESKIRGAN_KATEGORIYALAR}
    if company_id in _kategoriya_cache:
        return _kategoriya_cache[company_id]
    try:
        from database import SessionLocal as _SL
        _d = _SL()
        try:
            xom = crud.get_setting(_d, "enabled_categories", None, company_id=company_id)
        finally:
            _d.close()
    except Exception:
        xom = None
    if xom is None:
        # Hech qachon sozlanmagan — hammasi yoqiq (eski xatti-harakat),
        # ESKIRGANlardan tashqari (11.1-band).
        natija = {k for k, _ in IXTIYORIY_KATEGORIYALAR
                  if k not in _ESKIRGAN_KATEGORIYALAR}
    else:
        # ⚠ 2026-09-21: sozlama satri — bu ESKI MATN, bazada yillab
        # o'zgarmay yotishi mumkin. Undagi so'z hali MAVJUD turkummi,
        # tekshirilishi SHART. Aks holda 11.2a/11.2b da butunlay olib
        # tashlangan `termopanel` / `gips` eski satrdan qaytib kelardi,
        # admin esa ularni sozlamalar sahifasida KO'RMASDI ham (ro'yxatda
        # yo'q), ya'ni O'CHIRA OLMASDI. Endi noma'lum so'z jimgina
        # e'tiborsiz qoldiriladi — sozlama o'zi-o'zidan tozalanadi.
        _malum = {k for k, _ in IXTIYORIY_KATEGORIYALAR}
        natija = {x.strip() for x in xom.split(",") if x.strip() in _malum}
    _kategoriya_cache[company_id] = natija
    return natija


def cat_on(code, company_id=None):
    """Shablonlar uchun: shu kategoriya ko'rsatilsinmi?"""
    if code in _ASOSIY_KATEGORIYALAR:
        return True
    return code in enabled_categories_of(company_id)


templates.env.globals["company_logo_of"] = company_logo_of
templates.env.globals["cat_on"] = cat_on
# 2026-09-17: statik fayllar (masalan translit.js) uchun cache-busting —
# brauzer/Telegram WebApp eski nusxani abadiy keshlab qolmasligi uchun.
# Har deploy'da bu qiymat o'zgarishi kerak (masalan shu sana-vaqt) —
# shunda "?v=..." o'zgarib, brauzer albatta YANGI faylni yuklaydi.
templates.env.globals["static_version"] = "20260917-1"

import os
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

# Ba'zi serverlarda .woff2/.woff kengaytmalari noto'g'ri MIME turi bilan
# yuborilishi mumkin (masalan application/json) — brauzerlar buni rad etadi
# va ikonka shrifti yuklanmaydi. Shu sabab to'g'ri turlarni majburiy belgilaymiz.
import mimetypes
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("text/css", ".css")

class ReliableStaticFiles(StaticFiles):
    """Ba'zi hosting muhitlarida (masalan Railway) tizimning o'z MIME
    jadvali noto'g'ri yoki mavjud bo'lmasligi mumkin, natijada .woff2/.woff
    kabi shrift fayllari 'text/plain' deb yuborilib, brauzer ularni rad etadi.
    Bu klass kengaytmaga qarab TO'G'RIDAN-TO'G'RI to'g'ri turni majburlaydi —
    tizim sozlamalariga umuman bog'liq emas."""
    _FORCED_TYPES = {
        ".woff2": "font/woff2",
        ".woff": "font/woff",
        ".ttf": "font/ttf",
        ".css": "text/css; charset=utf-8",
    }

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        path = str(args[0]) if args else str(kwargs.get("full_path", ""))
        for ext, forced_type in self._FORCED_TYPES.items():
            if path.lower().endswith(ext):
                response.headers["content-type"] = forced_type
                break
        return response


app.mount("/static", ReliableStaticFiles(directory=static_dir), name="static")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    user = auth.get_current_user(request, db)
    if user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"error": None, "username": ""})


@app.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    from models import User
    username = username.strip()
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:250]

    rl = crud.check_login_rate_limit(db, username, ip)
    if rl["blocked"]:
        return templates.TemplateResponse(request, "login.html", {
            "error": f"Juda ko'p noto'g'ri urinish. {rl['retry_after_minutes']} daqiqadan so'ng qayta urining.",
            "username": username
        })

    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user or not auth.verify_and_upgrade_password(db, user, password):
        crud.log_login_attempt(db, username, success=False, ip_address=ip, user_agent=ua)
        return templates.TemplateResponse(request, "login.html", {"error": "Login yoki parol noto'g'ri!", "username": username})

    crud.log_login_attempt(db, username, success=True, ip_address=ip, user_agent=ua)
    token = auth.create_session(db, user.id)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(key="session_token", value=token, httponly=True, max_age=3600 * 8, samesite="lax", secure=True)
    return response


@app.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session_token")
    if token:
        auth.delete_session(db, token)
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("session_token")
    return response


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    users = auth.get_all_users(db, company_id=auth.company_id_of(current_user))
    return templates.TemplateResponse(request, "users.html", {"users": users, "current_user": current_user, "now": datetime.now().strftime("%d.%m.%Y %H:%M"), "active_page": "users"})


@app.get("/trash", response_class=HTMLResponse)
async def trash_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """O'chirilgan buyurtma, loyiha va xodimlar — inson xatosidan himoya uchun tiklash imkoni."""
    deleted_orders = crud.get_deleted_orders(db, company_id=auth.company_id_of(current_user))
    deleted_projects = crud.get_deleted_projects(db, company_id=auth.company_id_of(current_user))
    deleted_employees = crud.get_deleted_employees(db, company_id=auth.company_id_of(current_user))
    # ⚠ 2026-09-21: `company_id` uzatilmagan edi — B korxona admini A ning
    # audit jurnalini (kim nimani o'chirgani, usta/hodim nomlari) ko'rardi.
    # `crud.get_activity_log` da parametr ALLAQACHON bor edi, faqat shu
    # chaqiruvda unutilgan; `/logs` sahifasida to'g'ri uzatilgan.
    activity_log = crud.get_activity_log(db, limit=50,
                                         company_id=auth.company_id_of(current_user))
    return templates.TemplateResponse(request, "trash.html", {
        "deleted_orders": deleted_orders, "deleted_projects": deleted_projects,
        "deleted_employees": deleted_employees,
        "activity_log": activity_log,
        "current_user": current_user, "active_page": "trash"
    })


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Tizim jurnallari — kirish tarixi va backend xatoliklari (faqat admin)."""
    # M7: audit izi va kirish tarixi FAQAT joriy korxonaniki.
    # Faza 3 (2026-09-19): `error_logs.company_id` ustuni qo'shildi —
    # endi xatolar ham to'g'ri ajratiladi: korxonaniki o'ziga, platforma
    # xatolari (NULL) hammaga.
    _cid = auth.company_id_of(current_user)
    login_history = crud.get_login_history(db, limit=100, company_id=_cid)
    # 2026-09-20 — Texnik xatolar (Python traceback) FAQAT platforma
    # administratori uchun. Sabab: bunday xabar korxona egasiga hech narsa
    # bermaydi, lekin ikki xil zarar keltiradi — (1) "dastur buzuqmi?"
    # degan keraksiz xavotir, (2) fayl yo'llari, jadval nomlari va ba'zan
    # qiymatlar oshkor bo'lishi. Xatoni topish va tuzatish — xizmat
    # ko'rsatuvchining ishi. Ro'yxat umuman YUBORILMAYDI, ya'ni HTML
    # ichida ham qolmaydi.
    _platforma = bool(getattr(current_user, "is_platform_admin", False))
    error_logs = crud.get_error_logs(
        db, limit=100, company_id=_cid, include_platform=True) if _platforma else []
    activity_log = crud.get_activity_log(db, limit=100, company_id=_cid)
    return templates.TemplateResponse(request, "logs.html", {
        "login_history": login_history, "error_logs": error_logs,
         "is_platform_admin": _platforma, "activity_log": activity_log,
        "current_user": current_user, "active_page": "logs"
    })


@app.get("/api/system/health-check")
def api_system_health_check(db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Tizimdagi barcha ENUM ustunlarini tekshiradi (faqat o'qish, hech
    narsani o'zgartirmaydi) — noto'g'ri (masalan katta/kichik harf mos
    kelmaydigan) qiymatlarni oldindan aniqlash uchun."""
    _cid = auth.company_id_of(current_user)

    # 2026-09-20 — Bu tekshiruv IKKI xil narsadan iborat:
    #   • TEXNIK skan (enum ustunlari) — natijasi "productionstatus
    #     ustunida noto'g'ri qiymat" kabi xabarlar. Korxona egasi buni
    #     tushunmaydi va u bilan hech narsa qila olmaydi. Faqat platforma
    #     administratori uchun.
    #   • MOLIYAVIY izchillik — "buyurtma summasi detallar yig'indisiga
    #     mos emas", "ombor qoldig'i manfiy" kabi. Bu AYNAN biznes
    #     muammosi va mijoz uni o'zi tuzata oladi — shuning uchun
    #     hammaga ko'rsatiladi.
    _platforma = bool(getattr(current_user, "is_platform_admin", False))
    moliyaviy = crud.check_financial_consistency(db, company_id=_cid)

    if _platforma:
        result = crud.check_system_health(db, company_id=_cid)
    else:
        result = {"total_checks": 0, "issues_found": 0, "issues": [],
                  "check_errors": [], "technical_hidden": True}
    result["financial"] = moliyaviy
    result["is_platform_admin"] = _platforma

    # 2026-09-21: avtomatik tenant filtri HOZIR yoqilganmi — operatsion
    # o'qish. Ilgari buni bilishning yagona yo'li Railway sozlamalariga
    # kirish edi, u yerda esa qiymat yashirin ko'rinadi: "o'zgaruvchi bor"
    # degani "qiymati 1" degani EMAS. Himoya to'ri jimgina o'chiq qolishi
    # mumkin va buni hech kim sezmaydi.
    # `stats` — ishga tushgandan beri: nechta ORM so'rovga filtr
    # qo'llangan / kontekst bo'lmagani uchun o'tkazib yuborilgan.
    # `filtered` 0 bo'lib turishi filtr AMALDA ishlamayotganini bildiradi.
    try:
        import tenant_context as _tc
        result["tenant_filter"] = {
            "enabled": bool(_tc.ENABLED),
            "stats": _tc.get_stats(),
        }
    except Exception as _e:
        result["tenant_filter"] = {"enabled": None, "error": str(_e)[:120]}
    return result


@app.post("/api/orders/{order_id}/restore")
def api_restore_order(order_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.order_of_company(db, order_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    who = current_user.full_name or current_user.username
    if not crud.restore_order(db, order_id, performed_by=who):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    return {"status": "ok"}


@app.post("/api/projects/{project_id}/restore")
def api_restore_project(project_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.project_of_company(db, project_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    who = current_user.full_name or current_user.username
    if not crud.restore_project(db, project_id, performed_by=who):
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    return {"status": "ok"}


@app.delete("/api/orders/{order_id}/permanent")
def api_permanent_delete_order(order_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Butunlay o'chirish — faqat 'chiqindi qutisi'dagi (avval yumshoq o'chirilgan) buyurtma uchun."""
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.order_of_company(db, order_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    who = current_user.full_name or current_user.username
    if not crud.permanent_delete_order(db, order_id, performed_by=who):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi (avval yumshoq o'chirilgan bo'lishi kerak)")
    return {"status": "ok"}


@app.delete("/api/projects/{project_id}/permanent")
def api_permanent_delete_project(project_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Butunlay o'chirish — faqat 'chiqindi qutisi'dagi (avval yumshoq o'chirilgan) loyiha uchun."""
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.project_of_company(db, project_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    who = current_user.full_name or current_user.username
    ok, msg = crud.permanent_delete_project(db, project_id, performed_by=who)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "ok"}


@app.post("/api/users")
def api_create_user(data: dict, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    try:
        role = UserRole(data.get("role", "manager"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Noto'g'ri rol")
    # M1: yangi foydalanuvchi ALBATTA joriy adminning korxonasiga tegishli.
    user = auth.create_user(db, data["username"], data["password"], role,
                            data.get("full_name", ""),
                            company_id=auth.company_id_of(current_user))
    return {"id": user.id, "username": user.username, "role": user.role.value}


@app.post("/api/users/{user_id}/toggle")
def api_toggle_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    user = auth.toggle_user_active(db, user_id,
                                   company_id=auth.company_id_of(current_user))
    if not user:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"is_active": user.is_active}


@app.post("/api/users/{user_id}/password")
def api_change_password(user_id: int, data: dict, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    new_pass = data.get("new_password", "")
    if len(new_pass) < 6:
        raise HTTPException(status_code=400, detail="Parol kamida 6 belgi")

    # 2026-09-20 — O'Z parolini almashtirishda ESKI parol so'raladi.
    # Sabab: kimdir ochiq qolgan sessiyadan foydalanib parolni almashtirib,
    # egasini o'z tizimidan qulflab qo'yishi mumkin. Boshqa foydalanuvchining
    # parolini tiklashda esa eski parol so'ralmaydi — admin uni bilmaydi
    # (aynan shuning uchun tiklayapti).
    if user_id == current_user.id:
        eski = data.get("current_password", "")
        if not eski:
            raise HTTPException(status_code=400,
                                detail="Joriy parolni kiriting")
        # `verify_and_upgrade_password` — login oqimida ishlatiladigan
        # AYNI funksiya (eski SHA-256 hashni bcrypt ga ham ko'chiradi).
        if not auth.verify_and_upgrade_password(db, current_user, eski):
            raise HTTPException(status_code=400, detail="Joriy parol noto'g'ri")

    if not auth.change_password(db, user_id, new_pass,
                                company_id=auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    current_user = auth.get_current_user(request, db)
    if not current_user:
        return RedirectResponse("/login", status_code=302)
    # home.html moliyaviy ko'rsatkichlarni (bugungi foyda va h.k.) ko'rsatadi —
    # shuning uchun bu faqat Admin/Moliyachi uchun. Boshqa rollar — o'z asosiy
    # ish maydoniga yo'naltiriladi.
    role = current_user.role.value
    if role == "manager":
        return RedirectResponse("/orders", status_code=302)
    if role == "warehouse":
        return RedirectResponse("/inventory", status_code=302)
    if role == "master":
        return RedirectResponse("/orders", status_code=302)
    return templates.TemplateResponse(request, "home.html", {"current_user": current_user, "active_page": "home"})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    stats = services.get_dashboard_stats(db, company_id=auth.company_id_of(current_user))
    return templates.TemplateResponse(request, "dashboard.html", {"stats": stats, "current_user": current_user, "active_page": "dashboard"})


@app.get("/masters")
async def masters_page_redirect():
    """Eski Ustalar sahifasi endi Ustalar KPI / Hodimlar bo'limiga ko'chdi."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/kpi", status_code=307)


@app.get("/ustalar", response_class=HTMLResponse)
async def masters_manage_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Usta qo'shish/tahrirlash — Manager uchun, Moliya/KPI ma'lumotisiz.
    /kpi sahifasi faqat admin_or_financier ga ochiq bo'lgani uchun, Manager
    'Yangi usta' tugmasiga hech qachon yeta olmasdi — bu sahifa o'sha
    kamchilikni to'g'irlaydi (2026-09-06)."""
    return templates.TemplateResponse(request, "masters_manage.html", {
        "current_user": current_user, "active_page": "ustalar"
    })


@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.inventory_view)):
    items = crud.get_inventory(db, company_id=auth.company_id_of(current_user))
    kpi = services.get_inventory_kpi(db, company_id=auth.company_id_of(current_user))
    suppliers = crud.get_suppliers(db, company_id=auth.company_id_of(current_user))
    return templates.TemplateResponse(request, "inventory.html", {"items": items, "kpi": kpi, "suppliers": suppliers, "current_user": current_user, "active_page": "inventory"})


@app.post("/api/inventory/{item_id}/image")
def api_upload_inventory_image(item_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                                current_user=Depends(auth.admin_or_warehouse)):
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.inventory_of_company(db, item_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Material topilmadi")
    from models import Inventory
    item = db.query(Inventory).filter(Inventory.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Xomashyo topilmadi")
    url = _save_upload(file, "inventory", ALLOWED_IMAGE_EXT)
    item.image_url = url
    db.commit()
    return {"image_url": url}


@app.get("/api/inventory/kpi")
def api_inventory_kpi(db: Session = Depends(get_db), current_user=Depends(auth.inventory_view)):
    return services.get_inventory_kpi(db, company_id=auth.company_id_of(current_user))


@app.get("/recipes", response_class=HTMLResponse)
async def recipes_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    recipes = crud.get_recipes(db, company_id=auth.company_id_of(current_user))
    insights = {r.id: crud.get_recipe_insights(db, r.id) for r in recipes}
    return templates.TemplateResponse(request, "recipes.html", {"recipes": recipes, "insights": insights, "current_user": current_user, "active_page": "recipes"})


@app.get("/production", response_class=HTMLResponse)
async def production_page(request: Request, current_user=Depends(auth.admin_or_warehouse)):
    """2026-09-16: yangi Dinamik Ishlab chiqarish (Production/MRP) sahifasi.
    Barcha ma'lumotlar (mahsulot turlari, retseptlar, buyurtmalar)
    frontendda AJAX orqali /api/production/... dan yuklanadi — shuning
    uchun bu yerga hech qanday kontekst uzatish shart emas."""
    return templates.TemplateResponse(request, "production.html", {"current_user": current_user, "active_page": "production"})


@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_manager_accountant)):
    projects = crud.get_projects_with_stats(db, company_id=auth.company_id_of(current_user))
    kpi = crud.get_projects_dashboard_stats(db, company_id=auth.company_id_of(current_user))
    return templates.TemplateResponse(request, "projects.html", {"projects": projects, "kpi": kpi, "current_user": current_user, "active_page": "projects"})


@app.get("/api/projects/progress-map")
def api_projects_progress_map(db: Session = Depends(get_db), current_user=Depends(auth.admin_manager_accountant)):
    """Har bir loyiha uchun bajarilish foizi (tayyor/yetkazilgan buyurtmalar ulushi) — faqat o'qish."""
    from models import Order, OrderStatus
    from sqlalchemy import func, case

    rows = db.query(
        Order.project_id,
        func.count(Order.id).label("total"),
        func.sum(case((Order.status.in_([OrderStatus.READY, OrderStatus.DELIVERED]), 1), else_=0)).label("ready")
    ).filter(Order.status.notin_([OrderStatus.DRAFT, OrderStatus.CANCELLED]),
             Order.company_id == auth.company_id_of(current_user)
    ).group_by(Order.project_id).all()

    result = {}
    for project_id, total, ready in rows:
        result[project_id] = round((ready / total) * 100) if total else 0
    return result


@app.get("/api/projects/dashboard-stats")
def api_projects_dashboard_stats(db: Session = Depends(get_db), current_user=Depends(auth.admin_manager_accountant)):
    return crud.get_projects_dashboard_stats(db, company_id=auth.company_id_of(current_user))


@app.post("/api/projects/{project_id}/payment")
def api_add_payment(project_id: int, amount: float, db: Session = Depends(get_db), current_user=Depends(auth.admin_manager_accountant)):
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.project_of_company(db, project_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    updated = crud.add_payment(db, project_id, amount)
    if not updated:
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    return {"status": "ok", "total_paid": float(updated.total_paid)}


@app.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request, show_all: bool = False, db: Session = Depends(get_db), current_user=Depends(auth.orders_page_access)):
    orders = crud.get_orders_for_main_page(db, days=90, show_all=show_all, company_id=auth.company_id_of(current_user))
    for o in orders:
        o.deadline_urgency = crud.get_deadline_urgency(o.deadline, o.status.value, o.is_fully_delivered)
    projects = crud.get_projects(db, company_id=auth.company_id_of(current_user))
    masters = crud.get_masters(db, only_active=True, company_id=auth.company_id_of(current_user))
    recipes = crud.get_recipes(db, company_id=auth.company_id_of(current_user))
    penoplasts = services.get_penoplast_list(db)
    default_p = services.get_default_penoplast(db)

    # Loyiha bo'yicha guruhlaymiz
    groups = {}
    for o in orders:
        pid = o.project_id
        if pid not in groups:
            groups[pid] = {
                "project_id": pid,
                "project_name": o.project.project_name if o.project else "Loyihasiz",
                "client_name": o.project.client_name if o.project else "—",
                "orders": [],
                "total": 0.0,
                "debt": 0.0,
                "active": 0,
            }
        g = groups[pid]
        g["orders"].append(o)
        g["total"] += float(o.agreed_amount or o.total_amount or 0)
        g["debt"] += o.debt_amount
        if o.status.value not in ("ready", "delivered", "cancelled"):
            g["active"] += 1

    # 2026-09-15: har bir loyiha ichida buyurtmalar endi shunchaki "qachon
    # yaratilgan" tartibida emas — HALI TUGALLANMAGAN (jarayonda) buyurtmalar
    # eng tepaga, ular orasida esa TOPSHIRISH MUDDATI eng yaqini birinchi
    # bo'lib chiqadi (muddat yo'q bo'lsa — oxirida). Tugallangan buyurtmalar
    # bundan keyin, o'zining avvalgi (yaratilgan sana) tartibida qoladi.
    for g in groups.values():
        active_orders = [o for o in g["orders"] if o.status.value not in ("ready", "delivered", "cancelled")]
        finished_orders = [o for o in g["orders"] if o.status.value in ("ready", "delivered", "cancelled")]
        active_orders.sort(key=lambda o: (o.deadline is None, o.deadline))
        g["orders"] = active_orders + finished_orders

    # Eng yangi buyurtmasi bo'yicha tartiblaymiz
    grouped = sorted(
        groups.values(),
        key=lambda g: max((x.created_at for x in g["orders"] if x.created_at), default=datetime.min),
        reverse=True
    )

    return templates.TemplateResponse(request, "orders.html", {
        "orders": orders, "grouped": grouped,
        "projects": projects, "masters": masters,
        "recipes": recipes, "penoplasts": penoplasts,
        "default_penoplast_id": default_p.id if default_p else None,
        "current_user": current_user, "active_page": "orders",
        "show_all": show_all
    })


@app.post("/api/masters", response_model=schemas.MasterRead)
def api_create_master(master: schemas.MasterCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    new_master = crud.create_master(db, master, company_id=auth.company_id_of(current_user))
    tg_id = getattr(master, 'telegram_id', None)
    if tg_id and str(tg_id).strip().lstrip('-').isdigit():
        msg = (
            f"Assalomu alaykum, hurmatli hamkor! 🤝\n\n"
            f"Siz bizning rasmiy ustalar bazamizga\n"
            f"muvaffaqiyatli qo'shildingiz.\n"
            f"Hamkorligingiz uchun tashakkur!\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *{new_master.name}*\n"
            f"📱 {new_master.phone}\n"
            f"🎯 Bonus foizi: *{new_master.cashback_percent}%*\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 *Siz uchun maxsus imkoniyat:*\n"
            f"Bizda har bir buyurtmangiz uchun muntazam\n"
            f"hisoblab boriladigan bonus tizimi mavjud.\n"
            f"O'z bonuslaringizni va buyurtmalar holatini\n"
            f"botimiz orqali istalgan vaqtda kuzatib\n"
            f"borishingiz mumkin. 📊\n\n"
            f"Ishlaringizda rivoj va baraka tilaymiz! 🌟\n\n"
            f"🏗 *PenoDecorPro* — Zamonaviy fasad dekorlari\n"
            f"📍 Andijon, O'zbekiston"
        )
        _send_telegram_to(str(tg_id).strip(), msg)
    return new_master


@app.delete("/api/masters/{master_id}/delete")
def api_delete_master_permanent(master_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    # M5: usta FAQAT joriy korxonadan (aks holda 404).
    master = auth.master_of_company(db, master_id, auth.company_id_of(current_user))
    if not master:
        raise HTTPException(status_code=404, detail="Usta topilmadi")
    db.delete(master)
    db.commit()
    return {"status": "ok"}


@app.get("/api/masters", response_model=List[schemas.MasterRead])
def api_get_masters(only_active: bool = False, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return crud.get_masters(db, only_active=only_active,
                           company_id=auth.company_id_of(current_user))


@app.put("/api/masters/{master_id}", response_model=schemas.MasterRead)
def api_update_master(master_id: int, data: schemas.MasterUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    updated = crud.update_master(db, master_id, data,
                                company_id=auth.company_id_of(current_user))
    if not updated:
        raise HTTPException(status_code=404, detail="Usta topilmadi")
    return updated


@app.delete("/api/masters/{master_id}")
def api_delete_master(master_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    if not crud.delete_master(db, master_id, company_id=auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Usta topilmadi")
    return {"status": "ok"}


@app.post("/api/inventory", response_model=schemas.InventoryRead)
def api_create_item(item: schemas.InventoryCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    try:
        # M3/M8-F1: yangi material ALBATTA joriy adminning korxonasiga
        # tegishli — tenant endi `add_item()` ga BOSHIDAN uzatiladi
        # (ilgari qaytgandan keyin qo'yilardi va ichki commit vaqtida
        # ustun bo'sh qolardi).
        _it = crud.add_item(db, item, company_id=auth.company_id_of(current_user))
        return _it
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f'"{item.item_name}" nomli material allaqachon omborda mavjud. '
                   f'"← Ro\'yxatdan tanlayman" tugmasi orqali uni tanlang, yangi material sifatida qayta yaratmang.'
        )


@app.get("/api/inventory", response_model=List[schemas.InventoryRead])
def api_get_inventory(db: Session = Depends(get_db), current_user=Depends(auth.inventory_view)):
    return crud.get_inventory(db, company_id=auth.company_id_of(current_user))


@app.post("/api/inventory/{item_id}/stock", response_model=schemas.InventoryRead)
def api_update_stock(item_id: int, change: schemas.StockChange, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Qoldiqni narxsiz tuzatish (inventarizatsiya, kamomad va h.k.)."""
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.inventory_of_company(db, item_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Material topilmadi")
    updated = crud.update_stock(db, item_id, change.quantity_change,
                                 performed_by=current_user.full_name or current_user.username,
                                 notes=change.reason)
    if not updated:
        raise HTTPException(status_code=404, detail="Xomashyo topilmadi")
    return updated


@app.put("/api/inventory/{item_id}")
def api_update_inventory_item(item_id: int, data: schemas.InventoryUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """Xomashyo ma'lumotlarini yangilash (nomi, min qoldiq, kategoriya va h.k.)."""
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.inventory_of_company(db, item_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Material topilmadi")
    updated = crud.update_item(db, item_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok", "category": updated.category}


@app.post("/api/inventory/receipt")
def api_create_inventory_receipt(data: schemas.InventoryReceiptCreate, db: Session = Depends(get_db),
                                  current_user=Depends(auth.admin_or_warehouse)):
    """Ombor Kirim hujjati — bir nechta mahsulotni, qo'shimcha xarajatlar
    (Transport/Tushirish/Yuklash/Boshqa) bilan birga, BITTA yagona
    tranzaksiyada saqlaydi. Xato bo'lsa — hech narsa saqlanmaydi (rollback)."""
    who = current_user.full_name or current_user.username
    try:
        result = crud.create_inventory_receipt(
            db,
            items=[it.model_dump() for it in data.items],
            transport_cost=data.transport_cost, tushirish_cost=data.tushirish_cost,
            yuklash_cost=data.yuklash_cost, boshqa_cost=data.boshqa_cost,
            add_to_cost=data.add_to_cost, supplier_id=data.supplier_id,
            document_number=data.document_number, paid_now=data.paid_now,
            notes=data.notes, created_by=who, production_type=getattr(data, 'production_type', None),
            company_id=auth.company_id_of(current_user)
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kirim saqlashda xato: {str(e)}")


@app.post("/api/inventory/{item_id}/purchase")
def api_purchase_stock(item_id: int, data: schemas.StockPurchase, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """Ombor kirimi — xarid narxi bilan. O'rtacha vaznli narx hisoblanadi.
    paid_now > 0 bo'lsa — bir vaqtning o'zida xarid HAM yoziladi, HAM to'lov qilinadi,
    qolgan qismi avtomatik qarz sifatida qoladi."""
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.inventory_of_company(db, item_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Material topilmadi")
    who = current_user.full_name or current_user.username

    total_amount = round(data.quantity * data.price_per_unit)
    paid_now = min(data.paid_now, total_amount)   # ortiqcha to'lanmasin
    debt_remains = total_amount - paid_now
    is_credit = debt_remains > 0.01   # server o'zi hisoblaydi — frontenddan kelgan is_credit e'tiborga olinmaydi

    result = crud.purchase_stock(db, item_id, data.quantity, data.price_per_unit,
                                  purchased_by=who, notes=data.notes,
                                  supplier_id=data.supplier_id, is_credit=is_credit,
                                  volume_per_unit=data.volume_per_unit,
                                  payment_due_date=data.payment_due_date,
                                  is_opening_stock=data.is_opening_stock)
    if not result:
        raise HTTPException(status_code=404, detail="Xomashyo topilmadi")

    item = result["item"]

    # Transport — "O'z hisobimdan" tanlansa xarajat sifatida yoziladi
    if data.transport_payer == "self" and data.transport_cost > 0:
        crud.create_transport_expense(
            db,
            schemas.TransportExpenseCreate(
                amount=data.transport_cost,
                materials_note=item.item_name,
                notes=f"{item.item_name} xaridi bilan birga"
            ),
            created_by=who, company_id=auth.company_id_of(current_user)
        )

    # Hoziroq to'langan summa bo'lsa — darhol to'lov sifatida yoziladi (qarzdan ayiriladi)
    if is_credit and data.supplier_id and paid_now > 0:
        crud.create_supplier_payment(
            db,
            schemas.SupplierPaymentCreate(
                supplier_id=data.supplier_id,
                amount=paid_now,
                notes=f"{item.item_name} xaridi bilan bir vaqtda to'langan"
            ),
            paid_by=who, company_id=auth.company_id_of(current_user)
        )

    # Nasiya bo'lsa — kompaniya qarzi oshgani haqida ogohlantirish
    if is_credit and data.supplier_id:
        supplier = crud.get_supplier(db, data.supplier_id)
        if supplier:
            debt_info = crud.get_supplier_debt(db, data.supplier_id, company_id=auth.company_id_of(current_user))
            all_debt = sum(s["debt"] for s in crud.get_suppliers_with_debt(db, company_id=auth.company_id_of(current_user)))
            paid_line = f"✅ Hoziroq to'landi: {fmt_money(paid_now)} so'm\\n" if paid_now > 0 else ""
            msg = (
                f"🚚 *Nasiya xarid qilindi*\n\n"
                f"📦 {item.item_name}: {data.quantity:g} {item.unit} × {fmt_money(data.price_per_unit)}\n"
                f"💰 Jami summasi: {fmt_money(total_amount)} so'm\n"
                f"{paid_line}"
                f"\n🏪 Yetkazib beruvchi: *{supplier.name}*\n"
                f"🔴 Shu hamkorga qarz: {fmt_money(debt_info['debt'])} so'm\n"
                f"📊 Jami barcha qarz: {fmt_money(all_debt)} so'm\n\n"
                f"🏗 *PenoDecorPro* — {who}"
            )
            _send_telegram(msg)

    return {
        "status": "ok",
        "item_name": item.item_name,
        "new_quantity": float(item.stock_quantity),
        "old_price": result["old_price"],
        "new_price": result["new_price"],
        "purchase_total": result["purchase_total"],
        "paid_now": paid_now,
        "debt_remains": debt_remains,
        "price_changed": abs(result["old_price"] - result["new_price"]) > 0.01,
        "old_volume": result["old_volume"],
        "new_volume": result["new_volume"],
        "volume_changed": result["volume_changed"]
    }


@app.get("/api/inventory/purchases")
def api_get_purchases(item_id: Optional[int] = None, limit: int = 100,
                      db: Session = Depends(get_db), current_user=Depends(auth.inventory_view)):
    """Xaridlar tarixi."""
    items = crud.get_purchases(db, limit=limit, item_id=item_id, company_id=auth.company_id_of(current_user))
    return [{
        "id": p.id,
        "inventory_id": p.inventory_id,
        "item_name": p.item_name,
        "quantity": float(p.quantity),
        "unit": p.unit,
        "price_per_unit": float(p.price_per_unit),
        "total_amount": float(p.total_amount),
        "purchased_at": p.purchased_at.isoformat() if p.purchased_at else None,
        "purchased_by": p.purchased_by,
        "notes": p.notes,
        "receipt_id": p.receipt_id
    } for p in items]


@app.get("/api/inventory/purchase-stats")
def api_purchase_stats(year: Optional[int] = None, month: Optional[int] = None,
                       db: Session = Depends(get_db), current_user=Depends(auth.inventory_view)):
    """Material bo'yicha xarid statistikasi (oylik)."""
    return crud.get_purchase_stats(db, year=year, month=month, company_id=auth.company_id_of(current_user))


@app.post("/api/transport-expenses")
def api_create_transport(data: schemas.TransportExpenseCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Kirish transporti xarajatini qo'shish."""
    who = current_user.full_name or current_user.username
    exp = crud.create_transport_expense(db, data, created_by=who, company_id=auth.company_id_of(current_user))
    return {"status": "ok", "id": exp.id, "amount": float(exp.amount)}


@app.get("/api/transport-expenses")
def api_get_transport(limit: int = 100, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Kirish transporti tarixi."""
    items = crud.get_transport_expenses(db, limit=limit, company_id=auth.company_id_of(current_user))
    return [{
        "id": e.id,
        "amount": float(e.amount),
        "materials_note": e.materials_note,
        "expense_date": e.expense_date.isoformat() if e.expense_date else None,
        "created_by": e.created_by,
        "notes": e.notes
    } for e in items]


@app.delete("/api/transport-expenses/{exp_id}")
def api_delete_transport(exp_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    if not crud.delete_transport_expense(db, exp_id, company_id=auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


# ============================================================
# EMPLOYEES — Moslashuvchan hodim to'lovi
# ============================================================

@app.post("/api/employees")
def api_create_employee(data: schemas.EmployeeCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    # M1/M8-F1: xodim joriy adminning korxonasiga biriktiriladi — tenant
    # endi `create_employee()` ga BOSHIDAN uzatiladi (ilgari qaytgandan
    # keyin qo'yilardi va ichki commit vaqtida ustun bo'sh qolardi).
    emp = crud.create_employee(db, data, company_id=auth.company_id_of(current_user))
    return {"status": "ok", "id": emp.id}


@app.get("/api/employees")
def api_get_employees(only_active: bool = True, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    items = crud.get_employees(db, only_active=only_active,
                               company_id=auth.company_id_of(current_user))
    return [{
        "id": e.id, "name": e.name, "position": e.position,
        "pay_type": e.pay_type.value,
        "fixed_amount": float(e.fixed_amount or 0),
        "percent_value": float(e.percent_value or 0),
        "per_unit_rate": float(e.per_unit_rate or 0),
        "per_unit_type": e.per_unit_type,
        "extra_monthly": float(e.extra_monthly) if e.extra_monthly is not None else None,
        "production_type": e.production_type,
        "is_active": e.is_active,
        "notes": e.notes
    } for e in items]


@app.post("/api/employees/{employee_id}/advance")
def api_create_employee_advance(employee_id: int, amount: float, notes: Optional[str] = None,
                                  adv_date: Optional[str] = None,
                                  db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Hodimga avans (oldindan pul) berilganini qayd etadi.
    adv_date — YYYY-MM-DD formatida, ixtiyoriy (berilmasa — bugungi sana)."""
    # M1: xodim FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.employee_of_company(db, employee_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    parsed_date = None
    if adv_date:
        try:
            parsed_date = datetime.strptime(adv_date, "%Y-%m-%d")
        except ValueError:
            pass
    adv = crud.create_employee_advance(db, employee_id, amount, notes,
                                        given_by=current_user.full_name or current_user.username,
                                        adv_date=parsed_date)
    if not adv:
        raise HTTPException(status_code=404, detail="Hodim topilmadi")
    return {"status": "ok", "id": adv.id}


@app.get("/api/employees/{employee_id}/advances")
def api_get_employee_advances(employee_id: int, year: int, month: int,
                                db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Hodimga shu oyda berilgan barcha avanslar ro'yxati."""
    # M1: xodim FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.employee_of_company(db, employee_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    return {
        "advances": services.get_employee_advances_list(db, employee_id, year, month),
        "total": services.get_employee_advances_total(db, employee_id, year, month)
    }


@app.get("/api/employees/{employee_id}/monthly-adjustment")
def api_get_employee_adjustment(employee_id: int, year: int, month: int,
                                  db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Hodim uchun, shu oy uchun saqlangan qo'lda kamaytirish/bonusni qaytaradi."""
    # M1: xodim FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.employee_of_company(db, employee_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    adj = crud.get_employee_monthly_adjustment(db, employee_id, year, month)
    if not adj:
        return {"reduction_amount": 0, "reason": None, "bonus_amount": 0, "bonus_reason": None}
    return {
        "reduction_amount": float(adj.reduction_amount or 0), "reason": adj.reason,
        "bonus_amount": float(adj.bonus_amount or 0), "bonus_reason": adj.bonus_reason
    }


@app.post("/api/employees/{employee_id}/monthly-adjustment")
def api_set_employee_adjustment(employee_id: int, year: int, month: int,
                                  reduction_amount: Optional[float] = None, reason: Optional[str] = None,
                                  bonus_amount: Optional[float] = None, bonus_reason: Optional[str] = None,
                                  db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    # M1: xodim FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.employee_of_company(db, employee_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    """Hodim uchun, shu oy uchun qo'lda kamaytirish va/yoki bonusni yozadi/yangilaydi/o'chiradi."""
    who = current_user.full_name or current_user.username
    crud.set_employee_monthly_adjustment(db, employee_id, year, month, reduction_amount, reason,
                                          bonus_amount, bonus_reason, created_by=who)
    return {"status": "ok"}


@app.delete("/api/employees/advance/{advance_id}")
def api_delete_employee_advance(advance_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    # M1: avansning O'ZIDA company_id yo'q — u xodimga bog'langan.
    # Shuning uchun ota (xodim) orqali tekshiramiz.
    from models import EmployeeAdvance as _EA
    _adv = db.query(_EA).filter(_EA.id == advance_id).first()
    if not _adv or not auth.employee_of_company(
            db, _adv.employee_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Topilmadi")
    if not crud.delete_employee_advance(db, advance_id):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


@app.put("/api/employees/{emp_id}")
def api_update_employee(emp_id: int, data: schemas.EmployeeUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    # M1: xodim FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.employee_of_company(db, emp_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    who = current_user.full_name or current_user.username
    emp = crud.update_employee(db, emp_id, data, updated_by=who)
    if not emp:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


@app.get("/api/employees/{emp_id}/compensation-history")
def api_employee_compensation_history(emp_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Hodimning to'lov (oylik/foiz/birlik narxi) o'zgarishlar tarixi —
    eng yangisi birinchi bo'lib qaytadi."""
    # M1: xodim FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.employee_of_company(db, emp_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    from models import EmployeeCompensationHistory
    rows = db.query(EmployeeCompensationHistory).filter(
        EmployeeCompensationHistory.employee_id == emp_id
    ).order_by(EmployeeCompensationHistory.effective_year.desc(),
               EmployeeCompensationHistory.effective_month.desc(),
               EmployeeCompensationHistory.id.desc()).all()
    return [{
        "id": r.id,
        "effective_year": r.effective_year, "effective_month": r.effective_month,
        "pay_type": r.pay_type.value,
        "fixed_amount": float(r.fixed_amount or 0),
        "percent_value": r.percent_value,
        "per_unit_rate": float(r.per_unit_rate or 0),
        "per_unit_type": r.per_unit_type,
        "extra_monthly": float(r.extra_monthly) if r.extra_monthly else None,
        "reason": r.reason,
        "created_by": r.created_by,
        "created_at": r.created_at.strftime("%d.%m.%Y %H:%M") if r.created_at else None,
    } for r in rows]


@app.post("/api/employees/backfill-compensation-history")
def api_backfill_compensation_history(db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Bir martalik migratsiya — tarix yozuvi hali yo'q eski hodimlar
    uchun boshlang'ich to'lov tarixini yaratadi. Xavfsiz — bir necha marta
    bossa ham, allaqachon tarixi bor hodimlarga qayta tegilmaydi."""
    return crud.backfill_employee_compensation_history(
        db, company_id=auth.company_id_of(current_user))


@app.delete("/api/employees/{emp_id}")
def api_delete_employee(emp_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    # M1: xodim FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.employee_of_company(db, emp_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    who = current_user.full_name or current_user.username
    if not crud.delete_employee(db, emp_id, performed_by=who):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


@app.post("/api/employees/{emp_id}/restore")
def api_restore_employee(emp_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    # M1: xodim FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.employee_of_company(db, emp_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    who = current_user.full_name or current_user.username
    if not crud.restore_employee(db, emp_id, performed_by=who):
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    return {"status": "ok"}


@app.delete("/api/employees/{emp_id}/permanent")
def api_permanent_delete_employee(emp_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    # M1: xodim FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.employee_of_company(db, emp_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    who = current_user.full_name or current_user.username
    if not crud.permanent_delete_employee(db, emp_id, performed_by=who):
        raise HTTPException(status_code=404, detail="Xodim topilmadi (avval yumshoq o'chirilgan bo'lishi kerak)")
    return {"status": "ok"}


@app.post("/api/employees/{emp_id}/set-login")
def api_set_employee_login(emp_id: int, phone: str = Form(...), pin: str = Form(...),
                            db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Admin — xodimga telefon+PIN belgilaydi, shu orqali u o'z paneliga kira oladi."""
    # M1: xodim FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.employee_of_company(db, emp_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    if len(pin.strip()) != 4 or not pin.strip().isdigit():
        raise HTTPException(status_code=400, detail="PIN kod aynan 4 xonali raqam bo'lishi kerak")
    try:
        emp = crud.set_employee_login(db, emp_id, phone, pin)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Bu telefon raqami boshqa xodimda band")
    if not emp:
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    return {"status": "ok"}


# ============================================================
# XODIM PANELI — telefon+PIN bilan kirish, avans yozish
# ============================================================

@app.get("/hodim/login", response_class=HTMLResponse)
async def hodim_login_page(request: Request, db: Session = Depends(get_db)):
    emp = auth.get_current_employee(request, db)
    if emp:
        return RedirectResponse("/hodim", status_code=302)
    return templates.TemplateResponse(request, "hodim_login.html", {"error": None})


@app.post("/hodim/login")
async def hodim_login_submit(request: Request, phone: str = Form(...), pin: str = Form(...),
                              korxona: str = Form(""), db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:250]

    rl = crud.check_login_rate_limit(db, phone, ip)
    if rl["blocked"]:
        return templates.TemplateResponse(request, "hodim_login.html", {
            "error": f"Juda ko'p noto'g'ri urinish. {rl['retry_after_minutes']} daqiqadan so'ng qayta urining."
        })

    # M1 (CRITICAL): korxona kontekstisiz kirishga yo'l yo'q.
    # Mijoz yuborgan kod QIDIRUV KALITI, unga ishonilmaydi — korxona
    # bazadan topiladi. Bitta korxonali o'rnatmada kod bo'sh bo'lishi mumkin.
    _korxona = crud.resolve_company_by_code(db, korxona)
    if not _korxona:
        crud.log_login_attempt(db, phone, success=False, ip_address=ip, user_agent=ua)
        return templates.TemplateResponse(request, "hodim_login.html", {
            "error": "Korxona kodi topilmadi. Kodni administratordan so'rang."
        })

    emp = crud.authenticate_employee(db, phone, pin, company_id=_korxona.id)
    if not emp:
        crud.log_login_attempt(db, phone, success=False, ip_address=ip, user_agent=ua)
        return templates.TemplateResponse(request, "hodim_login.html", {"error": "Telefon yoki PIN noto'g'ri!"})

    crud.log_login_attempt(db, phone, success=True, ip_address=ip, user_agent=ua)
    token = auth.create_employee_session(db, emp.id)
    response = RedirectResponse("/hodim", status_code=302)
    response.set_cookie(key="emp_session_token", value=token, httponly=True,
                         max_age=3600 * auth.EMPLOYEE_SESSION_HOURS, samesite="lax", secure=True)
    return response


@app.get("/hodim/logout")
async def hodim_logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("emp_session_token")
    if token:
        auth.delete_employee_session(db, token)
    response = RedirectResponse("/hodim/login", status_code=302)
    response.delete_cookie("emp_session_token")
    return response


@app.get("/hodim", response_class=HTMLResponse)
async def hodim_panel(request: Request, db: Session = Depends(get_db)):
    emp = auth.get_current_employee(request, db)
    if not emp:
        return RedirectResponse("/hodim/login", status_code=302)
    return templates.TemplateResponse(request, "hodim_panel.html", {"employee": emp})


@app.get("/api/hodim/my-requests")
def api_hodim_my_requests(db: Session = Depends(get_db), emp=Depends(auth.require_employee_login)):
    return crud.get_employee_own_requests(db, emp.id)


@app.post("/api/hodim/advance-request")
def api_hodim_advance_request(amount: float = Form(...), requested_date: str = Form(...),
                               notes: str = Form(None), db: Session = Depends(get_db),
                               emp=Depends(auth.require_employee_login)):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Summa noto'g'ri")
    try:
        rdate = datetime.strptime(requested_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Sana noto'g'ri")
    req = crud.create_advance_request(db, emp.id, amount, rdate, notes)
    return {"status": "ok", "id": req.id}


# ============================================================
# ADMIN — xodim yozgan avans so'rovlarini tasdiqlash
# ============================================================

@app.get("/api/admin/pending-advance-requests")
def api_pending_advance_requests(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return crud.get_pending_advance_requests(db, company_id=auth.company_id_of(current_user))


@app.post("/api/admin/advance-requests/{request_id}/confirm")
def api_confirm_advance_request(request_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    result = crud.confirm_advance_request(db, request_id, current_user.full_name or current_user.username,
                                         company_id=auth.company_id_of(current_user))
    if not result:
        raise HTTPException(status_code=404, detail="So'rov topilmadi yoki allaqachon ko'rib chiqilgan")
    return result


@app.post("/api/admin/advance-requests/{request_id}/reject")
def api_reject_advance_request(request_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    if not crud.reject_advance_request(db, request_id, current_user.full_name or current_user.username,
                                      company_id=auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="So'rov topilmadi yoki allaqachon ko'rib chiqilgan")
    return {"status": "ok"}


# ============================================================
# MASTER KPI — Yillik KPI (sotuvdan %)
# ============================================================

@app.put("/api/masters/{master_id}/kpi")
def api_update_master_kpi(master_id: int, data: schemas.MasterKpiUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    m = crud.update_master_kpi(db, master_id, data.kpi_percent,
                               company_id=auth.company_id_of(current_user))
    if not m:
        raise HTTPException(status_code=404, detail="Usta topilmadi")
    return {"status": "ok", "kpi_percent": m.kpi_percent}


@app.get("/api/settings/ehson-percent")
def api_get_ehson_percent(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    """Ehson (xayriya) foizini o'qiydi — admin belgilagan, sof foydadan ajratiladigan ulush."""
    percent = crud.get_setting(db, "ehson_percent", "0", company_id=auth.company_id_of(current_user))
    return {"ehson_percent": float(percent or 0)}


@app.put("/api/settings/ehson-percent")
def api_set_ehson_percent(percent: float = Form(...), db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Ehson foizini belgilaydi — faqat Admin o'zgartira oladi."""
    if percent < 0 or percent > 100:
        raise HTTPException(status_code=400, detail="Foiz 0 dan 100 gacha bo'lishi kerak")
    crud.set_setting(db, "ehson_percent", str(percent), company_id=auth.company_id_of(current_user))
    return {"status": "ok", "ehson_percent": percent}


@app.get("/api/masters/kpi-report")
def api_masters_kpi_report(year: Optional[int] = None, include_inactive: bool = False,
                            db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    y = year or datetime.now().year
    return crud.get_masters_kpi_report(db, y, include_inactive=include_inactive,
                                      company_id=auth.company_id_of(current_user))


@app.get("/api/masters/{master_id}/kpi-detail")
def api_master_kpi_detail(master_id: int, year: Optional[int] = None,
                           db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    from datetime import datetime
    y = year or datetime.now().year
    return crud.get_master_kpi_detail(db, master_id, y,
                                     company_id=auth.company_id_of(current_user))


# ── "Sovg'a davri" (2026-09-12, savdo-summasi asosidagi, davriy) ──────
@app.get("/api/gift-period")
def api_get_gift_period(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return crud.get_gift_period_overview(db, company_id=auth.company_id_of(current_user))


@app.post("/api/gift-period/open")
def api_open_gift_period(data: dict, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    who = current_user.full_name or current_user.username
    result = crud.open_gift_period(db, data.get("tiers") or [], master_ids=data.get("master_ids"),
                                  performed_by=who, company_id=auth.company_id_of(current_user))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Xato yuz berdi"))
    return result


@app.put("/api/gift-period/tier/{tier_id}")
def api_update_gift_period_tier(tier_id: int, data: dict, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    result = crud.update_gift_period_tier(db, tier_id, data.get("gift_name"), data.get("threshold_amount"),
                                         company_id=auth.company_id_of(current_user))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Xato yuz berdi"))
    return result


@app.post("/api/gift-period/add-master")
def api_add_master_to_gift_period(data: dict, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    """2026-09-16: davrni to'xtatmasdan, yangi/faollashtirilgan ustani
    aniq-ishtirokchi ro'yxatiga qo'shish uchun."""
    who = current_user.full_name or current_user.username
    result = crud.add_master_to_active_gift_period(db, data.get("master_id"), performed_by=who,
                                                  company_id=auth.company_id_of(current_user))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Xato yuz berdi"))
    return result


@app.post("/api/gift-period/close")
def api_close_gift_period(data: dict = Body(default={}), db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    who = current_user.full_name or current_user.username
    force = bool((data or {}).get("force"))
    result = crud.close_gift_period(db, performed_by=who, force=force,
                                   company_id=auth.company_id_of(current_user))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result)
    return result


@app.post("/api/gift-period/redeem/{master_id}/{tier_id}")
def api_redeem_gift_period_tier(master_id: int, tier_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    who = current_user.full_name or current_user.username
    result = crud.redeem_gift_period_tier(db, master_id, tier_id, performed_by=who,
                                         company_id=auth.company_id_of(current_user))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Xato yuz berdi"))
    return result


@app.get("/api/transport-stats")
def api_transport_stats(year: Optional[int] = None, month: Optional[int] = None,
                        db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Transport xarajatlari statistikasi (kirish + chiqish)."""
    return crud.get_transport_stats(db, year=year, month=month, company_id=auth.company_id_of(current_user))


# ============================================================
# SUPPLIERS — Yetkazib beruvchilar va nasiya qarzi
# ============================================================

@app.get("/suppliers", response_class=HTMLResponse)
async def suppliers_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    return templates.TemplateResponse(request, "suppliers.html", {"current_user": current_user, "active_page": "suppliers"})


@app.get("/suppliers/receive", response_class=HTMLResponse)
async def supplier_receive_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """Yetkazib beruvchidan mahsulot kirim qilish — to'liq sahifa ko'rinishi.
    Backend/API o'zgarmagan — xuddi suppliers.html'dagi (sinalgan) xarid
    mexanizmining o'zi, faqat kattaroq, tartibli sahifa dizaynida."""
    suppliers = crud.get_suppliers(db, company_id=auth.company_id_of(current_user))
    return templates.TemplateResponse(request, "supplier_receive.html", {
        "current_user": current_user, "active_page": "supplier_receive", "suppliers": suppliers
    })


@app.post("/api/suppliers")
def api_create_supplier(data: schemas.SupplierCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    # M8/F1a: ta'minotchi joriy adminning korxonasiga biriktiriladi.
    s = crud.create_supplier(db, data, company_id=auth.company_id_of(current_user))
    return {"status": "ok", "id": s.id}


@app.get("/api/suppliers")
def api_get_suppliers(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    return crud.get_suppliers_with_debt(db, company_id=auth.company_id_of(current_user))


@app.put("/api/suppliers/{supplier_id}")
def api_update_supplier(supplier_id: int, data: schemas.SupplierUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.supplier_of_company(db, supplier_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Ta'minotchi topilmadi")
    s = crud.update_supplier(db, supplier_id, data)
    if not s:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


@app.delete("/api/suppliers/{supplier_id}")
def api_delete_supplier(supplier_id: int, force: bool = False, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """Yetkazib beruvchini o'chirish. Qarzi bo'lsa force=true kerak."""
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.supplier_of_company(db, supplier_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Ta'minotchi topilmadi")
    result = crud.delete_supplier(db, supplier_id, force=force)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return {"status": "ok"}


@app.get("/api/suppliers/{supplier_id}/history")
def api_supplier_history(supplier_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None,
                         page: int = 1, page_size: int = 20,
                         db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """Yetkazib beruvchi tarixi. start_date/end_date — YYYY-MM-DD formatida (ixtiyoriy).
    page/page_size — xaridlar ro'yxati sahifalanadi (standart: 20 tadan)."""
    from datetime import datetime as dt
    from database import TASHKENT_OFFSET

    s = crud.get_supplier(db, supplier_id, company_id=auth.company_id_of(current_user))
    if not s:
        raise HTTPException(status_code=404, detail="Topilmadi")

    # 2026-09-17 (audit topilmasi): foydalanuvchi kiritgan sana — Toshkent
    # taqvimi bo'yicha ("bugun 2026-09-01" deganda, u albatta Toshkent
    # kunini nazarda tutadi). Bazadagi vaqtlar esa UTC'da saqlanadi,
    # shuning uchun solishtirishdan oldin -5 soat siljitiladi.
    sd = (dt.strptime(start_date, "%Y-%m-%d") - TASHKENT_OFFSET) if start_date else None
    ed = (dt.strptime(end_date, "%Y-%m-%d") - TASHKENT_OFFSET) if end_date else None

    history = crud.get_supplier_history(db, supplier_id, start_date=sd, end_date=ed,
                                         page=page, page_size=page_size,
                                         company_id=auth.company_id_of(current_user))
    return {"name": s.name, "phone": s.phone, **history}


@app.put("/api/inventory/purchases/{purchase_id}")
def api_update_purchase(purchase_id: int, data: schemas.PurchaseUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """Xarid yozuvini tahrirlash — ombordagi joriy miqdor/narxga ta'sir qilmaydi."""
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.purchase_of_company(db, purchase_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Xarid topilmadi")
    updated = crud.update_purchase(db, purchase_id, data.model_dump(exclude_unset=True), company_id=auth.company_id_of(current_user))
    if not updated:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok", "total_amount": float(updated.total_amount)}


@app.delete("/api/inventory/purchases/{purchase_id}")
def api_delete_purchase(purchase_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """Xarid yozuvini o'chirish — ham OMBORdan miqdorni qaytaradi, ham pul oqimidan olib tashlaydi (to'liq bekor qilish)."""
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.purchase_of_company(db, purchase_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Xarid topilmadi")
    if not crud.delete_purchase(db, purchase_id, company_id=auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


@app.post("/api/suppliers/{supplier_id}/payment")
def api_supplier_payment(supplier_id: int, data: schemas.SupplierPaymentCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.supplier_of_company(db, supplier_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Ta'minotchi topilmadi")
    who = current_user.full_name or current_user.username
    data.supplier_id = supplier_id
    try:
        p = crud.create_supplier_payment(db, data, paid_by=who, company_id=auth.company_id_of(current_user))
    except crud.OverpaymentWarning as w:
        raise HTTPException(status_code=409, detail={
            "type": "overpayment_warning",
            "message": f"Kiritilgan summa ({w.amount:,.0f} so'm) qarzdan ({w.debt:,.0f} so'm) {w.excess:,.0f} so'mga ko'p. Shunday ham davom etasizmi?",
            "amount": w.amount, "debt": w.debt, "excess": w.excess
        })
    debt_info = crud.get_supplier_debt(db, supplier_id, company_id=auth.company_id_of(current_user))
    return {"status": "ok", "payment_id": p.id, **debt_info}


@app.delete("/api/suppliers/payments/{payment_id}")
def api_delete_supplier_payment(payment_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    if not crud.delete_supplier_payment(db, payment_id, company_id=auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


@app.get("/api/suppliers/debt-total")
def api_suppliers_debt_total(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """Barcha yetkazib beruvchilarga jami qarz — dashboard uchun."""
    suppliers = crud.get_suppliers_with_debt(db, company_id=auth.company_id_of(current_user))
    total = sum(s["debt"] for s in suppliers)
    return {"total_debt": total, "supplier_count": sum(1 for s in suppliers if s["debt"] > 0)}


@app.get("/api/suppliers/due-dates")
def api_suppliers_due_dates(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """Qarz to'lash muddatlari — Dashboard ogohlantirishi uchun."""
    return crud.get_supplier_payment_due_dates(db, company_id=auth.company_id_of(current_user))


@app.get("/api/suppliers/{supplier_id}/purchased-items")
def api_supplier_purchased_items(supplier_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """Shu yetkazib beruvchidan ilgari xarid qilingan materiallar — Kirim sahifasida qulaylik uchun."""
    return crud.get_supplier_purchased_items(db, supplier_id, company_id=auth.company_id_of(current_user))


@app.get("/api/inventory/purchase-trend")
def api_purchase_trend(months: int = 6, db: Session = Depends(get_db), current_user=Depends(auth.inventory_view)):
    """Oxirgi N oy xarid tendensiyasi."""
    return crud.get_purchase_stats_range(db, months=months, company_id=auth.company_id_of(current_user))


@app.post("/api/inventory/{item_id}/price")
def api_update_price(item_id: int, data: dict, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.inventory_of_company(db, item_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Material topilmadi")
    item = db.query(crud.Inventory).filter(crud.Inventory.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Topilmadi")
    item.price_per_unit = data.get("price_per_unit", 0)
    if "volume_per_unit" in data:
        item.volume_per_unit = data.get("volume_per_unit")
    db.commit()
    return {"status": "ok", "price_per_unit": item.price_per_unit}


@app.post("/api/inventory/{item_id}/min-stock")
def api_update_min_stock(item_id: int, data: dict, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """Xomashyoning 'kam qoldi' ogohlantirishi ishga tushadigan chegarasini
    (min_stock) o'zgartiradi — admin/ombor xodimi o'zi belgilaydi."""
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.inventory_of_company(db, item_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Material topilmadi")
    item = db.query(crud.Inventory).filter(crud.Inventory.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Topilmadi")
    min_stock = data.get("min_stock")
    if min_stock is None or float(min_stock) < 0:
        raise HTTPException(status_code=400, detail="Noto'g'ri qiymat")
    item.min_stock = float(min_stock)
    db.commit()
    return {"status": "ok", "min_stock": item.min_stock}


@app.post("/api/inventory/full-stock-report")
def api_full_stock_report(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    from models import Inventory as Inv
    # M3: SMS hisoboti FAQAT joriy korxonaning materiallari bo'yicha.
    items = db.query(Inv).filter(
        Inv.company_id == auth.company_id_of(current_user)
    ).order_by(Inv.item_name).all()
    if not items:
        return {"message": "Omborxona bo'sh!"}
    yetarli = []
    kam = []
    for item in items:
        qty = float(item.stock_quantity)
        min_q = float(item.min_stock or 0)
        if min_q > 0 and qty <= min_q:
            emoji = "🔴" if qty <= min_q * 0.5 else "🟡"
            kam.append(f"{emoji} {item.item_name}: {qty:.1f} {item.unit}")
        else:
            yetarli.append(f"✅ {item.item_name}: {qty:.1f} {item.unit}")
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    msg = f"📋 *Ombor hisoboti*\n_{now}_\n\n"
    if kam:
        msg += f"━━━ KAM QOLGANLAR ({len(kam)} ta) ━━━\n" + "\n".join(kam) + "\n\n"
    msg += f"━━━ YETARLI ({len(yetarli)} ta) ━━━\n" + "\n".join(yetarli)
    msg += f"\n\n🏗 *PenoDecorPro* — Andijon"
    _send_telegram(msg)
    return {"message": f"Ombor hisoboti yuborildi! ({len(items)} ta xomashyo)"}


@app.post("/api/inventory/low-stock-alert")
def api_low_stock_alert(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    low_items = crud.get_low_stock_items(db, company_id=auth.company_id_of(current_user))
    if not low_items:
        return {"sent": False, "message": "Barcha xomashyolar yetarli — SMS yuborilmadi!"}
    lines = []
    for item in low_items:
        qty = float(item.stock_quantity)
        min_q = float(item.min_stock)
        deficit = min_q - qty
        emoji = "🔴" if qty <= min_q * 0.5 else "🟡"
        lines.append(f"{emoji} {item.item_name}: {qty:.1f} {item.unit} qoldi (min: {min_q:.0f}, yetishmaydi: {deficit:.1f})")
    msg = f"⚠️ *Ombor ogohlantirishlari!*\n\n━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines) + f"\n━━━━━━━━━━━━━━━━━━━\n\nZudlik bilan buyurtma bering! 🚨\n\n🏗 *PenoDecorPro* — Andijon"
    _send_telegram(msg)
    return {"sent": True, "message": f"{len(low_items)} ta kam qolgan xomashyo haqida SMS yuborildi!"}


# ═══════════════════════════════════════════════════════════════
# AVTOMATIK, KUNLIK "kam qolganlar" ogohlantirishi — bu, LOGIN
# TALAB QILMAYDI (tashqi, bepul "vaqt bo'yicha chaqiruvchi" xizmat,
# masalan cron-job.org, buni har kuni bir marta chaqiradi). Xavfsizlik
# uchun, maxfiy kalit (CRON_SECRET env var) talab qilinadi — shu kalitni
# bilmagan hech kim, bu manzilni chaqira olmaydi.
# ═══════════════════════════════════════════════════════════════
CRON_SECRET = os.environ.get("CRON_SECRET", "")

@app.get("/api/cron/low-stock-check")
def api_cron_low_stock_check(secret: str = "", db: Session = Depends(get_db)):
    if not CRON_SECRET:
        raise HTTPException(status_code=503, detail="CRON_SECRET Railway'da o'rnatilmagan")
    if secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Noto'g'ri maxfiy kalit")
    # 2026-09-19 — Faza 3: ilgari bu so'rov KORXONA FILTRISIZ edi, ya'ni
    # bitta ogohlantirish xabarida BARCHA korxonalarning materiallari
    # aralashib ketardi. Endi har bir korxona alohida ko'rib chiqiladi.
    # (Hozircha yagona Telegram manzili bor, shuning uchun xabarga korxona
    # nomi qo'shiladi; har korxonaga alohida manzil — Telegram arxitekturasi
    # qaroridan keyin.)
    from production_models import Company as _Co
    _companies = [c.id for c in db.query(_Co).all()] or [None]
    _all_lines, _sent_any = [], False
    _per_company = {}
    for _cid in _companies:
        low_items = crud.get_low_stock_items(db, company_id=_cid)
        if not low_items:
            continue
        _sent_any = True
        _cname = None
        try:
            _cname = db.query(_Co).filter(_Co.id == _cid).first().name
        except Exception:
            pass
        _per_company.setdefault(_cid, [])
        if len(_companies) > 1 and _cname:
            _all_lines.append(f"\n🏢 *{_cname}*")
        for item in low_items:
            qty = float(item.stock_quantity)
            min_q = float(item.min_stock)
            deficit = min_q - qty
            emoji = "🔴" if qty <= min_q * 0.5 else "🟡"
            _satr = (f"{emoji} {item.item_name}: {qty:.1f} {item.unit} qoldi "
                     f"(min: {min_q:.0f}, yetishmaydi: {deficit:.1f})")
            _all_lines.append(_satr)
            _per_company[_cid].append(_satr)
    if not _sent_any:
        return {"sent": False, "message": "Barcha xomashyolar yetarli"}
    # Faza 3 (2-qadam): har korxonaga O'Z boti/chat manzili orqali alohida
    # xabar yuboriladi — korxonalar bir-birining ombor holatini ko'rmaydi.
    for _cid2, _lines2 in _per_company.items():
        if not _lines2:
            continue
        _msg2 = ("⚠️ *Kunlik ombor ogohlantirishi!*\n\n━━━━━━━━━━━━━━━━━━━\n"
                 + "\n".join(_lines2)
                 + "\n━━━━━━━━━━━━━━━━━━━\n\nZudlik bilan buyurtma bering! 🚨")
        _send_telegram(_msg2, company_id=_cid2)
    return {"sent": True, "companies": len(_per_company),
            "items": sum(len(v) for v in _per_company.values())}
    low_items = []
    lines = _all_lines
    for item in low_items:
        qty = float(item.stock_quantity)
        min_q = float(item.min_stock)
        deficit = min_q - qty
        emoji = "🔴" if qty <= min_q * 0.5 else "🟡"
        lines.append(f"{emoji} {item.item_name}: {qty:.1f} {item.unit} qoldi (min: {min_q:.0f}, yetishmaydi: {deficit:.1f})")
    msg = f"⚠️ *Kunlik ombor ogohlantirishi!*\n\n━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines) + f"\n━━━━━━━━━━━━━━━━━━━\n\nZudlik bilan buyurtma bering! 🚨\n\n🏗 *PenoDecorPro* — Andijon"
    _send_telegram(msg)
    return {"sent": True, "message": f"{len(low_items)} ta kam qolgan xomashyo haqida xabar yuborildi"}


# ═══════════════════════════════════════════════════════════════
# AVTOMATIK, KUNLIK "eski sessiyalarni tozalash" — bu ham, "kam
# qolganlar" tekshiruvi kabi, cron-job.org orqali, har kuni bir marta
# chaqiriladi. XAVFSIZ: faqat, muddati ALLAQACHON o'tgan (endi
# ishlatilmaydigan) tizimga kirish yozuvlarini o'chiradi — HOZIR
# tizimda ishlab turgan hech kimning sessiyasiga tegilmaydi.
# ═══════════════════════════════════════════════════════════════
@app.get("/api/cron/cleanup-sessions")
def api_cron_cleanup_sessions(secret: str = "", db: Session = Depends(get_db)):
    if not CRON_SECRET:
        raise HTTPException(status_code=503, detail="CRON_SECRET Railway'da o'rnatilmagan")
    if secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Noto'g'ri maxfiy kalit")
    result = auth.cleanup_expired_sessions(db)
    total = result["user_sessions"] + result["employee_sessions"]
    return {"cleaned": True, "message": f"{total} ta eski sessiya tozalandi", "detail": result}


# ═══════════════════════════════════════════════════════════════
# VAQTINCHALIK YORDAMCHI: to'g'ri Telegram Chat ID'ni topish uchun.
# Foydalanish: 1) Telegram'da botga (masalan @penodecorprobot) istalgan
# xabar yozing (masalan "salom"). 2) Shu manzilni oching:
# /api/cron/find-chat-id?secret=SIZNING_KALITINGIZ — u yerda, so'nggi
# yozgan odamning ismi va Chat ID'si ko'rinadi. Chat ID'ni topgach, buni
# TELEGRAM_COATING_ID o'rniga ishlatish uchun Claude'ga ayting.
# ═══════════════════════════════════════════════════════════════
@app.get("/api/cron/find-chat-id")
def api_find_chat_id(secret: str = ""):
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Noto'g'ri maxfiy kalit")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return {"error": "TELEGRAM_BOT_TOKEN Railway'da o'rnatilmagan"}
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        results = []
        for u in data.get("result", []):
            msg = u.get("message") or u.get("channel_post")
            if not msg:
                continue
            chat = msg.get("chat", {})
            results.append({
                "chat_id": chat.get("id"),
                "chat_type": chat.get("type"),
                "name": chat.get("title") or f"{chat.get('first_name','')} {chat.get('last_name','')}".strip(),
                "username": chat.get("username"),
                "text": msg.get("text")
            })
        if not results:
            return {"message": "Hech qanday xabar topilmadi. Avval botga Telegram'da biror xabar yozing, keyin bu sahifani qayta oching."}
        return {"found": results[-10:]}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/api/inventory/{item_id}")
def api_delete_item(item_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.inventory_of_company(db, item_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Material topilmadi")
    result = crud.delete_item(db, item_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return {"status": "ok", "soft": result["soft"], "message": result["message"]}


@app.post("/api/recipes", response_model=schemas.RecipeRead)
def api_create_recipe(recipe: schemas.RecipeCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    # M8/F1a: retsept joriy adminning korxonasiga biriktiriladi.
    return crud.create_recipe(db, recipe, company_id=auth.company_id_of(current_user))


@app.put("/api/recipes/{recipe_id}", response_model=schemas.RecipeRead)
def api_update_recipe(recipe_id: int, data: schemas.RecipeCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.recipe_of_company(db, recipe_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Retsept topilmadi")
    recipe = crud.update_recipe(db, recipe_id, data)
    if not recipe:
        raise HTTPException(status_code=404, detail="Retsept topilmadi")
    return recipe


@app.post("/api/recipes/{recipe_id}/image")
def api_upload_recipe_image(recipe_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                             current_user=Depends(auth.admin_or_warehouse)):
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.recipe_of_company(db, recipe_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Retsept topilmadi")
    from models import Recipe
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Retsept topilmadi")
    url = _save_upload(file, "recipes", ALLOWED_IMAGE_EXT)
    recipe.image_url = url
    db.commit()
    return {"image_url": url}


@app.delete("/api/recipes/{recipe_id}")
def api_delete_recipe(recipe_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    from models import Recipe
    # M3: retsept FAQAT joriy korxonadan (aks holda 404).
    recipe = db.query(Recipe).filter(
        Recipe.id == recipe_id,
        Recipe.company_id == auth.company_id_of(current_user)).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Retsept topilmadi")
    db.delete(recipe)
    db.commit()
    return {"status": "ok"}


@app.get("/api/recipes", response_model=List[schemas.RecipeRead])
def api_get_recipes(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    return crud.get_recipes(db, company_id=auth.company_id_of(current_user))


@app.post("/api/projects", response_model=schemas.ProjectRead)
def api_create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    # M8/F1a: loyiha joriy adminning korxonasiga biriktiriladi.
    return crud.create_project(db, project, company_id=auth.company_id_of(current_user))


@app.get("/api/projects", response_model=List[schemas.ProjectRead])
def api_get_projects(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return crud.get_projects(db, company_id=auth.company_id_of(current_user))


@app.put("/api/projects/{project_id}", response_model=schemas.ProjectRead)
def api_update_project(project_id: int, project: schemas.ProjectUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.project_of_company(db, project_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    updated = crud.update_project(db, project_id, project)
    if not updated:
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    return updated


@app.delete("/api/projects/{project_id}")
def api_delete_project(project_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.project_of_company(db, project_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    who = current_user.full_name or current_user.username
    if not crud.delete_project(db, project_id, performed_by=who):
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    return {"status": "ok"}


@app.post("/api/orders/coating-notify-new")
def api_coating_notify_with_loy(order_id: int, loy_kg: float, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    pass


@app.post("/api/orders", response_model=schemas.OrderRead)
def api_create_order(order: schemas.OrderCreate, loy_kg: Optional[float] = None,
                      confirm_shortage: bool = False,
                      db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    check = services.check_inventory_for_order(db, order)
    # M4: tayyor mahsulot yetarliligi FAQAT joriy korxona ombori bo'yicha.
    fcheck = crud.check_finished_for_order(db, order.items,
                                           company_id=auth.company_id_of(current_user))
    lcheck = services.check_loy_ingredients_for_order(db, order.recipe_id, loy_kg or 0)

    all_shortages = (list(check.get("shortages", []))
                      + list(fcheck.get("shortages", [])) + list(lcheck.get("shortages", [])))
    if all_shortages and not confirm_shortage:
        raise HTTPException(status_code=409, detail={
            "type": "stock_shortage_warning",
            "message": "Omborda yetishmayotgan xomashyo bor. Shunday ham davom etasizmi?",
            "shortages": all_shortages
        })
    new_order = crud.create_order(db, order)
    is_draft = getattr(order, 'is_draft', False)
    if not is_draft:
        services.deduct_inventory_for_order(db, new_order)
    low_items = crud.get_low_stock_items(db) if not is_draft else []
    if low_items:
        lines = []
        for item in low_items:
            qty = float(item.stock_quantity)
            min_q = float(item.min_stock)
            deficit = min_q - qty
            emoji = "🔴" if qty <= min_q * 0.5 else "🟡"
            lines.append(f"{emoji} {item.item_name}: {qty:.1f} {item.unit} qoldi (min: {min_q:.0f}, yetishmaydi: {deficit:.1f})")
        msg = f"⚠️ *Ombor ogohlantirishlari!*\n\n*{new_order.order_number}* buyurtmadan keyin:\n\n━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines) + f"\n━━━━━━━━━━━━━━━━━━━\n\nZudlik bilan buyurtma bering! 🚨\n\n🏗 *PenoDecorPro* — Andijon"
        _send_telegram(msg)
    return new_order


@app.get("/api/orders", response_model=List[schemas.OrderRead])
def api_get_orders(project_id: Optional[int] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return crud.get_orders(db, project_id=project_id,
                           company_id=auth.company_id_of(current_user))


@app.get("/api/orders/pinned")
def api_get_pinned_orders(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    # MUHIM: bu — statik yo'l, shuning uchun quyidagi /api/orders/{order_id}
    # (dinamik) marshrutdan OLDIN turishi SHART — aks holda FastAPI
    # "pinned" so'zini order_id sifatida ushlab, xato qaytaradi (2026-09-13
    # da aynan shu xato topilib, shu yerga ko'chirilgan edi).
    return crud.get_pinned_orders(db, company_id=auth.company_id_of(current_user))


@app.get("/api/orders/{order_id}")
def api_get_order(order_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    order = crud.get_order(db, order_id, company_id=auth.company_id_of(current_user))
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

    return {
        "id": order.id,
        "order_number": order.order_number,
        "project_id": order.project_id,
        "order_type": order.order_type.value if order.order_type else None,
        "status": order.status.value if order.status else None,
        "total_amount": float(order.total_amount or 0),
        "agreed_amount": float(order.agreed_amount or order.total_amount or 0),
        "discount_percent": order.discount_percent or 0,
        "payment_status": order.payment_status.value if order.payment_status else "unpaid",
        "paid_amount": order.paid_amount,
        "debt_amount": order.debt_amount,
        "is_archived": bool(order.is_archived),
        "is_draft": order.status == OrderStatus.DRAFT if order.status else False,
        "delivery_percent": order.delivery_percent,
        "master_id": order.master_id,
        "master_name": order.master.name if order.master else None,
        "client_name": order.project.client_name if order.project else None,
        "project_name": order.project.project_name if order.project else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "deadline": order.deadline.isoformat() if order.deadline else None,
        "base_price": float(order.base_price) if order.base_price is not None else None,
        "closed_at": order.closed_at.isoformat() if order.closed_at else None,
        # 2026-09-17: Milestone 4 — Production/MRP tayyorlik ko'rsatkichi
        # (Order.status'ga umuman tegishli emas — faqat ko'rsatish uchun).
        "mrp_readiness": production_service.get_order_mrp_readiness(db, order.id),
        "notes": order.notes,
        "items": [{
            "id": i.id,
            "name": i.name,
            "category": i.category,
            "width": i.width,
            "thickness": i.thickness,
            "length": i.length,
            "quantity": i.quantity,
            "is_coated": i.is_coated,
            "unit_price": float(i.unit_price or 0),
            "total_price": float(i.total_price or 0),
            "penoplast_id": i.penoplast_id,
            "penoplast_name": i.penoplast.item_name if i.penoplast else None,
            "price_per_m3": float(i.price_per_m3) if i.price_per_m3 else None,
            "notes": i.notes,
            "recipe_id": i.recipe_id,
            "finished_product_id": i.finished_product_id,
            "product_type_id": getattr(i, 'product_type_id', None),
            "order_qty_normalized": i.order_qty_normalized,
            "delivery_unit": i.delivery_unit,
            "price_per_unit_final": round(float(i.total_price or 0) / i.order_qty_normalized) if i.order_qty_normalized else 0,
            "cost_price_per_unit": services.get_order_item_unit_cost(db, order, i),
            "cost_price_per_unit_no_coating": services.get_order_item_unit_cost(db, order, i, include_coating=False),
            # MUHIM: Ichki qo'shimcha detallar — bu yerga QO'SHILMASA, bu
            # endpoint (buyurtmani TAHRIRLASH uchun ochilganda ishlatiladi)
            # ularni frontendga umuman yubormaydi. Natijada: tahrirlash
            # formasi ochilganda ichki detal ko'rinmay qoladi VA agar shu
            # holatda saqlansa — mavjud ichki detal (narxi bilan birga)
            # BUTUNLAY YO'QOLIB QOLARDI (update_order_full() bo'sh ro'yxat
            # bilan eskisini almashtiradi). Shuning uchun bu yerda ham,
            # OrderItemRead (schemas.py) bilan bir xil shaklda, qaytariladi.
            "sub_details": [{
                "id": sd.id,
                "name": sd.name,
                "category": sd.category,
                "width": sd.width,
                "thickness": sd.thickness,
                "length": sd.length,
                "quantity": sd.quantity,
                "is_coated": sd.is_coated,
                "volume_m3": float(sd.volume_m3 or 0),
                "total_price": float(sd.total_price or 0),
            } for sd in (i.sub_details or [])]
        } for i in order.items],
        "payments": [{
            "id": p.id,
            "order_id": p.order_id,
            "amount": float(p.amount),
            "payment_type": p.payment_type.value,
            "payment_method": p.payment_method.value,
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            "received_by": p.received_by,
            "notes": p.notes
        } for p in order.payments]
    }


@app.put("/api/orders/{order_id}")
def api_update_order(order_id: int, order: schemas.OrderCreate, loy_kg: Optional[float] = None,
                     confirm_shortage: bool = False,
                     db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Buyurtmani tahrirlash — ombor faqat FARQ bo'yicha to'g'rilanadi."""
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.order_of_company(db, order_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    result = crud.update_order_full(db, order_id, order, confirm_shortage=confirm_shortage)
    if not result["success"]:
        # Xomashyo yetishmovchiligi — 409 (create bilan bir xil), frontend
        # "davom etasizmi?" oynasini ko'rsatib, confirm_shortage=true bilan
        # qayta yuborishi mumkin.
        if result.get("type") == "stock_shortage_warning":
            raise HTTPException(status_code=409, detail=result)
        raise HTTPException(status_code=400, detail=result)

    # Loy rejasi o'zgargan bo'lsa
    if loy_kg is not None:
        loy_res = crud.update_order_loy(db, order_id, float(loy_kg))
        if loy_res.get("inventory_log"):
            result["inventory_log"].extend(loy_res["inventory_log"])
        result["loy_changed"] = {
            "old": loy_res.get("old_loy"),
            "new": loy_res.get("new_loy")
        }

    # Ombor ogohlantirishlari
    low_items = crud.get_low_stock_items(db)
    if low_items:
        lines = []
        for item in low_items:
            qty = float(item.stock_quantity)
            min_q = float(item.min_stock)
            emoji = "🔴" if qty <= min_q * 0.5 else "🟡"
            lines.append(f"{emoji} {item.item_name}: {qty:.1f} {item.unit} qoldi (min: {min_q:.0f})")
        ord_obj = crud.get_order(db, order_id, company_id=auth.company_id_of(current_user))
        msg = (f"⚠️ *Ombor ogohlantirishlari!*\n\n*{ord_obj.order_number}* tahrirlangandan keyin:\n\n"
               + "━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
               + "\n━━━━━━━━━━━━━━━━━━━\n\nZudlik bilan buyurtma bering! 🚨\n\n🏗 *PenoDecorPro* — Andijon")
        _send_telegram(msg)

    return result
@app.put("/api/orders/{order_id}/loy")
def api_update_loy(order_id: int, loy_kg: float, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Loy rejasini o'zgartirish."""
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.order_of_company(db, order_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    result = crud.update_order_loy(db, order_id, loy_kg)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


def _send_telegram_to_qoplamachi(text: str):
    """Qoplamachining o'z shaxsiy chatiga xabar yuboradi — QOPLAMACHI_TELEGRAM_CHAT_ID
    Railway env varida sozlanadi (bir nechta bo'lsa, vergul bilan ajratiladi).
    Eski, buzilgan TELEGRAM_COATING_ID'dan farqli — bu yangi, ishlaydigan sozlama
    (2026-09-06, faqat 'necha kg loy tayyorlash kerak' xabari uchun qo'shildi)."""
    # Faza 3 (2-qadam): avval korxonaning o'z sozlamasi, bo'lmasa muhit
    # o'zgaruvchisi. Shu bilan har korxonaning qoplamachisi o'z xabarini
    # o'z botidan oladi.
    raw = ""
    try:
        from database import SessionLocal as _SL
        import tenant_context as _tc
        _d = _SL()
        try:
            _cid = _tc.get_current_company(_d)
            if _cid is not None:
                raw = (crud.get_setting(_d, "telegram_qoplamachi_chat_id", "",
                                        company_id=_cid) or "").strip()
        finally:
            _d.close()
    except Exception:
        raw = ""
    if not raw:
        raw = os.environ.get("QOPLAMACHI_TELEGRAM_CHAT_ID", "").strip()
    if not raw:
        return
    for chat_id in [c.strip() for c in raw.split(",") if c.strip()]:
        _send_telegram_to(chat_id, text)


@app.post("/api/orders/{order_id}/coating-notify")
def api_coating_notify(order_id: int, loy_kg: float, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Rejalashtirilgan loy: xomashyoni ayiradi + qoplamachiga xabar."""
    order = crud.get_order(db, order_id, company_id=auth.company_id_of(current_user))
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

    inventory_log = []

    if loy_kg > 0:
        # Rejani notes ga yozamiz
        services._set_planned_loy(order, loy_kg)
        db.commit()
        db.refresh(order)

        # MUHIM: loy xomashyosi bu yerda ENDI AYIRILMAYDI! Avval bu funksiya
        # loyni ayirardi, lekin keyinchalik `create_order` ham (umumiy qoplama
        # loyi uchun) ayiradigan bo'ldi — natijada loy IKKI MARTA ayirilardi
        # (Railway log bilan aniqlangan: create_order:1052 + coating_notify:1894).
        # Endi bu yerda faqat Telegram xabari yuboriladi, xomashyo esa faqat
        # `create_order`/`update_order` da bir marta ayiriladi.
        if order.status != OrderStatus.DRAFT:
            msg = (
                f"🏗 *PenoDecorPro — Yangi buyurtma*\n\n"
                f"📋 Buyurtma: *{order.order_number}*\n"
                f"👤 Mijoz: {order.project.client_name if order.project else '—'}\n"
                f"🧱 Loy tayyorlang: *{int(loy_kg)} kg*\n\n"
                f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            _send_telegram(msg)
            _send_telegram_to_qoplamachi(msg)

    # "Loy sotish" turidagi detallar — MUHIM: bu yerda ENDI ayirilmaydi!
    # Sababi: create_order() (buyurtma yaratilganda) — bu ishni ALLAQACHON
    # qiladi. Agar bu yerda YANA qilsak — xomashyo IKKI-UCH MARTA ortiqcha
    # ayirilib ketadi (aynan shu xato topilgan va tuzatilgan edi).

    return {"status": "ok", "inventory_log": inventory_log}


@app.post("/api/orders/{order_id}/ready")
def api_mark_order_ready(order_id: int, loy_kg: Optional[float] = None,
                          db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    # ⚠ 2026-09-21, IDOR testi bilan topildi (tools/test_idor.py):
    # M2 qo'riqchisi TUSHIB QOLGAN edi. Pastdagi `crud.get_order(...)`
    # korxona bo'yicha cheklangan, LEKIN u faqat Telegram xabari uchun —
    # zarar undan OLDIN, `services.complete_order` da yetkaziladi.
    # O'lchangan: B korxona admini A ning buyurtmasini `in_progress` dan
    # `ready` ga o'tkazdi va A da avtomatik yetkazish yozuvi yaratildi
    # (xomashyo hisobi va usta KPI si ham shu zanjirda).
    if not auth.order_of_company(db, order_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    result = services.complete_order(db, order_id, loy_kg)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    order = crud.get_order(db, order_id, company_id=auth.company_id_of(current_user))
    if order:
        if loy_kg and loy_kg > 0:
            msg = (
                f"🏗 *PenoDecorPro — Buyurtma tayyor*\n\n"
                f"📋 Buyurtma: *{order.order_number}*\n"
                f"👤 Mijoz: {order.project.client_name if order.project else '—'}\n"
                f"🧱 Ishlatilgan loy: *{int(loy_kg)} kg*\n\n"
                f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            _send_telegram(msg)
        if order.project and order.project.notes:
            notes = order.project.notes or ''
            tg_id = None
            if 'tg_id=' in notes:
                try:
                    tg_id = notes.split('tg_id=')[1].split(',')[0].strip()
                except Exception as e:
                    try:
                        crud.log_error(db, str(e), endpoint="api_mark_order_ready:tg_id_parse")
                    except Exception:
                        pass
            if tg_id and tg_id.lstrip('-').isdigit():
                # MUHIM (2026-09): agar mijoz mahsulotni QISMAN, bir necha
                # marta (masalan 5 ta yukka bo'lib) ALLAQACHON olib bo'lgan
                # bo'lsa — "Tayyor" bosilganda "kelib olishingiz mumkin!"
                # degan xabar noto'g'ri chiqadi (chunki hech narsa qolmagan,
                # olib bo'lingan). Shuning uchun xabar matni buyurtmaning
                # HAQIQIY yetkazish holatiga qarab tanlanadi.
                if order.is_fully_delivered:
                    client_msg = (
                        f"✅ *Buyurtmangiz to'liq yakunlandi!*\n\n"
                        f"📋 Buyurtma: *{order.order_number}*\n"
                        f"👤 Mijoz: {order.project.client_name}\n"
                        f"🏗 PenoDecorPro — Andijon\n\n"
                        f"Barcha mahsulot to'liq topshirildi. Xarid uchun rahmat!\n"
                        f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                    )
                else:
                    client_msg = (
                        f"✅ *Buyurtmangiz tayyor!*\n\n"
                        f"📋 Buyurtma: *{order.order_number}*\n"
                        f"👤 Mijoz: {order.project.client_name}\n"
                        f"🏗 PenoDecorPro — Andijon\n\n"
                        f"Buyurtmangizni olishingiz mumkin!\n"
                        f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                    )
                _send_telegram_to(tg_id, client_msg)

    # Agar "Tayyor" belgilashda BUTUN mahsulot avtomatik bir yo'la
    # topshirilgan (yetkazilgan) deb belgilangan bo'lsa — o'sha yetkazish
    # uchun ham, xuddi qo'lda "Saqlash va nakladnoy olish" bosilgandagidek,
    # Yuk xati PDF'ini mijozga (agar tg_id bo'lsa) yuboramiz.
    auto_delivery = result.get("auto_delivery")
    if isinstance(auto_delivery, dict) and auto_delivery.get("delivery_id"):
        _send_delivery_pdf_to_customer(db, auto_delivery["delivery_id"])
    return result


@app.post("/api/orders/mark-all-ready")
def api_mark_all_ready(loy_kg: Optional[float] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    from models import Order, OrderStatus
    # M2: OMMAVIY amal — FAQAT joriy korxonaning buyurtmalari.
    # Filtrsiz bo'lsa, bitta tugma bosish BARCHA korxonalarning
    # buyurtmalarini "tayyor" qilib, ularning omboriga yozardi.
    pending = db.query(Order).filter(
        Order.company_id == auth.company_id_of(current_user),
        Order.status != OrderStatus.READY,
        Order.is_deleted.isnot(True)).all()
    processed = 0
    failed = []
    total_inventory_changes = []
    loy_per_order = (loy_kg / len(pending)) if (loy_kg and len(pending) > 0) else None
    for order in pending:
        result = services.complete_order(db, order.id, loy_per_order)
        if result["success"]:
            processed += 1
            if result.get("inventory_changes"):
                total_inventory_changes.extend(result["inventory_changes"])
        else:
            reason = result.get("message", "")
            if result.get("shortages"):
                reason += " — " + ", ".join(result["shortages"][:3])
            failed.append({"order_id": order.id, "reason": reason})
    return {"processed": processed, "total_pending": len(pending), "failed": failed, "total_inventory_changes": total_inventory_changes}


@app.delete("/api/orders/{order_id}")
def api_delete_order(order_id: int, actual_loy_kg: Optional[float] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Buyurtmani o'chirish — xomashyo omborga qaytariladi.
    actual_loy_kg — agar berilsa, rejalashtirilgan loy bilan solishtirilib,
    ortgan qismi omborga qaytariladi (xuddi buyurtma yakunlanganidagi kabi)."""
    order = crud.get_order(db, order_id, company_id=auth.company_id_of(current_user))
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

    log = []
    order_num = order.order_number

    # ── Xomashyo qaytadimi? ──
    # Qoralama            → ombordan hech narsa yechilmagan, qaytarish shart emas
    # Hech narsa topshirilmagan → hammasi qaytadi
    # QISMAN topshirilgan  → FAQAT qolgan (topshirilmagan) qismi qaytadi
    # To'liq YETKAZILGAN   → hech narsa qaytmaydi (hammasi mijozda)
    has_delivery = bool(order.deliveries)
    is_fully_delivered = order.status == OrderStatus.DELIVERED or order.is_fully_delivered
    can_return = order.status != OrderStatus.DRAFT and not is_fully_delivered

    if can_return and not order.stock_returned:
        if has_delivery:
            # Qisman topshirilgan — faqat qolgan qismi qaytadi
            log.extend(services.return_inventory_for_order_partial(db, order))
        else:
            # Hech narsa topshirilmagan — hammasi qaytadi
            log.extend(services.return_inventory_for_order(db, order))

        # Tayyor mahsulotlar qaytadi — hech narsa topshirilmagan bo'lsa TO'LIQ,
        # QISMAN topshirilgan bo'lsa faqat QOLGAN (topshirilmagan) qismi
        # (_return_finished_for_order o'zi item.remaining_qty orqali farqni
        # to'g'ri hisoblaydi — topshirilgan qism mijozda qoladi).
        log.extend(crud._return_finished_for_order(db, order))

        # Loy ingredientlari — reja/haqiqiy solishtirib qaytariladi.
        # actual_loy_kg berilgan bo'lsa (hodim "qancha ishlatildi" deb yozgan) —
        # ortgan qismi aniq qaytadi. Berilmagan bo'lsa:
        #   - hech narsa topshirilmagan bo'lsa — to'liq rejalashtirilgan miqdor qaytadi;
        #   - QISMAN topshirilgan bo'lsa — buyurtmaning yetkazilgan foiziga qarab,
        #     QOLGAN (topshirilmagan) qism uchun mo'ljallangan loy proporsional qaytadi
        #     (aniq "qancha ishlatilgani" ma'lum bo'lmagani uchun taxminiy hisob).
        planned_loy = services._get_planned_loy(order)

        if actual_loy_kg is not None:
            diff = planned_loy - float(actual_loy_kg)
            if diff > 0.01:
                log.extend(services.return_loy_ingredients(db, order, diff))
            elif diff < -0.01:
                log.extend(services.deduct_loy_ingredients(db, order, abs(diff)))
        elif planned_loy > 0:
            if not has_delivery:
                log.extend(services.return_loy_ingredients(db, order, planned_loy))
            else:
                # MUHIM (2026-09 chuqur audit — ikkinchi bosqich): order-wide
                # delivery_percent EMAS — faqat haqiqatda loy sarflaydigan
                # detallar bo'yicha hisoblangan ulush ishlatiladi (qarang:
                # services.loy_relevant_remaining_fraction izohi).
                remaining_fraction = services.loy_relevant_remaining_fraction(order)
                proportional_loy = planned_loy * remaining_fraction
                if proportional_loy > 0.01:
                    log.extend(services.return_loy_ingredients(db, order, proportional_loy))

        # "Loy sotish" detallari — har biri o'z retseptiga ko'ra, ALOHIDA
        # (item.remaining_qty asosida) qaytariladi.
        # MUHIM (2026-09 chuqur audit — ikkinchi bosqich): avval bu butun
        # buyurtmaning order-wide has_delivery'iga qarab HAMMASI YOKI HECH
        # NARSA tarzida ishlardi — agar buyurtmadagi BOSHQA bir detal
        # (masalan profil) qisman topshirilgan bo'lsa, shu "loy sotish"
        # detali o'zi UMUMAN topshirilmagan bo'lsa ham, uning loyi
        # UMUMAN qaytmas edi. Endi har bir "loy sotish" detali o'zining
        # remaining_qty'i (topshirilmagan qismi) bo'yicha, mustaqil
        # qaytariladi — boshqa detallarning yetkazilish holatidan qat'i
        # nazar.
        for item in order.items:
            if (item.category or '').lower() == 'loy_sotish' and item.recipe_id:
                remaining = item.remaining_qty
                if remaining > 0.001:
                    log.extend(services.return_loy_ingredients(db, order, float(remaining), recipe_id=item.recipe_id))

        # MUHIM: "qaytarildi" deb BELGILAYMIZ — shu buyurtma keyinchalik
        # tiklanib, YANA o'chirilsa ham, ombor IKKINCHI MARTA qaytarilmasin.
        order.stock_returned = True

    # Nima uchun (to'liq) qaytmagani — foydalanuvchiga aytamiz
    reason = None
    if order.status == OrderStatus.DRAFT:
        reason = "Qoralama — ombordan hech narsa yechilmagan edi"
    elif is_fully_delivered:
        reason = "Buyurtma TO'LIQ YETKAZILGAN — mahsulot mijozda, xomashyo qaytmaydi"
    elif has_delivery:
        pct = order.delivery_percent
        reason = f"Qisman topshirilgan ({pct:.0f}%) — faqat QOLGAN ({100-pct:.0f}%) qismi uchun xomashyo qaytdi"

    # Kelajakda KPI/hisobotlar uchun saqlanishi kerakmi?
    # Har qanday haqiqiy ish izi bo'lsa (yetkazish, tayyor, to'langan) — yumshoq o'chiramiz.
    # MUHIM: "to'lov qilingan" — endi yakka o'zi yumshoq o'chirishga sabab
    # bo'lmaydi. Agar buyurtmaga HECH NARSA topshirilmagan bo'lsa (hali
    # ish boshlanmagan, chin bekor qilish) — buyurtma BUTUNLAY o'chadi,
    # va unga bog'liq TO'LOVLAR HAM avtomatik birga o'chadi (pastda,
    # crud.delete_order ichida) — moliyaviy iz qoldirishning hojati yo'q,
    # chunki hech qanday haqiqiy xizmat ko'rsatilmagan edi.
    should_soft_delete = (
        has_delivery
        or order.status in (OrderStatus.READY, OrderStatus.DELIVERED)
    )

    # MUHIM: yuqorida yaratilgan yangi "ombor harakati" yozuvlari (masalan
    # Loy qaytarilgani) hali bazaga yozilmagan (faqat xotirada) bo'lishi
    # mumkin. Ularni ENDI, delete_order ichidagi "bog'lanishni uzish"
    # so'rovidan OLDIN, bazaga yozib qo'yamiz — aks holda FK xatosi chiqadi.
    db.flush()

    if not crud.delete_order(db, order_id, soft=should_soft_delete, performed_by=(current_user.full_name or current_user.username)):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

    if log:
        print(f"✓ {order_num} o'chirildi. Omborga qaytdi: {log}")
    else:
        print(f"✓ {order_num} o'chirildi. Xomashyo qaytmadi: {reason}")

    return {"status": "ok", "inventory_log": log, "returned": bool(log), "reason": reason,
            "soft_deleted": should_soft_delete}


@app.delete("/api/order-items/{item_id}")
def api_delete_order_item(item_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    if not crud.delete_order_item(db, item_id, company_id=auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Detal topilmadi")
    return {"status": "ok"}


@app.put("/api/order-items/{item_id}")
def api_update_order_item(item_id: int, data: dict, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    updated = crud.update_order_item(db, item_id, data, company_id=auth.company_id_of(current_user))
    if not updated:
        raise HTTPException(status_code=404, detail="Detal topilmadi")
    return {"status": "ok"}


@app.get("/api/dashboard/stats")
def api_dashboard_stats(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return services.get_dashboard_stats(db, company_id=auth.company_id_of(current_user))


@app.get("/api/dashboard/today")
def api_dashboard_today(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return services.get_today_stats(db, company_id=auth.company_id_of(current_user))


@app.get("/api/dashboard/charts")
def api_dashboard_charts(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return services.get_chart_data(db, company_id=auth.company_id_of(current_user))


@app.get("/api/warnings/low-stock")
def api_low_stock(db: Session = Depends(get_db), current_user=Depends(auth.require_login)):
    return {"warnings": services.get_low_stock_warnings(db)}


@app.get("/api/notifications")
def api_notifications(db: Session = Depends(get_db), current_user=Depends(auth.require_login)):
    return services.get_notifications(db, company_id=auth.company_id_of(current_user))


@app.get("/api/dashboard/today-tasks")
def api_today_tasks(db: Session = Depends(get_db), current_user=Depends(auth.require_login)):
    return services.get_today_tasks(db)


@app.get("/api/dashboard/production-periods")
def api_production_periods(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return services.get_production_period_stats(db, company_id=auth.company_id_of(current_user))


@app.get("/api/inventory/movements")
def api_inventory_movements(item_id: Optional[int] = None, movement_type: Optional[str] = None,
                             order_id: Optional[int] = None, date_from: Optional[str] = None,
                             date_to: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db),
                             current_user=Depends(auth.inventory_view)):
    """Ombor harakatlari jurnali — kirim va chiqimlar tarixi (faqat o'qish).

    M3: faqat joriy korxonaning harakatlari.
    date_from/date_to — 'YYYY-MM-DD' ko'rinishida, ma'lum kunlar oralig'ini
    ko'rish uchun (masalan, hodim ishga kelmagan kunlarda qancha xomashyo
    ishlatilganini tekshirish uchun)."""
    from models import InventoryMovement
    from datetime import datetime, timedelta
    from database import TASHKENT_OFFSET
    q = db.query(InventoryMovement).filter(
        InventoryMovement.company_id == auth.company_id_of(current_user))
    if item_id:
        q = q.filter(InventoryMovement.inventory_id == item_id)
    if movement_type in ("in", "out"):
        q = q.filter(InventoryMovement.movement_type == movement_type)
    if order_id:
        q = q.filter(InventoryMovement.order_id == order_id)
    if date_from:
        try:
            # 2026-09-17 (audit topilmasi): foydalanuvchi tanlagan sana —
            # Toshkent taqvimi bo'yicha, bazadagi vaqt esa UTC — shuning
            # uchun solishtirishdan oldin -5 soat siljitiladi.
            q = q.filter(InventoryMovement.created_at >= datetime.strptime(date_from, "%Y-%m-%d") - TASHKENT_OFFSET)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d") - TASHKENT_OFFSET + timedelta(days=1)
            q = q.filter(InventoryMovement.created_at < dt)
        except ValueError:
            pass
    rows = q.order_by(InventoryMovement.created_at.desc()).limit(limit).all()
    return [schemas.InventoryMovementRead.model_validate(r) for r in rows]


@app.get("/api/projects/{project_id}/detail-stats")
def api_project_detail_stats(project_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_manager_accountant)):
    """Loyiha detali uchun qo'shimcha ko'rsatkichlar — faqat o'qish, mavjud
    calculate_order_profit() dan foydalanadi, hech narsani o'zgartirmaydi."""
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.project_of_company(db, project_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    import services
    from models import Order, OrderStatus

    orders = db.query(Order).filter(Order.project_id == project_id, Order.is_deleted.isnot(True)).all()
    status_counts = {}
    total_profit = 0.0
    for o in orders:
        st = o.status.value
        status_counts[st] = status_counts.get(st, 0) + 1
        if o.status == OrderStatus.READY:
            try:
                total_profit += float(services.calculate_order_profit(
                    db, o.id, company_id=auth.company_id_of(current_user)).get("foyda", 0))
            except Exception as e:
                try:
                    crud.log_error(db, str(e), endpoint=f"project_detail:calculate_order_profit order#{o.id}")
                except Exception:
                    pass

    ready_count = status_counts.get("ready", 0) + status_counts.get("delivered", 0)
    total_count = len(orders)
    progress_pct = round((ready_count / total_count) * 100) if total_count else 0

    return {
        "status_counts": status_counts,
        "total_profit": round(total_profit),
        "progress_pct": progress_pct,
        "total_orders": total_count,
    }


@app.get("/debts", response_class=HTMLResponse)
async def debts_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    """Qarzdorlar sahifasi — ikkita yo'nalish:
    1) Bizga qarzdorlar — mijozlar (Order.debt_amount asosida, ESKI
       Project.total_budget emas — bu qadimgi, buyurtma to'lovlariga
       umuman bog'lanmagan maydon edi, shuning uchun almashtirildi).
    2) Biz qarzdormiz — yetkazib beruvchilar (mavjud, sinalgan
       get_suppliers_with_debt() funksiyasidan)."""
    from models import Order, OrderStatus

    # M2: qarzdorlar ro'yxati FAQAT joriy korxonaning buyurtmalaridan.
    orders = db.query(Order).filter(
        Order.company_id == auth.company_id_of(current_user),
        Order.is_deleted.isnot(True),
        Order.status != OrderStatus.DRAFT
    ).all()
    order_debts = [o for o in orders if float(o.debt_amount or 0) > 0.5]
    order_debts.sort(key=lambda o: float(o.debt_amount or 0), reverse=True)
    total_customer_debt = sum(float(o.debt_amount or 0) for o in order_debts)

    suppliers_all = crud.get_suppliers_with_debt(db, company_id=auth.company_id_of(current_user))
    supplier_debts = [s for s in suppliers_all if s['debt'] > 0]
    supplier_debts.sort(key=lambda s: s['debt'], reverse=True)
    total_supplier_debt = sum(s['debt'] for s in supplier_debts)

    from datetime import datetime as _dt
    now = _dt.utcnow()
    company_obligations = services.get_company_obligations_status(db, now.year, now.month, company_id=auth.company_id_of(current_user))
    recurring_targets = services.get_recurring_obligations(db, company_id=auth.company_id_of(current_user))

    return templates.TemplateResponse(request, "debts.html", {
        "order_debts": order_debts,
        "supplier_debts": supplier_debts,
        "total_customer_debt": total_customer_debt,
        "total_supplier_debt": total_supplier_debt,
        "company_obligations": company_obligations,
        "recurring_targets": recurring_targets,
        "cur_year": now.year, "cur_month": now.month,
        "current_user": current_user, "active_page": "debts"
    })


@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return templates.TemplateResponse(request, "reports.html", {"current_user": current_user, "active_page": "reports"})


@app.get("/api/reports/top-products")
def api_reports_top_products(days: int = 90, limit: int = 15, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return services.get_top_products_report(
        db, days=days, limit=limit, company_id=auth.company_id_of(current_user))


@app.get("/api/dashboard/top-finished-products")
def api_dashboard_top_finished_products(days: int = 30, limit: int = 5, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    """Dashboard uchun — faqat Tayyor mahsulotlardan sotilgan tovarlar (qaytganlari ayrilgan)."""
    return services.get_top_finished_products_sold(db, days=days, limit=limit)


@app.get("/api/reports/top-materials")
def api_reports_top_materials(days: int = 90, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return services.get_top_materials_report(db, days=days, company_id=auth.company_id_of(current_user))


@app.get("/api/reports/top-customers")
def api_reports_top_customers(days: int = 90, limit: int = 10, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return services.get_top_customers_report(db, days=days, limit=limit, company_id=auth.company_id_of(current_user))


@app.get("/api/reports/top-suppliers")
def api_reports_top_suppliers(days: int = 90, limit: int = 10, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return services.get_top_suppliers_report(db, days=days, limit=limit, company_id=auth.company_id_of(current_user))


@app.get("/api/reports/comparison")
def api_reports_comparison(year: int, month: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return services.get_monthly_comparison(db, year, month)


@app.get("/api/reports/forecast")
def api_reports_forecast(year: int, month: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return services.get_simple_forecast(db, year, month)


@app.get("/api/reports/alerts")
def api_reports_alerts(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return services.get_business_alerts(db, company_id=auth.company_id_of(current_user))


@app.get("/api/reports/brak-materials")
def api_reports_brak_materials(start_date: Optional[str] = None, end_date: Optional[str] = None,
                                 db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    """Brak sabab sarflangan xomashyo — nomi, miqdori, tan narxi bo'yicha qiymati."""
    from datetime import datetime as dt
    from database import TASHKENT_OFFSET
    sd = (dt.strptime(start_date, "%Y-%m-%d") - TASHKENT_OFFSET) if start_date else None
    ed = (dt.strptime(end_date, "%Y-%m-%d") - TASHKENT_OFFSET + timedelta(days=1)) if end_date else None
    return crud.get_brak_material_summary(db, start_date=sd, end_date=ed, company_id=auth.company_id_of(current_user))


@app.get("/api/reports/business-health")
def api_reports_business_health(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return services.get_business_health(db, company_id=auth.company_id_of(current_user))


@app.get("/api/obligations/recurring")
def api_get_recurring_obligations(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return services.get_recurring_obligations(db, company_id=auth.company_id_of(current_user))


@app.post("/api/obligations/recurring")
def api_set_recurring_obligation(category: str, label: str, monthly_target: float,
                                   icon: str = "📦", due_day: int = 5,
                                   db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return services.set_recurring_obligation(db, category, label, monthly_target, icon=icon, due_day=due_day, company_id=auth.company_id_of(current_user))


@app.delete("/api/obligations/recurring/{obligation_id}")
def api_delete_recurring_obligation(obligation_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    if not services.delete_recurring_obligation(db, obligation_id, company_id=auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


@app.get("/api/obligations/status")
def api_obligations_status(year: int, month: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return services.get_company_obligations_status(db, year, month, company_id=auth.company_id_of(current_user))


@app.get("/api/obligations/timeline")
def api_obligations_timeline(category: str, year: int, month: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return services.get_obligation_timeline(db, category, year, month, company_id=auth.company_id_of(current_user))


@app.get("/api/obligations/employee/{employee_id}/timeline")
def api_employee_obligation_timeline(employee_id: int, year: int, month: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    # M5: xodim FAQAT joriy korxonadan (aks holda 404).
    if not auth.employee_of_company(db, employee_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    return services.get_employee_payment_timeline(db, employee_id, year, month)


@app.post("/api/obligations/employee/{employee_id}/close")
def api_close_employee_debt(employee_id: int, year: int, month: int, amount: float,
                              db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    # M5: xodim FAQAT joriy korxonadan (aks holda 404).
    if not auth.employee_of_company(db, employee_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    who = current_user.full_name or current_user.username
    return services.close_employee_debt(db, employee_id, year, month, amount, paid_by=who)


@app.get("/api/finance/cash-balance")
def api_get_cash_balance(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    """Kassa balansi — kompaniyada hozir haqiqatda qancha naqd pul bor."""
    return services.get_cash_balance(db, company_id=auth.company_id_of(current_user))


@app.get("/api/finance/cash-transactions")
def api_get_cash_transactions(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    """Kassaga qo'lda qilingan yozuvlar tarixi."""
    rows = crud.get_cash_transactions(db, company_id=auth.company_id_of(current_user))
    return [{
        "id": r.id, "category": r.category, "amount": float(r.amount),
        "notes": r.notes, "performed_by": r.performed_by,
        "created_at": r.created_at.isoformat() if r.created_at else None
    } for r in rows]


@app.delete("/api/finance/cash-transactions/{tx_id}")
def api_delete_cash_transaction(tx_id: int, db: Session = Depends(get_db),
                                current_user=Depends(auth.admin_only)):
    """Kassaga qo'lda qo'shilgan yozuvni o'chiradi — faqat Admin.
    Yozuv FAQAT joriy korxonadan topiladi (aks holda 404)."""
    _cid = auth.company_id_of(current_user)
    if not auth.cash_transaction_of_company(db, tx_id, _cid):
        raise HTTPException(status_code=404, detail="Kassa yozuvi topilmadi")
    if not crud.delete_cash_transaction(db, tx_id, company_id=_cid):
        raise HTTPException(status_code=404, detail="Kassa yozuvi topilmadi")
    return {"status": "ok"}


@app.post("/api/finance/cash-transaction")
def api_record_cash_transaction(category: str = Form(...), amount: float = Form(...),
                                 notes: str = Form(None), db: Session = Depends(get_db),
                                 current_user=Depends(auth.admin_only)):
    """Kassaga qo'lda yozuv qo'shadi — faqat Admin.
    category: 'boshlangich' (musbat) / 'usta_kpi' (manfiy) / 'ehson' (manfiy)."""
    if category not in ("boshlangich", "usta_kpi", "ehson"):
        raise HTTPException(status_code=400, detail="Noto'g'ri kategoriya")
    who = current_user.full_name or current_user.username
    tx = crud.record_cash_transaction(db, category, amount, notes=notes, performed_by=who, company_id=auth.company_id_of(current_user))
    balance = services.get_cash_balance(db, company_id=auth.company_id_of(current_user))
    return {"status": "ok", "transaction_id": tx.id, "new_balance": balance["balance"]}


@app.get("/finance", response_class=HTMLResponse)
async def finance_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return templates.TemplateResponse(request, "finance.html", {"current_user": current_user, "active_page": "finance"})


@app.get("/kunlik-xarajat", response_class=HTMLResponse)
async def kunlik_xarajat_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_manager_accountant)):
    """Manager (Hodim) uchun — daromad/foyda/qarzlarni KO'RSATMASDAN, faqat
    kunlik xarajat (tushlik, kutilmagan va h.k.) qo'shish uchun, alohida,
    kichik sahifa (2026-09)."""
    return templates.TemplateResponse(request, "kunlik_xarajat.html", {"current_user": current_user, "active_page": "kunlik_xarajat"})


@app.get("/api/finance/report")
def api_finance_report(year: int, month: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    # M4: hisobotning tayyor mahsulot qismi joriy korxona bilan cheklanadi
    # (qolgan qismlari M6 da ko'riladi).
    return services.get_monthly_report(db, year, month,
                                       company_id=auth.company_id_of(current_user))


@app.get("/api/finance/debt-summary")
def api_finance_debt_summary(year: int, month: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    """Mijoz, yetkazuvchi, hodim va doimiy majburiyatlar qarzini — bitta
    joyga jamlab beradi ("Moliya" sahifasidagi yangi bo'lim uchun)."""
    return services.get_full_debt_summary(db, year, month, company_id=auth.company_id_of(current_user))


@app.get("/api/finance/split-profit-pdf")
def api_split_profit_pdf(year: int, month: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    """Gips va Penoplast uchun mustaqil sof foyda hisoboti — PDF."""
    from fastapi.responses import Response
    import finance_pdf

    split = services.calculate_split_profit_report(db, year, month, company_id=auth.company_id_of(current_user))
    pdf_bytes = finance_pdf.generate_split_profit_pdf(
        split, year, month, db=db, company_id=auth.company_id_of(current_user))
    filename = f"gips_penoplast_hisobot_{year}_{month:02d}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


@app.get("/api/finance/report-pdf")
def api_finance_report_pdf(year: int, month: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    """Bir oylik to'liq moliyaviy hisobot — PDF (yuklab olish uchun)."""
    from fastapi.responses import Response
    import finance_pdf
    from datetime import datetime as _dt

    report = services.get_monthly_report(db, year, month,
                                        company_id=auth.company_id_of(current_user))

    _start = _dt(year, month, 1)
    _end = _dt(year + 1, 1, 1) if month == 12 else _dt(year, month + 1, 1)
    expense_transactions = crud.get_expense_transactions(db, year=year, month=month, company_id=auth.company_id_of(current_user))

    brak_summary = crud.get_brak_material_summary(db, start_date=_start, end_date=_end, company_id=auth.company_id_of(current_user))
    brak_by_material = brak_summary.get("by_material", [])
    debt_summary = services.get_full_debt_summary(db, year, month, company_id=auth.company_id_of(current_user))

    pdf_bytes = finance_pdf.generate_finance_report_pdf(
        report, expense_transactions, brak_by_material, year, month, debt_summary,
        db=db, company_id=auth.company_id_of(current_user)
    )
    filename = f"moliyaviy_hisobot_{year}_{month:02d}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


@app.get("/api/finance/daily")
def api_finance_daily(target_date: Optional[str] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    """Bitta kun uchun moliyaviy ko'rinish (savdo/foyda/tan narx + xarajatlar).
    target_date berilmasa — bugungi kun olinadi. Format: YYYY-MM-DD"""
    from datetime import date as date_cls
    if target_date:
        d = date_cls.fromisoformat(target_date)
    else:
        d = date_cls.today()
    return services.get_daily_finance_summary(db, d, company_id=auth.company_id_of(current_user))


@app.get("/api/finance/history")
def api_finance_history(months: int = 12, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    return services.get_finance_history(db, months, company_id=auth.company_id_of(current_user))


@app.post("/api/finance/transactions")
def api_create_expense_transaction(data: schemas.ExpenseTransactionCreate, db: Session = Depends(get_db),
                                    current_user=Depends(auth.admin_manager_accountant)):
    tx = crud.create_expense_transaction(db, data.model_dump(), performed_by=current_user.full_name or current_user.username, source="manual", company_id=auth.company_id_of(current_user))
    return schemas.ExpenseTransactionRead.model_validate(tx)


@app.get("/api/finance/transactions")
def api_list_expense_transactions(year: Optional[int] = None, month: Optional[int] = None,
                                   day: Optional[int] = None, category: Optional[str] = None,
                                   db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    rows = crud.get_expense_transactions(db, year=year, month=month, day=day, category=category, company_id=auth.company_id_of(current_user))
    return [schemas.ExpenseTransactionRead.model_validate(r) for r in rows]


@app.delete("/api/finance/transactions/{tx_id}")
def api_delete_expense_transaction(tx_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    ok = crud.delete_expense_transaction(db, tx_id, company_id=auth.company_id_of(current_user))
    if not ok:
        raise HTTPException(status_code=404, detail="Tranzaksiya topilmadi")
    return {"status": "ok"}


@app.put("/api/finance/transactions/{tx_id}")
def api_update_expense_transaction(tx_id: int, data: schemas.ExpenseTransactionCreate, db: Session = Depends(get_db),
                                    current_user=Depends(auth.admin_manager_accountant)):
    """2026-09-16: foydalanuvchi so'rovi bo'yicha qo'shildi — xato kiritilgan
    xarajat summasini o'chirib-qayta yozish o'rniga, to'g'ridan-to'g'ri
    tahrirlash imkonini beradi (masalan "125" o'rniga "125 000" bo'lishi
    kerak bo'lgan holatlar uchun)."""
    tx = crud.update_expense_transaction(db, tx_id, data.model_dump(), company_id=auth.company_id_of(current_user))
    if not tx:
        raise HTTPException(status_code=404, detail="Tranzaksiya topilmadi")
    return schemas.ExpenseTransactionRead.model_validate(tx)


@app.post("/api/finance/expense")
def api_save_expense(year: int, month: int, data: dict, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    services.save_monthly_expense(db, year, month, data, performed_by=current_user.full_name or current_user.username, company_id=auth.company_id_of(current_user))
    return {"status": "ok"}


@app.get("/api/orders/{order_id}/profit")
def api_order_profit(order_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    # M2: buyurtma FAQAT joriy korxonadan (aks holda 404).
    if not crud.get_order(db, order_id, company_id=auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    return services.calculate_order_profit(db, order_id, company_id=auth.company_id_of(current_user))


@app.get("/api/orders/{order_id}/pdf")
def api_order_pdf(order_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    from fastapi.responses import Response
    import pdf_service
    import traceback
    order = crud.get_order(db, order_id, company_id=auth.company_id_of(current_user))
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    try:
        pdf_bytes = pdf_service.generate_nakladnoy(order, db)
    except Exception as e:
        err = traceback.format_exc()
        print("PDF XATO:\n", err)
        raise HTTPException(status_code=500, detail=f"PDF xato: {str(e)}")
    filename = f"nakladnoy_{order.order_number}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/health")
async def health():
    return {"status": "ok", "message": "PenoDecorPro ERP ishlamoqda!"}


@app.get("/returns", response_class=HTMLResponse)
async def returns_page(request: Request, show_all: bool = False, db: Session = Depends(get_db), current_user=Depends(auth.manager_or_warehouse)):
    returns = crud.get_return_items_for_main_page(db, days=90, show_all=show_all, company_id=auth.company_id_of(current_user))
    orders  = crud.get_orders_for_main_page(db, days=90, show_all=True,
                                            company_id=auth.company_id_of(current_user))
    projects = crud.get_projects(db, company_id=auth.company_id_of(current_user))
    return templates.TemplateResponse(request, "returns.html", {
        "returns": returns, "orders": orders, "projects": projects,
        "current_user": current_user, "show_all": show_all
    })


@app.get("/api/projects/{project_id}/items")
def api_get_project_items(project_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Loyihadagi barcha buyurtmalar detallari — brak yozish uchun (narxsiz)."""
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.project_of_company(db, project_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    from models import Order, OrderStatus

    orders = db.query(Order).filter(
        Order.project_id == project_id,
        Order.status.notin_([OrderStatus.DRAFT, OrderStatus.CANCELLED]),
        Order.is_deleted.isnot(True)
    ).order_by(Order.created_at.desc()).all()

    items = []
    for o in orders:
        for i in o.items:
            items.append({
                "order_id": o.id,
                "order_number": o.order_number,
                "item_id": i.id,
                "name": i.name,
                "category": i.category,
                "is_coated": i.is_coated,
                "order_qty_normalized": i.order_qty_normalized,
                "delivery_unit": i.delivery_unit
            })
    return {"items": items}


@app.post("/api/returns")
def api_create_return(data: schemas.ReturnItemCreate, db: Session = Depends(get_db), current_user=Depends(auth.manager_or_warehouse)):
    return crud.create_return_item(db, data, company_id=auth.company_id_of(current_user))


@app.get("/api/returns")
def api_get_returns(order_id: Optional[int] = None, db: Session = Depends(get_db), current_user=Depends(auth.manager_or_warehouse)):
    return crud.get_return_items(db, order_id=order_id, company_id=auth.company_id_of(current_user))


@app.get("/api/returns/stats")
def api_return_stats(db: Session = Depends(get_db), current_user=Depends(auth.manager_or_warehouse)):
    return crud.get_return_stats(db, company_id=auth.company_id_of(current_user))


@app.post("/api/returns/{return_id}/refund")
def api_mark_refunded(return_id: int, db: Session = Depends(get_db), current_user=Depends(auth.manager_or_warehouse)):
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.return_of_company(db, return_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Qaytarish topilmadi")
    who = current_user.full_name or current_user.username
    item = crud.mark_refunded(db, return_id, refunded_by=who)
    if not item:
        raise HTTPException(status_code=404, detail="Qaytarish topilmadi")
    return {"status": "ok", "is_refunded": item.is_refunded}


@app.delete("/api/returns/{return_id}")
def api_delete_return(return_id: int, db: Session = Depends(get_db), current_user=Depends(auth.manager_or_warehouse)):
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.return_of_company(db, return_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Qaytarish topilmadi")
    if not crud.delete_return_item(db, return_id):
        raise HTTPException(status_code=404, detail="Qaytarish topilmadi")
    return {"status": "ok"}


# ============================================================
# PAYMENTS — To'lovlar API
# ============================================================

@app.post("/api/payments")
def api_create_payment(data: schemas.PaymentCreate, write_off_remainder: bool = False, db: Session = Depends(get_db), current_user=Depends(auth.order_payments)):
    """Yangi to'lov qo'shish.
    write_off_remainder=true bo'lsa — to'lovdan keyin qolgan (kichik) qarz
    CHEGIRMA sifatida yozib yuboriladi (jami summadan ham ayiriladi —
    shuning uchun FOYDA hisobotida ham to'g'ri, kamroq ko'rsatiladi)."""
    if not data.received_by:
        data.received_by = current_user.full_name or current_user.username
    try:
        payment = crud.create_payment(db, data, company_id=auth.company_id_of(current_user))
    except crud.OverpaymentWarning as w:
        raise HTTPException(status_code=409, detail={
            "type": "overpayment_warning",
            "message": f"Kiritilgan summa ({w.amount:,.0f} so'm) qarzdan ({w.debt:,.0f} so'm) {w.excess:,.0f} so'mga ko'p. Shunday ham davom etasizmi?",
            "amount": w.amount, "debt": w.debt, "excess": w.excess
        })
    except ValueError as e:
        status = 404 if "topilmadi" in str(e) else 400
        raise HTTPException(status_code=status, detail=str(e))

    order = crud.get_order(db, data.order_id, company_id=auth.company_id_of(current_user))

    write_off_info = None
    if write_off_remainder and order:
        remaining = order.debt_amount
        if remaining > 0.5:
            # MUHIM: faqat "Kelishilgan"(agreed_amount)ni kamaytiramiz.
            # "Jami summa"(total_amount)ga TEGMAYMIZ — shunda u har doim
            # buyurtmaning asl (chegirmasiz) qiymatini ko'rsatib turadi,
            # "Chegirma" esa (Jami - Kelishilgan) o'zi avtomatik kattalashadi —
            # boshidagi chegirma bilan bu "kechirilgan" summa TABIIY qo'shilib boradi.
            order.agreed_amount = float(order.agreed_amount or order.total_amount or 0) - remaining
            import re as _re
            base_notes = _re.sub(r'\s*\[WRITEOFF:[\d.]+\]', '', order.notes or '').strip()
            order.notes = (base_notes + f" [WRITEOFF:{remaining:.0f}]").strip()
            crud._update_order_payment_status(db, order)
            db.commit()
            db.refresh(order)
            write_off_info = {
                "amount": round(remaining),
                "message": f"Qolgan {remaining:.0f} so'm chegirmaga qo'shildi (foyda hisobotida ham to'g'ri ayiriladi)"
            }

    return {
        "status": "ok",
        "payment_id": payment.id,
        # Takror yuborilgan so'rov bo'lsa — yangi yozuv YARATILMAGAN,
        # mavjudining o'zi qaytarilgan (crud.create_payment ga qarang)
        "duplicate": bool(getattr(payment, "_is_duplicate_submit", False)),
        "paid_amount": order.paid_amount,
        "debt_amount": order.debt_amount,
        "payment_status": order.payment_status.value,
        "is_archived": order.is_archived,
        "write_off": write_off_info
    }


@app.get("/api/payments")
def api_get_payments(order_id: Optional[int] = None, db: Session = Depends(get_db), current_user=Depends(auth.order_payments)):
    """To'lovlar ro'yxati."""
    payments = crud.get_payments(db, order_id=order_id, company_id=auth.company_id_of(current_user))
    return [{
        "id": p.id,
        "order_id": p.order_id,
        "amount": float(p.amount),
        "payment_type": p.payment_type.value,
        "payment_method": p.payment_method.value,
        "paid_at": p.paid_at.isoformat() if p.paid_at else None,
        "received_by": p.received_by,
        "notes": p.notes
    } for p in payments]


@app.delete("/api/payments/{payment_id}")
def api_delete_payment(payment_id: int, db: Session = Depends(get_db), current_user=Depends(auth.order_payments)):
    """To'lovni o'chirish."""
    who = current_user.full_name or current_user.username
    if not crud.delete_payment(db, payment_id, performed_by=who, company_id=auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="To'lov topilmadi")
    return {"status": "ok"}


@app.put("/api/orders/{order_id}/agreed-amount")
def api_update_agreed_amount(order_id: int, data: schemas.OrderAgreedUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Kelishilgan summani (chegirmadan keyingi narx) yangilash."""
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.order_of_company(db, order_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    order = crud.update_order_agreed_amount(db, order_id, data.agreed_amount)
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    return {
        "status": "ok",
        "total_amount": float(order.total_amount or 0),
        "agreed_amount": float(order.agreed_amount or 0),
        "discount_percent": order.discount_percent,
        "paid_amount": order.paid_amount,
        "debt_amount": order.debt_amount,
        "payment_status": order.payment_status.value
    }


@app.get("/api/penoplasts")
def api_get_penoplasts(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Penoplast (plotnost) turlari ro'yxati."""
    items = services.get_penoplast_list(db)
    default_p = services.get_default_penoplast(db)
    return {
        "items": [{
            "id": p.id,
            "name": p.item_name,
            "stock": float(p.stock_quantity or 0),
            "unit": p.unit,
            "volume_per_unit": float(p.volume_per_unit or 1.0),
            "price_per_unit": float(p.price_per_unit or 0),
            "is_default": bool(p.is_default_penoplast)
        } for p in items],
        "default_id": default_p.id if default_p else None
    }


@app.post("/api/inventory/{item_id}/set-default-penoplast")
def api_set_default_penoplast(item_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_warehouse)):
    """Asosiy plotnost qilib belgilash."""
    # M3: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.inventory_of_company(db, item_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Material topilmadi")
    item = db.query(Inventory).filter(Inventory.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Xomashyo topilmadi")
    if not item.is_penoplast:
        raise HTTPException(status_code=400, detail="Bu penoplast emas")

    db.query(Inventory).filter(Inventory.is_default_penoplast == True).update(
        {"is_default_penoplast": False}
    )
    item.is_default_penoplast = True
    db.commit()
    return {"status": "ok", "default_id": item.id, "name": item.item_name}


@app.post("/api/orders/{order_id}/activate")
def api_activate_draft(order_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Qoralamani jarayonga olish — ombordan xomashyo yechiladi."""
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.order_of_company(db, order_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    result = crud.activate_draft_order(db, order_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


# ============================================================
# FINISHED PRODUCTS — Tayyor mahsulotlar ombori
# ============================================================

@app.get("/finished", response_class=HTMLResponse)
async def finished_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    """Tayyor mahsulotlar sahifasi."""
    # M4 (2026-09-18): SAHIFA ham API kabi tenant bilan cheklanadi —
    # M2 saboqi: server chizadigan sahifa boshqa funksiyalardan o'qiydi.
    _cid = auth.company_id_of(current_user)
    items = crud.get_finished_products(db, company_id=_cid)
    penoplasts = services.get_penoplast_list(db)
    default_p = services.get_default_penoplast(db)
    recipes = crud.get_recipes(db, company_id=_cid)
    stats = crud.get_finished_stats(db, company_id=_cid)
    masters = crud.get_masters(db, only_active=True, company_id=_cid)
    return templates.TemplateResponse(request, "finished.html", {
        "items": items, "penoplasts": penoplasts,
        "default_penoplast_id": default_p.id if default_p else None,
        "recipes": recipes, "stats": stats, "masters": masters,
        "current_user": current_user, "active_page": "finished"
    })


@app.get("/api/system/telegram-debug")
def api_telegram_debug(current_user=Depends(auth.platform_admin_only)):
    """Diagnostika: server qaysi botga ulanganini va oxirgi kimlar
    botga 'Start' bosganini (chat_id'lari bilan) ko'rsatadi."""
    import urllib.request as _ur
    import json as _json_mod

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    result = {"token_configured": bool(token)}
    if not token:
        return result

    try:
        me_url = f"https://api.telegram.org/bot{token}/getMe"
        with _ur.urlopen(me_url, timeout=10) as r:
            me_data = _json_mod.loads(r.read())
        result["bot_info"] = me_data.get("result", {})
    except Exception as e:
        result["bot_info_error"] = str(e)

    try:
        updates_url = f"https://api.telegram.org/bot{token}/getUpdates?limit=10"
        with _ur.urlopen(updates_url, timeout=10) as r:
            upd_data = _json_mod.loads(r.read())
        recent_chats = []
        for u in upd_data.get("result", []):
            msg = u.get("message") or u.get("my_chat_member", {})
            chat = msg.get("chat", {}) if msg else {}
            if chat:
                recent_chats.append({
                    "chat_id": chat.get("id"),
                    "first_name": chat.get("first_name"),
                    "username": chat.get("username"),
                })
        result["recent_chats"] = recent_chats
        result["configured_backup_chat_id"] = os.environ.get("BACKUP_TELEGRAM_CHAT_ID", "(sozlanmagan)")
    except Exception as e:
        result["updates_error"] = str(e)

    return result


@app.post("/api/system/telegram-setup-webhook-security")
def api_telegram_setup_webhook_security(request: Request, current_user=Depends(auth.platform_admin_only)):
    """BIR MARTALIK sozlash: Telegram webhookni, XAVFSIZ IMZO bilan qayta
    ro'yxatdan o'tkazadi. Shundan keyin — soxta (Telegram'dan bo'lmagan)
    so'rovlar avtomatik rad etiladi.

    Yangi, tasodifiy imzo o'zi yaratiladi va qaytariladi — buni albatta
    Railway'dagi TELEGRAM_WEBHOOK_SECRET muhit o'zgaruvchisiga qo'shib,
    saqlab qo'yish kerak (aks holda, server qayta ishga tushganda,
    tizim eski imzoni "unutadi" va tekshiruv o'chib qoladi)."""
    import urllib.request as _ur
    import json as _json_mod
    import secrets as _secrets

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN sozlanmagan")

    # MUHIM: Railway, "proksi" orqali ishlaydi — shuning uchun, dastur
    # ichidan qaralganda, so'rov manzili ba'zan "http://" (s"siz) bo'lib
    # ko'rinishi mumkin, garchi tashqaridan HAMMA VAQT "https://" orqali
    # kirilsa ham. Telegram esa, FAQAT https://ni qabul qiladi — shuning
    # uchun, "http"ni, doim, majburiy ravishda "https"ga almashtiramiz.
    webhook_url = str(request.base_url).rstrip("/") + "/telegram/webhook"
    webhook_url = webhook_url.replace("http://", "https://", 1)
    new_secret = _secrets.token_urlsafe(32)

    try:
        set_url = f"https://api.telegram.org/bot{token}/setWebhook"
        payload = _json_mod.dumps({"url": webhook_url, "secret_token": new_secret}).encode()
        req = _ur.Request(set_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with _ur.urlopen(req, timeout=10) as r:
            tg_response = _json_mod.loads(r.read())
    except _ur.HTTPError as e:
        # MUHIM: Telegram, xato bo'lganda ham, SABABINI JSON ichida
        # qaytaradi — lekin urllib, buni oddiy "HTTP Error 400" qilib
        # yashirib qo'yardi. Endi, javob tanasini o'qib, ANIQ sababni
        # ko'rsatamiz (masalan "noto'g'ri token" yoki "noto'g'ri manzil").
        try:
            err_body = _json_mod.loads(e.read().decode())
            err_detail = err_body.get("description", str(e))
        except Exception:
            err_detail = str(e)
        raise HTTPException(status_code=400, detail=f"Telegram rad etdi: {err_detail}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Telegram bilan bog'lanishda xato: {e}")

    if not tg_response.get("ok"):
        raise HTTPException(status_code=400, detail=f"Telegram rad etdi: {tg_response.get('description')}")

    return {
        "status": "ok",
        "webhook_url": webhook_url,
        "new_secret": new_secret,
        "message": (
            "✅ Webhook xavfsiz imzo bilan qayta ro'yxatdan o'tkazildi. "
            "MUHIM: yuqoridagi 'new_secret' qiymatini nusxalab, Railway'dagi "
            "TELEGRAM_WEBHOOK_SECRET muhit o'zgaruvchisiga joylashtiring va saqlang."
        )
    }


@app.post("/api/system/backup/send-now")
def api_backup_send_now(current_user=Depends(auth.platform_admin_only)):
    """Kunlik avtomatik backup vazifasini HOZIROQ, qo'lda ishga tushiradi
    (23:30 ni kutmasdan, Telegram ulanishini sinab ko'rish uchun)."""
    run_daily_backup()
    return {"status": "ok", "message": "Backup yuborildi (agar BACKUP_TELEGRAM_CHAT_ID sozlangan bo'lsa)"}


@app.get("/api/system/backup")
def api_system_backup(db: Session = Depends(get_db),
                      current_user=Depends(auth.platform_admin_only)):
    """Korxona ma'lumotining to'liq zaxira nusxasi (JSON).

    2026-09-20 — endi FAQAT platforma administratori uchun. Ilgari har
    qanday korxona admini (hisobchi ham admin roliga ega bo'lsa) bitta
    so'rov bilan butun biznesni — mijozlar, narxlar, foyda, maoshlar —
    yuklab olardi. Interfeysdan tugmani olib tashlash yetarli emas edi:
    manzilni to'g'ridan-to'g'ri ochish ham mumkin.

    Kunlik zaxira (barcha korxonalar) avvalgidek rejalashtiruvchi orqali
    platforma egasiga boradi.""" 
    import json
    from fastapi.responses import Response

    # M7: tenant admin FAQAT o'z korxonasining zahira nusxasini oladi.
    backup_data = crud.export_full_backup(db, company_id=auth.company_id_of(current_user))
    filename = f"penodecorpro-backup-{datetime.utcnow().strftime('%Y-%m-%d_%H-%M')}.json"
    content = json.dumps(backup_data, ensure_ascii=False, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.get("/api/platform/companies")
def api_platform_companies(db: Session = Depends(get_db),
                           current_user=Depends(auth.platform_admin_only)):
    """Platformadagi barcha korxonalar ro'yxati (faqat platforma admini)."""
    from production_models import Company as _Co
    from models import User as _U
    import tenant_context as _tc
    # MUHIM (2026-09-19, jonli sinovda aniqlangan): bu PLATFORMA amali —
    # u ataylab BARCHA korxonalarni ko'rishi kerak. Global tenant filtri
    # esa so'rovlarga joriy korxona shartini qo'shadi va boshqa
    # korxonalarning yozuvlarini yashiradi (sinovda B korxona
    # "0 foydalanuvchi" bo'lib ko'rindi). `system_context` shu filtrni
    # SHU sessiyada vaqtincha o'chiradi.
    with _tc.system_context(db):
        rows = db.query(_Co).order_by(_Co.id).all()
        out = []
        for c in rows:
            n_users = db.query(_U).filter(_U.company_id == c.id).count()
            out.append({"id": c.id, "name": c.name, "code": c.code,
                        "users": n_users,
                        "created_at": c.created_at.isoformat() if c.created_at else None})
    return out


@app.post("/api/platform/companies")
def api_platform_create_company(name: str = Form(...), admin_username: str = Form(...),
                                admin_full_name: str = Form(""),
                                db: Session = Depends(get_db),
                                current_user=Depends(auth.platform_admin_only)):
    """Yangi korxona va uning BIRINCHI admin hisobini yaratadi (Faza 5).

    NEGA KERAK: shu paytgacha yangi korxona faqat baza orqali yaratilardi.
    Mijoz qabul qilish takrorlanadigan ish — u interfeysda bo'lishi kerak.

    PAROL: tizim o'zi TASODIFIY parol chiqaradi va uni javobda BIR MARTA
    qaytaradi. Baza faqat hashini saqlaydi, ya'ni keyin uni hech kim
    (siz ham) ko'ra olmaydi. Mijoz kirgach o'z parolini almashtiradi —
    "Foydalanuvchilar" sahifasidan.

    Hammasi bitta tranzaksiyada: hisob yaratilmasa, korxona ham
    yaratilmaydi (yarim holat qolmaydi)."""
    import secrets, string, re as _re_co
    from production_models import Company as _Co
    from models import User as _U, UserRole as _UR

    nom = (name or "").strip()
    login = (admin_username or "").strip()
    if len(nom) < 2:
        raise HTTPException(status_code=400, detail="Korxona nomi juda qisqa")
    if not _re_co.fullmatch(r"[A-Za-z0-9_.-]{3,50}", login):
        raise HTTPException(
            status_code=400,
            detail="Login 3-50 belgi: lotin harflari, raqam, _ . - belgilaridan iborat bo'lsin")
    import tenant_context as _tc
    # Login butun tizim bo'yicha yagona — tekshiruv ham global bo'lishi
    # SHART. Aks holda boshqa korxonada band login "bo'sh" ko'rinadi va
    # yaratish bazada tushunarsiz xato bilan yiqiladi.
    with _tc.system_context(db):
        band = db.query(_U).filter(_U.username == login).first() is not None
    if band:
        raise HTTPException(status_code=400, detail="Bu login band")

    # Korxona kodi — nomdan, band bo'lsa raqam qo'shiladi
    asos = _re_co.sub(r"[^A-Z0-9]+", "-", nom.upper()).strip("-")[:24] or "KORXONA"
    kod, i = asos, 1
    with _tc.system_context(db):
        while db.query(_Co).filter(_Co.code == kod).first():
            i += 1
            kod = f"{asos[:20]}-{i}"

    # Tasodifiy parol — o'qish oson bo'lishi uchun chalkash belgilarsiz
    alifbo = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    parol = "".join(secrets.choice(alifbo) for _ in range(12))

    try:
        korxona = _Co(name=nom, code=kod)
        db.add(korxona)
        db.flush()                      # id kerak
        auth.create_user(db, login, parol, _UR.ADMIN,
                         (admin_full_name or nom).strip(),
                         company_id=korxona.id)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Yaratib bo'lmadi: {e}")

    # Yangi korxonada ixtiyoriy turlar (blok, loy) O'CHIQ —
    # mijoz kerak bo'lsa sozlamalardan yoqadi. Aks holda u birinchi kuni
    # o'zi ishlab chiqarmaydigan turlarni ko'rib chalkashardi.
    try:
        crud.set_setting(db, "enabled_categories", "", company_id=korxona.id)
        _clear_category_cache(korxona.id)
    except Exception:
        pass

    _clear_company_name_cache()
    return {"status": "ok", "company": {"id": korxona.id, "name": nom, "code": kod},
            "admin": {"username": login, "password": parol},
            "eslatma": "Parol FAQAT SHU YERDA ko'rsatiladi — keyin tiklab bo'lmaydi."}


@app.post("/api/platform/companies/{company_id}/reset-admin-password")
def api_platform_reset_admin_password(company_id: int, username: str = Form(""),
                                      db: Session = Depends(get_db),
                                      current_user=Depends(auth.platform_admin_only)):
    """Korxona adminining parolini qayta tiklaydi (Faza 5).

    NEGA KERAK: parol yaratishda BIR MARTA ko'rsatiladi va bazada faqat
    hashi saqlanadi — ya'ni uni hech kim (siz ham) qayta ko'ra olmaydi.
    Mijoz parolni yo'qotsa, uni tiklashning yo'li bo'lishi SHART, aks holda
    korxona butunlay qulflanib qoladi.

    `username` berilmasa — o'sha korxonaning ENG ESKI admin hisobi olinadi.
    Yangi parol javobda BIR MARTA qaytariladi.
    """
    import secrets
    from models import User as _U, UserRole as _UR
    import tenant_context as _tc

    # Platforma amali — global filtr o'chiriladi, aks holda boshqa
    # korxonaning hisobi "topilmadi" bo'lib ko'rinadi.
    with _tc.system_context(db):
        q = db.query(_U).filter(_U.company_id == company_id)
        if (username or "").strip():
            u = q.filter(_U.username == username.strip()).first()
        else:
            u = q.filter(_U.role == _UR.ADMIN).order_by(_U.id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Bu korxonada admin topilmadi")
        if getattr(u, "is_platform_admin", False):
            raise HTTPException(
                status_code=400,
                detail="Platforma adminining paroli bu yerdan tiklanmaydi")

        alifbo = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
        parol = "".join(secrets.choice(alifbo) for _ in range(12))
        u.password_hash = auth.hash_password(parol)

        # ── HISOBDORLIK ────────────────────────────────────────────
        # Platforma admini texnik jihatdan har doim kira oladi (bazaga
        # to'g'ridan-to'g'ri kirish bor) — buni yashirishning ma'nosi yo'q.
        # Ishonchni yaratadigan narsa — imkoniyatning yo'qligi emas, balki
        # har bir bunday amalning KO'RINADIGAN bo'lishi. Shuning uchun:
        #   1) yozuv MIJOZNING o'z audit jurnaliga tushadi;
        #   2) mijozning Telegram botiga darhol xabar ketadi.
        # Ya'ni siz parolni tiklay olasiz, lekin JIMGINA emas.
        crud.log_activity(
            db, "password_reset", "user", u.id, u.username,
            performed_by=f"Platforma administratori ({current_user.username})",
            new_value="Parol platforma administratori tomonidan tiklandi",
            company_id=company_id)
        db.commit()
        login = u.username

    # Xabarnoma tranzaksiyadan KEYIN — Telegram ishlamasa ham parol
    # tiklangan bo'lib qoladi.
    try:
        _send_telegram(
            f"🔑 *Diqqat: parol tiklandi*\n\n"
            f"`{login}` hisobining paroli platforma administratori "
            f"tomonidan yangilandi.\n\n"
            f"Agar buni siz so'ramagan bo'lsangiz — darhol bog'laning.",
            company_id=company_id)
    except Exception:
        pass

    return {"status": "ok", "username": login, "password": parol,
            "eslatma": "Parol FAQAT SHU YERDA ko'rsatiladi. "
                       "Mijozning audit jurnaliga yozuv tushdi va botiga xabar yuborildi."}


@app.get("/api/settings/company")
def api_get_company(db: Session = Depends(get_db),
                    current_user=Depends(auth.require_login)):
    """Joriy korxona ma'lumoti (nomi interfeysda ko'rsatiladi)."""
    from production_models import Company as _Co
    cid = auth.company_id_of(current_user)
    row = db.query(_Co).filter(_Co.id == cid).first()
    return {"id": cid, "name": (row.name if row else None),
            "code": (row.code if row else None),
            "slogan": (getattr(row, "slogan", None) if row else None),
            "phone": (getattr(row, "phone", None) if row else None),
            "address": (getattr(row, "address", None) if row else None),
            "logo_path": (getattr(row, "logo_path", None) if row else None)}


@app.put("/api/settings/company")
def api_set_company(name: str = Form(...), slogan: str = Form(None),
                    phone: str = Form(None), address: str = Form(None),
                    db: Session = Depends(get_db),
                    current_user=Depends(auth.admin_only)):
    """Korxona brendi: nomi, shiori, telefoni, manzili.

    Bu ma'lumot yuk xati, nakladnoy va moliya hisobotlarida ishlatiladi.
    Berilmagan (None) maydon o'zgarmaydi; bo'sh matn — tozalaydi."""
    from production_models import Company as _Co
    nom = (name or "").strip()
    if len(nom) < 2:
        raise HTTPException(status_code=400, detail="Nom juda qisqa")
    if len(nom) > 200:
        raise HTTPException(status_code=400, detail="Nom juda uzun (200 belgidan ko'p)")
    cid = auth.company_id_of(current_user)
    row = db.query(_Co).filter(_Co.id == cid).first()
    if not row:
        raise HTTPException(status_code=404, detail="Korxona topilmadi")
    row.name = nom
    # 2026-09-20 — MUHIM: bo'sh maydon "tozalash" degani.
    # Ilgari `if qiymat is None: continue` yozilgan edi, lekin FastAPI
    # bo'sh form maydonini `None` deb uzatadi — natijada foydalanuvchi
    # telefonni o'chirib saqlasa, eski qiymat joyida qolardi (jonli
    # sinovda aniqlandi). Endi to'rttala maydon HAR DOIM so'rovdan
    # o'rnatiladi: interfeys ularni doim birga yuboradi.
    for maydon, qiymat, chegara in (("slogan", slogan, 150),
                                    ("phone", phone, 60),
                                    ("address", address, 200)):
        v = (qiymat or "").strip()
        if len(v) > chegara:
            raise HTTPException(status_code=400,
                                detail=f"'{maydon}' juda uzun ({chegara} belgidan ko'p)")
        setattr(row, maydon, v or None)
    db.commit()
    _clear_company_name_cache(cid)
    return {"status": "ok", "name": nom}


@app.get("/api/settings/categories")
def api_get_categories(db: Session = Depends(get_db),
                       current_user=Depends(auth.admin_only)):
    """Ixtiyoriy kategoriyalar va ularning holati."""
    cid = auth.company_id_of(current_user)
    yoqilgan = enabled_categories_of(cid)
    return {"categories": [{"code": k, "label": v, "enabled": k in yoqilgan}
                           for k, v in IXTIYORIY_KATEGORIYALAR]}


@app.put("/api/settings/categories")
def api_set_categories(codes: str = Form(""), db: Session = Depends(get_db),
                       current_user=Depends(auth.admin_only)):
    """Yoqilgan kategoriyalarni saqlaydi (vergul bilan ajratilgan).

    Bo'sh yuborilsa — barcha ixtiyoriy turlar o'chadi (faqat asosiy
    uchtasi qoladi). Asosiy turlar (profil, panel, donali)
    har doim yoqiq va bu yerdan o'chirilmaydi."""
    ruxsat = {k for k, _ in IXTIYORIY_KATEGORIYALAR}
    tanlangan = [x.strip() for x in (codes or "").split(",") if x.strip() in ruxsat]
    _cid = auth.company_id_of(current_user)
    crud.set_setting(db, "enabled_categories", ",".join(tanlangan), company_id=_cid)
    _clear_category_cache(_cid)
    return {"status": "ok", "enabled": tanlangan}


@app.post("/api/settings/company/logo")
async def api_upload_company_logo(file: UploadFile = File(...),
                                  db: Session = Depends(get_db),
                                  current_user=Depends(auth.admin_only)):
    """Korxona logotipini yuklaydi (hujjatlarda ishlatiladi).

    Faqat rasm, 2 MB gacha. Fayl `static/logos/company_<id>.<kengaytma>`
    nomi bilan saqlanadi — ya'ni har korxonaning o'z fayli bor va
    bir-birining ustiga yozilmaydi."""
    import os as _os
    RUXSAT = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
    if file.content_type not in RUXSAT:
        raise HTTPException(status_code=400,
                            detail="Faqat PNG, JPG yoki WEBP rasm yuklash mumkin")
    data = await file.read()
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Rasm 2 MB dan katta bo'lmasin")
    if not data:
        raise HTTPException(status_code=400, detail="Fayl bo'sh")

    cid = auth.company_id_of(current_user)
    papka = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "static", "logos")
    _os.makedirs(papka, exist_ok=True)
    kengaytma = RUXSAT[file.content_type]
    nom = f"company_{cid}{kengaytma}"
    with open(_os.path.join(papka, nom), "wb") as f:
        f.write(data)

    from production_models import Company as _Co
    row = db.query(_Co).filter(_Co.id == cid).first()
    if not row:
        raise HTTPException(status_code=404, detail="Korxona topilmadi")
    # Eski boshqa kengaytmali fayllarni tozalaymiz
    for k in (".png", ".jpg", ".webp"):
        if k != kengaytma:
            eski = _os.path.join(papka, f"company_{cid}{k}")
            if _os.path.exists(eski):
                try:
                    _os.remove(eski)
                except OSError:
                    pass
    row.logo_path = f"static/logos/{nom}"
    db.commit()
    return {"status": "ok", "logo_path": row.logo_path}


@app.get("/api/settings/telegram-bot")
def api_get_telegram_bot(db: Session = Depends(get_db),
                         current_user=Depends(auth.admin_only)):
    """Korxonaning o'z Telegram boti sozlamasi (Faza 3).

    Token QAYTARILMAYDI — faqat sozlangan yoki yo'qligi va oxirgi 4 belgisi.
    Aks holda token brauzer tarixida va loglarda qolib ketardi."""
    cid = auth.company_id_of(current_user)
    tok = crud.get_setting(db, "telegram_bot_token", "", company_id=cid) or ""
    chat = crud.get_setting(db, "telegram_chat_id", "", company_id=cid) or ""
    return {"configured": bool(tok),
            "token_hint": (("…" + tok[-4:]) if len(tok) >= 4 else ""),
            "chat_id": chat}


@app.put("/api/settings/telegram-bot")
def api_set_telegram_bot(token: str = Form(""), chat_id: str = Form(""),
                         db: Session = Depends(get_db),
                         current_user=Depends(auth.admin_only)):
    """Korxonaning Telegram boti tokenini va xabar manzilini saqlaydi.

    Har korxona O'Z botiga ega bo'ladi (@BotFather orqali yaratiladi).
    Bo'sh token yuborilsa — eski qiymat saqlanib qoladi (tasodifan
    o'chirib yubormaslik uchun); tozalash uchun "-" yuboriladi."""
    cid = auth.company_id_of(current_user)
    t = (token or "").strip()
    if t == "-":
        crud.set_setting(db, "telegram_bot_token", "", company_id=cid)
    elif t:
        crud.set_setting(db, "telegram_bot_token", t, company_id=cid)
    c = (chat_id or "").strip()
    if c == "-":
        crud.set_setting(db, "telegram_chat_id", "", company_id=cid)
    elif c:
        crud.set_setting(db, "telegram_chat_id", c, company_id=cid)
    return {"status": "ok"}


@app.post("/api/system/restore")
async def api_restore_backup(file: UploadFile = File(...),
                             replace: bool = False,
                             db: Session = Depends(get_db),
                             current_user=Depends(auth.platform_admin_only)):
    """Zaxira nusxadan korxona ma'lumotini tiklaydi (Faza 2).

    Faqat JORIY korxonaga tiklanadi. Korxonada ma'lumot bo'lsa,
    `?replace=true` berilmaguncha rad etiladi; berilsa avval SHU korxona
    tozalanadi (boshqa korxonalarga tegilmaydi). Hammasi bitta
    tranzaksiyada — xato bo'lsa hech narsa o'zgarmaydi."""
    import json as _json_r
    try:
        raw = await file.read()
        data = _json_r.loads(raw.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Faylni o'qib bo'lmadi: {e}")

    result = crud.import_full_backup(
        db, data, company_id=auth.company_id_of(current_user), replace=replace)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Tiklash amalga oshmadi"))
    return result


# ============================================================
# ZAXIRADAN TIKLASH — OPERATOR SAHIFASI  (2026-09-20)
# ============================================================
# Nega alohida sahifa: `POST /api/system/restore` faqat API orqali
# chaqirilardi, ya'ni fayl yuklash uchun maxsus vosita kerak edi.
# Bu sahifa o'sha bo'shliqni yopadi.
#
# Nega JavaScriptsiz: bu operator vositasi — eng kam harakatlanuvchi
# qismdan iborat bo'lgani ma'qul. Oddiy HTML forma POST qiladi, natijani
# server chizadi. Hech qanday fetch, hech qanday dinamik holat.
#
# Nega `/api/` dan TASHQARIDA: sessiya tugasa, 401 javobi `/login` ga
# yo'naltirilsin (api yo'llari xom JSON qaytaradi).

_TIKLASH_SOZ = "TIKLASHNI-TASDIQLAYMAN"


def _tiklash_html(tana: str) -> str:
    return f"""<!doctype html><html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Zaxiradan tiklash</title><style>
 body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
   background:#f6f7f9;color:#1a1d21;margin:0;padding:24px;line-height:1.55}}
 .w{{max-width:640px;margin:0 auto;background:#fff;border:1px solid #e3e6ea;
   border-radius:12px;padding:28px}}
 h1{{font-size:20px;margin:0 0 4px}} .sub{{color:#6b7280;font-size:13px;margin-bottom:22px}}
 .ogoh{{background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:14px;
   font-size:13px;margin-bottom:20px}}
 .xato{{background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:14px;margin-bottom:18px}}
 .ok{{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:14px;margin-bottom:18px}}
 label{{display:block;font-size:12px;font-weight:600;text-transform:uppercase;
   letter-spacing:.03em;color:#6b7280;margin:16px 0 6px}}
 input[type=text],input[type=file]{{width:100%;box-sizing:border-box;padding:10px 12px;
   border:1px solid #d1d5db;border-radius:8px;font-size:14px;background:#fff}}
 .qator{{display:flex;align-items:center;gap:8px;margin-top:16px;font-size:14px}}
 button{{margin-top:22px;width:100%;padding:12px;border:0;border-radius:8px;
   background:#111827;color:#fff;font-size:15px;font-weight:600;cursor:pointer}}
 table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}}
 td{{padding:5px 0;border-bottom:1px solid #f1f2f4}}
 td:last-child{{text-align:right;font-variant-numeric:tabular-nums}}
 a{{color:#2563eb}} code{{background:#f3f4f6;padding:1px 5px;border-radius:4px;font-size:12px}}
</style></head><body><div class="w">{tana}</div></body></html>"""


@app.get("/tiklash", response_class=HTMLResponse)
def tiklash_sahifa(request: Request, db: Session = Depends(get_db),
                   current_user=Depends(auth.platform_admin_only)):
    """Zaxira faylini yuklash formasi."""
    from models import Order as _O, Inventory as _I, Master as _M, Project as _P
    cid = auth.company_id_of(current_user)
    son = {
        "Buyurtmalar": db.query(_O).filter(_O.company_id == cid).count(),
        "Loyihalar": db.query(_P).filter(_P.company_id == cid).count(),
        "Ombor": db.query(_I).filter(_I.company_id == cid).count(),
        "Ustalar": db.query(_M).filter(_M.company_id == cid).count(),
    }
    jadval = "".join(f"<tr><td>{k}</td><td><b>{v}</b></td></tr>" for k, v in son.items())
    bosh = sum(son.values()) == 0

    tana = f"""
    <h1>Zaxiradan tiklash</h1>
    <div class="sub">Korxona <b>#{cid}</b> · foydalanuvchi <b>{current_user.username}</b></div>

    <div class="ogoh">
      <b>Hozirgi holat</b>
      <table>{jadval}</table>
      <div style="margin-top:10px">
        { "Korxona bo'sh — ustiga yozish belgisi kerak emas."
          if bosh else
          "Korxonada ma'lumot bor. Tiklash uchun <b>ustiga yozish</b> belgilanishi "
          "va tasdiqlash so'zi kiritilishi shart. Mavjud ma'lumot <b>o'chadi</b>." }
      </div>
    </div>

    <form method="post" action="/tiklash" enctype="multipart/form-data">
      <label>Zaxira fayli (.json)</label>
      <input type="file" name="file" accept=".json,application/json" required>

      <div class="qator">
        <input type="checkbox" name="replace" value="true" id="r">
        <label for="r" style="margin:0;text-transform:none;font-weight:500;color:#1a1d21">
          Mavjud ma'lumot ustiga yozilsin (avval tozalanadi)
        </label>
      </div>

      <label>Tasdiqlash so'zi</label>
      <input type="text" name="confirm" placeholder="{_TIKLASH_SOZ}" autocomplete="off">
      <div style="font-size:12px;color:#6b7280;margin-top:5px">
        Faqat ustiga yozishda talab qilinadi. Aynan shunday yozing:
        <code>{_TIKLASH_SOZ}</code>
      </div>

      <button type="submit">Tiklashni boshlash</button>
    </form>

    <div style="font-size:12px;color:#6b7280;margin-top:20px">
      Login hisoblari (<code>users</code>) tiklanmaydi — hozirgi hisoblaringiz
      saqlanib qoladi. Boshqa korxonalarga tegilmaydi. Hammasi bitta
      tranzaksiyada: xato bo'lsa hech narsa o'zgarmaydi.
    </div>
    """
    return HTMLResponse(_tiklash_html(tana))


@app.post("/tiklash", response_class=HTMLResponse)
async def tiklash_bajarish(file: UploadFile = File(...),
                           replace: str = Form(default=""),
                           confirm: str = Form(default=""),
                           db: Session = Depends(get_db),
                           current_user=Depends(auth.platform_admin_only)):
    """Formadan kelgan faylni tiklaydi va natijani sahifada ko'rsatadi."""
    import json as _js_t

    def xato(matn):
        return HTMLResponse(_tiklash_html(
            f'<h1>Tiklash bajarilmadi</h1><div class="xato">{matn}</div>'
            f'<a href="/tiklash">&larr; Qaytish</a>'), status_code=400)

    ustiga = str(replace).lower() in ("true", "on", "1", "yes")
    if ustiga and confirm.strip() != _TIKLASH_SOZ:
        return xato(f"Ustiga yozish uchun tasdiqlash so'zi kerak: <code>{_TIKLASH_SOZ}</code>")

    raw = await file.read()
    if not raw:
        return xato("Fayl bo'sh.")
    if len(raw) > 200 * 1024 * 1024:
        return xato("Fayl juda katta (200 MB dan oshdi).")
    try:
        data = _js_t.loads(raw.decode("utf-8"))
    except Exception as e:
        return xato(f"JSON o'qilmadi: {e}")

    try:
        natija = crud.import_full_backup(
            db, data, company_id=auth.company_id_of(current_user), replace=ustiga)
    except Exception as e:
        return xato(f"Tiklashda xato: {e}")

    if not natija.get("success"):
        return xato(natija.get("message", "Tiklash amalga oshmadi"))

    per = natija.get("per_table") or {}
    jadval = "".join(f"<tr><td>{k}</td><td><b>{v}</b></td></tr>"
                     for k, v in sorted(per.items()) if v)
    tashlab = natija.get("skipped_tables") or []

    try:
        crud.log_activity(db, action="Zaxiradan tiklash", entity_type="system",
                          entity_id=0, entity_label=file.filename,
                          performed_by=getattr(current_user, "username", None),
                          new_value=f"ustiga_yozish={ustiga}")
    except Exception:
        pass

    tana = (f'<h1>Tiklash yakunlandi</h1>'
            f'<div class="ok">'
            f'<b>{natija.get("restored_rows", 0)}</b> ta yozuv, '
            f'<b>{natija.get("restored_tables", 0)}</b> ta jadvalga tiklandi.<br>'
            f'Ketma-ketliklar (sequence) to\'g\'rilandi: '
            f'<b>{natija.get("sequences_fixed", 0)}</b>'
            + (f'<br>Tashlab ketilgan jadvallar: <code>'
               + ", ".join(map(str, tashlab)) + "</code>" if tashlab else "")
            + f'</div>'
            f'<table>{jadval}</table>'
            f'<div style="font-size:12px;color:#6b7280;margin-top:16px">'
            f'Login hisoblari tiklanmadi — hozirgi hisobingiz bilan davom eting.</div>'
            f'<div style="margin-top:18px"><a href="/">Bosh sahifa</a> &nbsp;\u00b7&nbsp; '
            f'<a href="/tiklash">Tiklash sahifasi</a></div>')
    return HTMLResponse(_tiklash_html(tana))


@app.post("/api/system/factory-reset")
def api_factory_reset(confirm: str = "", keep_only_self: bool = False,
                       db: Session = Depends(get_db), current_user=Depends(auth.platform_admin_only)):
    """DIQQAT: QAYTARIB BO'LMAYDIGAN AMAL!
    Foydalanuvchilardan (login) TASHQARI — BARCHA ma'lumotni butunlay o'chiradi:
    buyurtmalar, ombor, retseptlar, ustalar, yetkazib beruvchilar, loyihalar va h.k.
    Agar keep_only_self=True bo'lsa — FAQAT hozirgi (o'zi) hisobidan tashqari,
    boshqa BARCHA foydalanuvchilar (login) hisoblari HAM o'chiriladi.
    Xavfsizlik uchun — aniq tasdiqlash so'zisiz ishlamaydi."""
    REQUIRED_PHRASE = "HAMMASINI-OCHIR"
    if confirm != REQUIRED_PHRASE:
        raise HTTPException(
            status_code=400,
            detail=f"Xavfsizlik uchun, so'rovga ?confirm={REQUIRED_PHRASE} qo'shing. "
                   "DIQQAT: bu amal QAYTARIB BO'LMAYDI!"
        )
    keep_id = current_user.id if keep_only_self else None
    # M7: reset FAQAT joriy korxona doirasida — boshqa korxona ma'lumoti
    # o'chmaydi.
    result = crud.factory_reset_all_data(db, keep_only_user_id=keep_id,
                                         company_id=auth.company_id_of(current_user))
    msg = ("Korxonangizning barcha ma'lumoti tozalandi (faqat siz qoldingiz)"
           if keep_only_self else
           "Korxonangizning barcha ma'lumoti tozalandi (Foydalanuvchilardan tashqari)")
    return {"status": "ok", "message": msg, "deleted": result}


@app.get("/kpi", response_class=HTMLResponse)
async def kpi_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    """Ustalar yillik KPI va moslashuvchan hodim to'lovi sahifasi."""
    return templates.TemplateResponse(request, "kpi.html", {
        "current_user": current_user, "active_page": "kpi"
    })


@app.get("/api/finished")
def api_get_finished(source: Optional[str] = None, only_available: bool = False, show_all: bool = False,
                     db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    """Tayyor mahsulotlar ro'yxati."""
    _cid = auth.company_id_of(current_user)   # M4
    if source or only_available:
        items = crud.get_finished_products(db, source=source, only_available=only_available,
                                           company_id=_cid)
    else:
        items = crud.get_finished_products_for_main_page(db, days=90, show_all=show_all,
                                                         company_id=_cid)
    return [{
        "id": fp.id,
        "name": fp.name,
        "category": fp.category,
        # Bosqich 3, 10-band — tayyor mahsulotning mahsulot TURI.
        # Eski turkumlarda NULL (hali `ProductType` yozuvi yo'q).
        "product_type_id": fp.product_type_id,
        "width": fp.width,
        "thickness": fp.thickness,
        "is_coated": fp.is_coated,
        "quantity": float(fp.quantity or 0),
        "unit": fp.unit,
        "unit_price": float(fp.unit_price or 0),
        "cost_price": float(fp.cost_price or 0),
        "source": fp.source.value,
        "from_order_id": fp.from_order_id,
        "from_order_number": fp.from_order.order_number if fp.from_order else None,
        "return_reason": fp.return_reason,
        "volume_m3": float(fp.volume_m3 or 0),
        "planned_loy_kg": float(fp.planned_loy_kg or 0),
        "actual_loy_kg": float(fp.actual_loy_kg) if fp.actual_loy_kg is not None else None,
        "unit_volume_m3": float(fp.unit_volume_m3) if fp.unit_volume_m3 is not None else None,
        "unit_loy_kg": float(fp.unit_loy_kg) if fp.unit_loy_kg is not None else None,
        "production_status": fp.production_status.value if fp.production_status else None,
        "recipe_id": fp.recipe_id,
        "created_at": fp.created_at.isoformat() if fp.created_at else None,
        "created_by": fp.created_by,
        "notes": fp.notes,
        "image_url": fp.image_url,
        "reserved_quantity": float(fp.reserved_quantity or 0),
        "reserved_for_order_item_id": fp.reserved_for_order_item_id,
        "total_value": round(float(fp.quantity or 0) * float(fp.unit_price or 0))
    } for fp in items]


@app.post("/api/finished/{fp_id}/image")
def api_upload_finished_image(fp_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                               current_user=Depends(auth.admin_warehouse_or_manager)):
    # M4: mahsulot FAQAT joriy korxonadan (aks holda 404).
    fp = auth.finished_product_of_company(db, fp_id, auth.company_id_of(current_user))
    if not fp:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
    url = _save_upload(file, "finished", ALLOWED_IMAGE_EXT)
    fp.image_url = url
    db.commit()
    return {"image_url": url}


@app.post("/api/projects/{project_id}/image")
def api_upload_project_image(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                              current_user=Depends(auth.admin_manager_accountant)):
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.project_of_company(db, project_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    from models import Project
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    url = _save_upload(file, "projects", ALLOWED_IMAGE_EXT)
    proj.image_url = url
    db.commit()
    return {"image_url": url}


@app.post("/api/returns/{return_id}/image")
def api_upload_return_image(return_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                             current_user=Depends(auth.manager_or_warehouse)):
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.return_of_company(db, return_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Qaytarish topilmadi")
    from models import ReturnItem
    ret = db.query(ReturnItem).filter(ReturnItem.id == return_id).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Qaytarish topilmadi")
    url = _save_upload(file, "returns", ALLOWED_IMAGE_EXT)
    ret.image_url = url
    db.commit()
    return {"image_url": url}


@app.get("/api/finished/stats")
def api_finished_stats(db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    return crud.get_finished_stats(db, company_id=auth.company_id_of(current_user))


@app.get("/api/finished/search")
def api_search_finished(q: str = "", category: Optional[str] = None, exclude_category: Optional[str] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    """Nom bo'yicha qidirish — buyurtmada taklif uchun. category — masalan
    'profil', faqat shu turdagi mahsulotlarni ko'rsatish uchun (ixtiyoriy)."""
    try:
        return {"items": crud.search_finished_products(db, q, category=category,
                                                      exclude_category=exclude_category,
                                                      company_id=auth.company_id_of(current_user))}
    except Exception as e:
        import traceback
        print("Tayyor mahsulot qidiruvida XATO:\n", traceback.format_exc())
        return {"items": [], "error": str(e)}


@app.post("/api/finished/loss")
def api_record_finished_loss(data: schemas.FinishedProductLossCreate, db: Session = Depends(get_db),
                               current_user=Depends(auth.admin_warehouse_or_manager)):
    """Tayyor mahsulotdan brak/yo'qotish sababli miqdorni kamaytirish (o'chirish emas)."""
    who = current_user.full_name or current_user.username
    result = crud.record_finished_product_loss(db, data, created_by=who,
                                              company_id=auth.company_id_of(current_user))
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.delete("/api/finished/loss/{loss_id}")
def api_delete_finished_loss(loss_id: int, db: Session = Depends(get_db),
                             current_user=Depends(auth.admin_only)):
    """Xato yozilgan brakni bekor qiladi (2026-09-20 da qo'shildi).

    Ilgari brakni orqaga qaytarish yo'li UMUMAN yo'q edi — bir marta
    yozilgan brak Moliyadagi "Brak xarajati" da abadiy qolib ketardi.
    Faqat admin, faqat o'z korxonasi, Faoliyat jurnaliga yoziladi."""
    who = current_user.full_name or current_user.username
    natija = crud.delete_finished_product_loss(
        db, loss_id, company_id=auth.company_id_of(current_user), performed_by=who)
    if not natija["success"]:
        raise HTTPException(status_code=404, detail=natija["message"])
    return natija


@app.post("/api/finished/{fp_id}/release-reservation")
def api_release_finished_product_reservation(fp_id: int, db: Session = Depends(get_db),
                                               current_user=Depends(auth.admin_warehouse_or_manager)):
    """2026-09-17: Production/MRP orqali biror buyurtmaga band qilingan
    tayyor mahsulotni ozod qilib, umumiy sotuvga qaytaradi."""
    who = current_user.full_name or current_user.username
    result = crud.release_finished_product_reservation(
        db, fp_id, performed_by=who, company_id=auth.company_id_of(current_user))
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.post("/api/finished/production-brak")
def api_finished_production_brak(data: schemas.FinishedProductProductionBrakCreate, db: Session = Depends(get_db),
                                   current_user=Depends(auth.admin_warehouse_or_manager)):
    """Tayyor mahsulot ISHLAB CHIQARISH JARAYONIDA chiqqan brak — mahsulot
    soniga tegmaydi, faqat qo'shimcha xomashyo ombordan ayiriladi.
    Profil/Panel/Donali/Blok — `brak_qty` (mahsulot birligida) orqali,
    BARQAROR nisbatdan hisoblab."""
    who = current_user.full_name or current_user.username
    result = crud.record_finished_product_production_brak(
        db, data.finished_product_id, data.brak_qty, data.notes, created_by=who,
        company_id=auth.company_id_of(current_user),
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.post("/api/finished/sell-batch")
def api_sell_finished_products_batch(data: schemas.FinishedProductSaleBatchCreate, db: Session = Depends(get_db),
                                       current_user=Depends(auth.admin_warehouse_or_manager)):
    """Bir nechta turli tayyor mahsulotni, bitta xaridorga, bitta Yuk xati bilan sotish."""
    who = current_user.full_name or current_user.username
    result = crud.sell_finished_products_batch(db, data, created_by=who,
                                              company_id=auth.company_id_of(current_user))
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.post("/api/finished/sell")
def api_sell_finished_product(data: schemas.FinishedProductSaleCreate, db: Session = Depends(get_db),
                                current_user=Depends(auth.admin_warehouse_or_manager)):
    """Tayyor mahsulotni to'g'ridan-to'g'ri sotish (buyurtma/Yuk xatisiz)."""
    who = current_user.full_name or current_user.username
    result = crud.sell_finished_product(db, data, created_by=who,
                                       company_id=auth.company_id_of(current_user))
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.get("/api/finished/sales")
def api_get_finished_sales(year: Optional[int] = None, month: Optional[int] = None,
                            db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    """Tayyor mahsulot savdolari tarixi (ixtiyoriy oy/yil filtri bilan)."""
    from models import FinishedProductSale
    from sqlalchemy import extract
    # M4 (2026-09-18) — TENANT: sotuvlar ro'yxati korxona filtrisiz edi (H-5).
    q = db.query(FinishedProductSale).filter(
        FinishedProductSale.company_id == auth.company_id_of(current_user)
    ).order_by(FinishedProductSale.sold_at.desc())
    if year:
        q = q.filter(extract('year', FinishedProductSale.sold_at) == year)
    if month:
        q = q.filter(extract('month', FinishedProductSale.sold_at) == month)
    sales = q.limit(200).all()
    return [{
        "id": s.id, "product_name": s.product_name, "quantity": float(s.quantity),
        "unit": s.unit, "unit_price": float(s.unit_price), "total_amount": float(s.total_amount),
        "cost_amount": float(s.cost_amount or 0), "sold_at": s.sold_at.isoformat() if s.sold_at else None,
        "buyer_name": s.buyer_name, "payment_method": s.payment_method, "notes": s.notes
    } for s in sales]


@app.post("/api/finished/produce")
def api_produce(data: schemas.ProduceCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    """Tayyor mahsulot ishlab chiqarish."""
    who = current_user.full_name or current_user.username
    result = crud.produce_finished_product(db, data, created_by=who,
                                          company_id=auth.company_id_of(current_user))
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)

    # Ombor ogohlantirishi
    low_items = crud.get_low_stock_items(db)
    if low_items:
        lines = []
        for item in low_items:
            qty = float(item.stock_quantity)
            min_q = float(item.min_stock)
            emoji = "🔴" if qty <= min_q * 0.5 else "🟡"
            lines.append(f"{emoji} {item.item_name}: {qty:.1f} {item.unit} qoldi (min: {min_q:.0f})")
        msg = ("⚠️ *Ombor ogohlantirishlari!*\n\nTayyor mahsulot ishlab chiqarilgandan keyin:\n\n"
               + "━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
               + "\n━━━━━━━━━━━━━━━━━━━\n\n🏗 *PenoDecorPro* — Andijon")
        _send_telegram(msg)

    return result
@app.post("/api/finished/{fp_id}/complete")
def api_complete_production(fp_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    """Mahsulotni 'Tayyor' deb belgilash — sotuvga tayyor."""
    result = crud.complete_production(db, fp_id, company_id=auth.company_id_of(current_user))
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.get("/api/finished/{fp_id}/profit")
def api_finished_profit(fp_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_financier)):
    """Tayyor mahsulot foydasi (faqat admin)."""
    result = crud.get_finished_profit(db, fp_id, company_id=auth.company_id_of(current_user))
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.post("/api/finished/{fp_id}/add")
def api_add_production(fp_id: int, data: schemas.StockAdjust,
                       db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    """Tayyor mahsulotga miqdor qo'shish — xomashyo proporsional yechiladi."""
    result = crud.add_to_production(db, fp_id, data.quantity,
                                    company_id=auth.company_id_of(current_user))
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)

    # Ombor ogohlantirishi
    low_items = crud.get_low_stock_items(db)
    if low_items:
        lines = []
        for item in low_items:
            qty = float(item.stock_quantity)
            min_q = float(item.min_stock)
            emoji = "🔴" if qty <= min_q * 0.5 else "🟡"
            lines.append(f"{emoji} {item.item_name}: {qty:.1f} {item.unit} qoldi (min: {min_q:.0f})")
        msg = ("⚠️ *Ombor ogohlantirishlari!*\n\n"
               + "━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
               + "\n━━━━━━━━━━━━━━━━━━━\n\n🏗 *PenoDecorPro* — Andijon")
        _send_telegram(msg)

    return result


@app.post("/api/finished/{fp_id}/reduce")
def api_reduce_production(fp_id: int, data: schemas.StockAdjust,
                          db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    """Tayyor mahsulot miqdorini kamaytirish (brak/singan) — xomashyo qaytmaydi."""
    result = crud.reduce_production(db, fp_id, data.quantity, data.reason,
                                    company_id=auth.company_id_of(current_user))
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.put("/api/finished/{fp_id}")
def api_update_finished(fp_id: int, data: schemas.FinishedProductUpdate,
                        db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    """Tayyor mahsulotni tahrirlash."""
    fp = crud.update_finished_product(db, fp_id, data.model_dump(exclude_unset=True),
                                      company_id=auth.company_id_of(current_user))
    if not fp:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok", "quantity": float(fp.quantity), "unit_price": float(fp.unit_price or 0)}


@app.delete("/api/finished/{fp_id}")
def api_delete_finished(fp_id: int, return_to_stock: bool = False,
                        db: Session = Depends(get_db), current_user=Depends(auth.admin_warehouse_or_manager)):
    """Tayyor mahsulotni o'chirish.
    - IN_PROGRESS: xato tuzatish deb hisoblanadi — o'chadi, xomashyo qaytadi.
    - READY: faqat qoldiq 0 bo'lsa o'chadi, xomashyo qaytmaydi."""
    from models import ProductionStatus as _PS
    # M4: mahsulot FAQAT joriy korxonadan (aks holda 404).
    _cid = auth.company_id_of(current_user)
    fp = auth.finished_product_of_company(db, fp_id, _cid)
    if not fp:
        raise HTTPException(status_code=404, detail="Topilmadi")
    if fp.production_status != _PS.IN_PROGRESS and float(fp.quantity or 0) > 0.001:
        raise HTTPException(
            status_code=400,
            detail=f"Bu mahsulotda hali {float(fp.quantity):g} {fp.unit} qoldiq bor — "
                   f"o'chirib bo'lmaydi. Avval to'liq soting yoki \"Kamaytirish (brak)\" "
                   f"orqali nolga tushiring, keyin o'chiring."
        )
    if not crud.delete_finished_product(db, fp_id, company_id=_cid):
        raise HTTPException(status_code=400, detail="O'chirib bo'lmadi")
    return {"status": "ok"}


# ============================================================
# DELIVERIES — Yetkazishlar
# ============================================================

@app.get("/api/orders/{order_id}/delivery-status")
def api_delivery_status(order_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Buyurtmaning yetkazish holati."""
    # M2: buyurtma FAQAT joriy korxonadan (aks holda 404).
    if not crud.get_order(db, order_id, company_id=auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    result = crud.get_delivery_status(db, order_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/api/orders/{order_id}/pin")
def api_toggle_order_pin(order_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    # ⚠ 2026-09-21, IDOR testi bilan topildi (tools/test_idor.py):
    # bu yerda M2 qo'riqchisi TUSHIB QOLGAN edi. `crud.toggle_order_pin`
    # buyurtmani faqat ID bo'yicha topadi, korxonani tekshirmaydi —
    # natijada B korxona admini A korxonaning buyurtmasini qadab/yechib
    # qo'ya olardi (HTTP da o'lchangan: 200 qaytdi va `is_pinned`
    # HAQIQATAN o'zgardi). Bundan tashqari 200/404 farqi "bu ID boshqa
    # korxonada bormi" degan savolga javob berardi.
    # `TENANT_FILTER=1` buni yopadi, lekin u standart holatda O'CHIQ va
    # o'chirilishi mumkin — shuning uchun teshik ILDIZIDAN yopiladi.
    if not auth.order_of_company(db, order_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    result = crud.toggle_order_pin(db, order_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "Topilmadi"))
    return result


@app.post("/api/deliveries")
def api_create_delivery(data: schemas.DeliveryCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Yangi yetkazish."""
    who = current_user.full_name or current_user.username
    result = crud.create_delivery(db, data, delivered_by=who, company_id=auth.company_id_of(current_user))
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)

    # Telegram xabar
    d = crud.get_delivery(db, result["delivery_id"])
    if d and d.order:
        lines = []
        for di in d.items:
            nm = di.order_item.name if di.order_item else "—"
            lines.append(f"• {nm}: {di.quantity:g} {di.unit}")
        client = d.order.project.client_name if d.order.project else "—"
        msg = (
            f"📦 *Mahsulot topshirildi*\n\n"
            f"📋 {d.delivery_number}\n"
            f"👤 Mijoz: {client}\n\n"
            + "\n".join(lines)
            + f"\n\n📊 Bajarilish: *{result['delivery_percent']}%*"
            + ("\n✅ *Buyurtma to'liq topshirildi!*" if result["is_fully_delivered"] else "")
            + f"\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        _send_telegram(msg)
        _send_delivery_pdf_to_customer(db, result["delivery_id"])

    return result


@app.get("/api/finished/sales/batch/{group_id}/pdf")
def api_finished_sale_batch_pdf(group_id: str, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Bir nechta mahsulot — bitta Yuk xati (guruh bo'yicha)."""
    from fastapi.responses import Response
    import delivery_pdf
    import traceback
    from models import FinishedProductSale

    # M4 (2026-09-18) — TENANT: `group_id` ota tekshiruvisiz ishlatilardi —
    # A korxona xodimi B ning yuk xatini ochishi mumkin edi (H-7).
    sales = db.query(FinishedProductSale).filter(
        FinishedProductSale.sale_group_id == group_id,
        FinishedProductSale.company_id == auth.company_id_of(current_user)
    ).order_by(FinishedProductSale.id).all()
    if not sales:
        raise HTTPException(status_code=404, detail="Sotuv guruhi topilmadi")
    try:
        pdf_bytes = delivery_pdf.generate_finished_sale_batch_pdf(sales, group_id, db)
    except Exception as e:
        print("Sotuv guruhi PDF XATO:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"PDF xato: {str(e)}")

    filename = f"yuk_xati_sotuv_{group_id}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


@app.get("/api/finished/sales/{sale_id}/pdf")
def api_finished_sale_pdf(sale_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Tayyor mahsulot sotuvi uchun Yuk xati (PDF)."""
    from fastapi.responses import Response
    import delivery_pdf
    import traceback
    from models import FinishedProductSale

    # M4 (2026-09-18) — TENANT: `sale_id` ota tekshiruvisiz ishlatilardi (H-7).
    sale = db.query(FinishedProductSale).filter(
        FinishedProductSale.id == sale_id,
        FinishedProductSale.company_id == auth.company_id_of(current_user)
    ).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sotuv topilmadi")
    try:
        pdf_bytes = delivery_pdf.generate_finished_sale_pdf(sale, db)
    except Exception as e:
        print("Sotuv PDF XATO:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"PDF xato: {str(e)}")

    filename = f"yuk_xati_sotuv_{sale.id}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


@app.get("/api/deliveries/{delivery_id}/pdf")
def api_delivery_pdf(delivery_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Yetkazish nakladnoyi (PDF)."""
    from fastapi.responses import Response
    import delivery_pdf
    import traceback

    d = crud.get_delivery(db, delivery_id, company_id=auth.company_id_of(current_user))
    if not d:
        raise HTTPException(status_code=404, detail="Yetkazish topilmadi")
    try:
        pdf_bytes = delivery_pdf.generate_delivery_pdf(d, db)
    except Exception as e:
        print("Yetkazish PDF XATO:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"PDF xato: {str(e)}")

    filename = f"nakladnoy_{d.delivery_number.replace('/', '_')}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


@app.get("/api/orders/{order_id}/summary-pdf")
def api_summary_pdf(order_id: int, ids: str = "", db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Hisob-kitob varaqasi — tanlangan nakladnoylar bo'yicha.
    ids — vergul bilan ajratilgan delivery ID lar: '3,5,7'. Bo'sh bo'lsa — hammasi."""
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.order_of_company(db, order_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    from fastapi.responses import Response
    import delivery_pdf as _delivery_pdf
    import traceback as _tb
    from models import Order as _Order

    order = db.query(_Order).filter(_Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

    all_deliveries = sorted(order.deliveries, key=lambda x: x.delivered_at or datetime.min)
    if ids:
        try:
            wanted_ids = {int(x) for x in ids.split(",") if x.strip()}
        except ValueError:
            raise HTTPException(status_code=400, detail="ids parametri noto'g'ri")
        deliveries = [d for d in all_deliveries if d.id in wanted_ids]
    else:
        deliveries = all_deliveries

    if not deliveries:
        raise HTTPException(status_code=404, detail="Tanlangan yuk xatlari topilmadi")

    try:
        pdf_bytes = _delivery_pdf.generate_summary_pdf(order, deliveries, db)
    except Exception as e:
        print("Hisob-kitob PDF XATO:\n", _tb.format_exc())
        raise HTTPException(status_code=500, detail=f"PDF xato: {str(e)}")

    filename = f"hisob-kitob_{order.order_number.replace('/', '_')}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


# ============================================================
# MAHSULOT RASMI VA BUYURTMA FAYLLARI (faqat qo'shimcha — hisob-kitobga ta'sir qilmaydi)
# ============================================================

def _master_by_chat_id(db, chat_id):
    """Telegram chat_id bo'yicha ustani topadi (ko'p-tenantga tayyor).

    2026-09-19 — Faza 3 (Telegram): ilgari `Master.telegram_id` butun tizim
    bo'yicha YAGONA edi, shuning uchun bitta usta faqat BITTA korxonada
    ro'yxatdan o'ta olardi. SaaS uchun bu to'g'ri emas: bir usta ikki
    korxonada ishlashi mumkin. Cheklov `(company_id, telegram_id)` ga
    o'zgartirildi, ya'ni endi bir nechta moslik bo'lishi MUMKIN.

    Qaytaradi: (master, xato_matni). Bir nechta moslik topilsa — usta
    qaysi korxona nomidan yozayotgani NOMA'LUM, shuning uchun hech biri
    tanlanmaydi va tushunarli xabar qaytariladi. (Har korxonaga alohida
    bot ulanganda, korxona bot tokenidan aniqlanadi va bu holat
    umuman tug'ilmaydi — bu keyingi qadam.)"""
    from models import Master as _Mst
    rows = db.query(_Mst).filter(_Mst.telegram_id == chat_id,
                                 _Mst.is_active == True).all()
    if not rows:
        return None, None
    if len(rows) == 1:
        return rows[0], None
    return None, ("Sizning Telegram hisobingiz bir nechta korxonada usta "
                  "sifatida ro'yxatdan o'tgan. Iltimos, korxona "
                  "administratoriga murojaat qiling.")


ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
# CorelDRAW (.cdr) va AutoCAD (.dwg, .dxf) chizmalarini ham buyurtmaga
# biriktirish mumkin bo'lishi uchun qo'shildi (2026-09).
ALLOWED_DESIGN_EXT = {".cdr", ".dwg", ".dxf"}
ALLOWED_FILE_EXT = ALLOWED_IMAGE_EXT | {".pdf"} | ALLOWED_DESIGN_EXT
MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB (chizma fayllar rasm/PDF'dan ancha katta bo'lishi mumkin)


def _save_upload(file: UploadFile, subfolder: str, allowed_ext: set) -> str:
    import uuid
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"Ruxsat etilmagan fayl turi: {ext}")
    contents = file.file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="Fayl hajmi 25 MB dan katta bo'lmasin")
    folder = os.path.join(static_dir, "uploads", subfolder)
    os.makedirs(folder, exist_ok=True)
    fname = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(folder, fname), "wb") as f:
        f.write(contents)
    return f"/static/uploads/{subfolder}/{fname}"


@app.post("/api/order-items/{item_id}/image")
def api_upload_order_item_image(item_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                                 current_user=Depends(auth.orders_page_access)):
    # M2: detal FAQAT joriy korxonadan (aks holda 404).
    from models import OrderItem as _OI_g
    if not db.query(_OI_g).filter(
            _OI_g.id == item_id,
            _OI_g.company_id == auth.company_id_of(current_user)).first():
        raise HTTPException(status_code=404, detail="Detal topilmadi")
    from models import OrderItem
    item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Detal topilmadi")
    url = _save_upload(file, "order_items", ALLOWED_IMAGE_EXT)
    item.image_url = url
    db.commit()
    return {"image_url": url}


@app.delete("/api/order-items/{item_id}/image")
def api_delete_order_item_image(item_id: int, db: Session = Depends(get_db),
                                 current_user=Depends(auth.orders_page_access)):
    # M2: detal FAQAT joriy korxonadan (aks holda 404).
    from models import OrderItem as _OI_g
    if not db.query(_OI_g).filter(
            _OI_g.id == item_id,
            _OI_g.company_id == auth.company_id_of(current_user)).first():
        raise HTTPException(status_code=404, detail="Detal topilmadi")
    from models import OrderItem
    item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Detal topilmadi")
    item.image_url = None
    db.commit()
    return {"status": "ok"}


@app.post("/api/orders/{order_id}/attachments")
def api_upload_order_attachment(order_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                                 current_user=Depends(auth.orders_page_access)):
    from models import OrderAttachment, Order
    # M2: fayl FAQAT o'z korxonasining buyurtmasiga biriktiriladi.
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.company_id == auth.company_id_of(current_user)).first()
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    url = _save_upload(file, "order_attachments", ALLOWED_FILE_EXT)
    att = OrderAttachment(
        order_id=order_id, file_url=url, file_name=file.filename,
        uploaded_by=current_user.full_name or current_user.username
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return schemas.OrderAttachmentRead.model_validate(att)


@app.get("/api/orders/{order_id}/attachments")
def api_list_order_attachments(order_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    from models import OrderAttachment
    # M2: buyurtma FAQAT joriy korxonadan (aks holda 404).
    if not crud.get_order(db, order_id, company_id=auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    atts = db.query(OrderAttachment).filter(OrderAttachment.order_id == order_id).order_by(OrderAttachment.uploaded_at.desc()).all()
    return [schemas.OrderAttachmentRead.model_validate(a) for a in atts]


@app.delete("/api/orders/attachments/{attachment_id}")
def api_delete_order_attachment(attachment_id: int, db: Session = Depends(get_db),
                                 current_user=Depends(auth.orders_page_access)):
    from models import OrderAttachment
    # M2: biriktirmada company_id yo'q — ota (buyurtma) orqali tekshiriladi.
    from models import Order as _Ord
    att = (db.query(OrderAttachment)
           .join(_Ord, _Ord.id == OrderAttachment.order_id)
           .filter(OrderAttachment.id == attachment_id,
                   _Ord.company_id == auth.company_id_of(current_user))
           .first())
    if not att:
        raise HTTPException(status_code=404, detail="Fayl topilmadi")
    try:
        fpath = os.path.join(static_dir, att.file_url.replace("/static/", "", 1))
        if os.path.exists(fpath):
            os.remove(fpath)
    except Exception as e:
        try:
            crud.log_error(db, str(e), endpoint="api_delete_order_attachment:file_remove")
        except Exception:
            pass
    db.delete(att)
    db.commit()
    return {"status": "ok"}
    import delivery_pdf
    import traceback

    order = crud.get_order(db, order_id, company_id=auth.company_id_of(current_user))
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

    all_dlv = sorted(order.deliveries, key=lambda x: x.delivered_at or datetime.min)

    if ids.strip():
        try:
            wanted = {int(x) for x in ids.split(',') if x.strip()}
        except ValueError:
            raise HTTPException(status_code=400, detail="ids noto'g'ri")
        deliveries = [d for d in all_dlv if d.id in wanted]
    else:
        deliveries = all_dlv

    if not deliveries:
        raise HTTPException(status_code=400, detail="Yuk xati tanlanmagan")

    try:
        pdf_bytes = delivery_pdf.generate_summary_pdf(order, deliveries, db)
    except Exception as e:
        print("Hisob-kitob PDF XATO:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"PDF xato: {str(e)}")

    filename = f"hisob_kitob_{order.order_number}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


@app.delete("/api/deliveries/{delivery_id}")
def api_delete_delivery(delivery_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Yetkazishni o'chirish."""
    # M2: obyekt FAQAT joriy korxonadan topiladi (aks holda 404).
    if not auth.delivery_of_company(db, delivery_id, auth.company_id_of(current_user)):
        raise HTTPException(status_code=404, detail="Yetkazish topilmadi")
    if not crud.delete_delivery(db, delivery_id):
        raise HTTPException(status_code=404, detail="Yetkazish topilmadi")
    return {"status": "ok"}


@app.get("/api/loy-cost")
def api_loy_cost(recipe_id: Optional[int] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """1 kg loyning tan narxi (retsept bo'yicha)."""
    return services.get_loy_cost_per_kg(
        db, recipe_id, company_id=auth.company_id_of(current_user))


@app.get("/api/loy-stock")
def api_loy_stock(recipe_id: Optional[int] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Tayyor loy zaxirasi."""
    from models import Recipe
    # ⚠ 2026-09-21: ikkala so'rov ham korxona bo'yicha cheklanmagan edi.
    # `db.query(Recipe).first()` BUTUN bazadagi birinchi retseptni olardi.
    # O'lchangan: B korxona admini A ning retseptini (`AAA_Rec`) ko'rdi,
    # ustiga `get_or_create_loy_stock` B korxonasida "Tayyor loy (AAA_Rec)"
    # nomli ombor pozitsiyasini YARATIB ham qo'ydi — ya'ni bu faqat o'qish
    # sizishi emas, korxonalararo YOZISH ham edi.
    _cid = auth.company_id_of(current_user)
    _rq = db.query(Recipe).filter(Recipe.company_id == _cid)
    recipe = None
    if recipe_id:
        recipe = _rq.filter(Recipe.id == recipe_id).first()
    if not recipe:
        recipe = _rq.first()
    if not recipe:
        return {"stock_kg": 0, "name": None}

    stock = services.get_or_create_loy_stock(db, recipe, company_id=auth.company_id_of(current_user))
    if not stock:
        return {"stock_kg": 0, "name": None}
    return {
        "stock_kg": float(stock.stock_quantity or 0),
        "name": stock.item_name,
        "recipe": recipe.name.value if hasattr(recipe.name, 'value') else str(recipe.name)
    }


@app.get("/api/orders/{order_id}/planned-loy")
def api_planned_loy(order_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Buyurtmada rejalashtirilgan loy miqdori (qoplama uchun)."""
    order = crud.get_order(db, order_id, company_id=auth.company_id_of(current_user))
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    return {"planned_loy": services._get_planned_loy(order)}


@app.get("/api/dashboard/deliveries")
def api_delivery_stats(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Yetkazish statistikasi."""
    return crud.get_delivery_stats(db, company_id=auth.company_id_of(current_user))


@app.get("/api/dashboard/debts")
def api_debt_stats(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Qarzdorlik statistikasi."""
    return crud.get_debt_stats(db, company_id=auth.company_id_of(current_user))


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    # Xavfsizlik: "standart yopiq" (fail-closed) — agar TELEGRAM_WEBHOOK_SECRET
    # muhit o'zgaruvchisi sozlanmagan bo'lsa, so'rovni RAD ETAMIZ (avval esa
    # sozlanmagan bo'lsa hech qanday tekshiruvsiz qabul qilinar edi). Bu —
    # kelajakda o'zgaruvchi tasodifan o'chib qolsa ham, endpoint himoyasiz
    # qolmasligini kafolatlaydi.
    if not TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook sozlanmagan")
    incoming_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if incoming_secret != TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Noto'g'ri imzo")

    try:
        data = await request.json()
    except:
        return {"ok": True}
    message = data.get("message", {})
    if not message:
        return {"ok": True}
    chat_id = str(message.get("chat", {}).get("id", ""))
    text = (message.get("text") or "").strip().lower()
    if not chat_id:
        return {"ok": True}

    if text == "/start":
        db = SessionLocal()
        try:
            from models import Master
            master, _amb = _master_by_chat_id(db, chat_id)
            if _amb:
                _send_telegram_to(chat_id, _amb)
                return {"ok": True}
            keyboard = _master_bot_keyboard(db, master)
        finally:
            db.close()
        welcome_msg = "Assalomu alaykum! 👋\n\n*PenoDecorPro* bot ga xush kelibsiz!\n\nQuyidagi tugmalardan foydalaning:"
        try:
            url = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN', '')}/sendMessage"
            send_data = _json.dumps({"chat_id": chat_id, "text": welcome_msg, "parse_mode": "Markdown", "reply_markup": keyboard}).encode("utf-8")
            req = urllib.request.Request(url, data=send_data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"Keyboard SMS xatosi: {e}")
        return {"ok": True}

    if text in ["/id", "🪪 mening id raqamim", "mening id raqamim"]:
        reply = f"🪪 *Sizning Telegram ID raqamingiz:*\n\n`{chat_id}`\n\nShu raqamni nusxalab administratorga yuboring — ustalar ro'yxatiga qo'shilasiz va bonuslaringizni kuzatib borishingiz mumkin bo'ladi! 👷"
        _send_telegram_to(chat_id, reply)
        return {"ok": True}

    if text in ["/bonus", "💰 bonuslarim", "bonuslarim", "/balans"]:
        db = SessionLocal()
        try:
            from models import Master
            master, _amb = _master_by_chat_id(db, chat_id)
            if _amb:
                _send_telegram_to(chat_id, _amb)
                return {"ok": True}
            if not master:
                reply = "❌ Siz ustalar ro'yxatida topilmadingiz.\n\nIltimos, administrator bilan bog'laning.\n\n📞 PenoDecorPro — Andijon"
            else:
                # 2026-09-12: har doim ishlaydigan, yillik SOF FOYDADAN
                # hisoblangan keshbek hisoboti (admin panelidagi "Ustalar
                # KPI" bilan bir xil formula). Faol/o'tgan sovg'a
                # davrlaridagi buyurtmalar bu yerdan chiqarib tashlanadi —
                # crud.get_master_yearly_cashback() ichida hisobga olinadi.
                current_year = datetime.now().year
                info = crud.get_master_yearly_cashback(
                    db, master.id, current_year,
                    company_id=getattr(master, "company_id", None))
                reply = f"💰 *Sizning {current_year}-yil keshbegingiz*\n\n👤 {master.name}\n\n🎁 *Hisoblangan keshbek: {int(info['jami_bonus']):,} so'm*\n\n🏗 PenoDecorPro — Andijon"
        except Exception as e:
            reply = "⚠️ Xatolik yuz berdi. Iltimos qayta urinib ko'ring."
        finally:
            db.close()

        db2 = SessionLocal()
        try:
            keyboard = _master_bot_keyboard(db2, master)
        finally:
            db2.close()
        try:
            url = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN', '')}/sendMessage"
            send_data = _json.dumps({"chat_id": chat_id, "text": reply, "parse_mode": "Markdown", "reply_markup": keyboard}).encode("utf-8")
            req = urllib.request.Request(url, data=send_data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            _send_telegram_to(chat_id, reply)
        return {"ok": True}

    if text in ["/sovgalar", "🎁 sovg'alar", "sovg'alar", "sovgalar"]:
        # 2026-09-12: YANGI, davriy (savdo-summasi asosidagi) sovg'a
        # tizimi — faqat admin "davr" ochganda faol. Aniq so'm miqdori
        # ko'rsatilmaydi, faqat qaysi bosqichga yetgani/necha % qolgani
        # (eski show_gifts tizimi bilan bir xil falsafa).
        db = SessionLocal()
        try:
            from models import Master
            master, _amb = _master_by_chat_id(db, chat_id)
            if _amb:
                _send_telegram_to(chat_id, _amb)
                return {"ok": True}
            if not master:
                reply = "❌ Siz ustalar ro'yxatida topilmadingiz.\n\nIltimos, administrator bilan bog'laning.\n\n📞 PenoDecorPro — Andijon"
            else:
                prog = crud.get_master_gift_period_progress(db, master.id)
                if not prog["active"]:
                    reply = "🎁 Hozircha faol sovg'a davri yo'q.\n\n🏗 PenoDecorPro — Andijon"
                else:
                    sales = prog["current_sales"]
                    reply = f"🎁 *Sovg'a davri — joriy holatingiz*\n\n👤 {master.name}\n━━━━━━━━━━━━━━━━━━━\n"
                    prev_threshold = 0.0
                    for t in prog["tiers"]:
                        if t["ready"]:
                            reply += f"✅ {t['gift_name']} — *tayyor, olishga yetdingiz!*\n"
                        else:
                            span = t["threshold_amount"] - prev_threshold
                            progress = max(0.0, sales - prev_threshold)
                            pct = max(0, min(100, round((progress / span) * 100))) if span > 0 else 0
                            reply += f"⬜ {t['gift_name']} — {pct}% (qolgan: {100-pct}%)\n"
                        prev_threshold = t["threshold_amount"]
                    reply += f"━━━━━━━━━━━━━━━━━━━\n\n🏗 PenoDecorPro — Andijon"
        except Exception as e:
            reply = "⚠️ Xatolik yuz berdi. Iltimos qayta urinib ko'ring."
        finally:
            db.close()

        db2 = SessionLocal()
        try:
            keyboard = _master_bot_keyboard(db2, master)
        finally:
            db2.close()
        try:
            url = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN', '')}/sendMessage"
            send_data = _json.dumps({"chat_id": chat_id, "text": reply, "parse_mode": "Markdown", "reply_markup": keyboard}).encode("utf-8")
            req = urllib.request.Request(url, data=send_data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            _send_telegram_to(chat_id, reply)
        return {"ok": True}

    return {"ok": True}


# ============================================================
# KUNLIK AVTOMATIK ZAXIRA NUSXA (Telegram orqali)
# ============================================================

def run_daily_backup():
    """Har kuni bir marta ishga tushadi: butun bazaning zaxira nusxasini
    JSON fayl qilib, Telegram orqali admin(lar)ga yuboradi."""
    import json as _json_mod

    chat_ids_raw = os.environ.get("BACKUP_TELEGRAM_CHAT_ID", "").strip()
    if not chat_ids_raw:
        print("⚠ BACKUP_TELEGRAM_CHAT_ID sozlanmagan — avtomatik backup o'tkazib yuborildi")
        return

    chat_ids = [c.strip() for c in chat_ids_raw.split(",") if c.strip()]

    db = SessionLocal()
    try:
        # M7: kunlik zaxira — PLATFORMA darajasidagi tizim amali (hech qanday
        # tenant so'rovi orqali emas, rejalashtiruvchi tomonidan ishga
        # tushadi) va u platforma egasining o'z Telegram chatiga ketadi,
        # shuning uchun ATAYLAB butun bazani qamraydi. Tenantga hech narsa
        # oshkor qilinmaydi. Parol/PIN hashlari esa endi `export_full_backup`
        # ning o'zida umuman chiqarilmaydi.
        # Faza 3 (2-qadam): kunlik zaxira ATAYLAB platforma darajasida
        # qoladi — u rejalashtiruvchi tomonidan, hech qanday korxona
        # so'rovisiz ishga tushadi va platforma egasining chatiga boradi.
        # Shu sababli u muhit o'zgaruvchilaridagi token/chatni ishlatadi.
        backup_data = crud.export_full_backup(db)
        content = _json_mod.dumps(backup_data, ensure_ascii=False, indent=2).encode("utf-8")

        # Faza 4: Telegram bitta faylda 50 MB gacha ruxsat beradi. Mijozlar
        # ko'paygan sari zaxira kattalashadi va chegaradan oshsa fayl
        # JIMGINA yuborilmay qoladi — ya'ni kunlar davomida zaxirasiz
        # qolish mumkin. Shuning uchun 40 MB dan oshganda ogohlantirish
        # yuboriladi, 49 MB dan oshganda esa fayl o'rniga xabar ketadi.
        _mb = len(content) / (1024 * 1024)
        if _mb >= 49:
            _send_telegram(
                f"⛔ *Kunlik zaxira YUBORILMADI*\n\nFayl hajmi {_mb:.1f} MB — "
                f"Telegram chegarasi (50 MB) dan oshdi.\n\n"
                f"Zaxirani qo'lda yuklab oling: /api/system/backup\n"
                f"Uzoq muddatli yechim kerak (masalan bulutli saqlash).")
            print(f"⛔ Kunlik zaxira yuborilmadi — {_mb:.1f} MB")
            return
        if _mb >= 40:
            _send_telegram(
                f"⚠️ *Zaxira hajmi ogohlantirishi*\n\nBugungi zaxira {_mb:.1f} MB.\n"
                f"Telegram chegarasi 50 MB. Yaqinlashyapti — boshqa saqlash "
                f"usulini rejalashtirish vaqti keldi.")
        filename = f"penodecorpro-backup-{datetime.utcnow().strftime('%Y-%m-%d')}.json"

        total_rows = sum(len(rows) for rows in backup_data["tables"].values())
        caption = f"🗄 Kunlik avtomatik zaxira nusxa\n📅 {datetime.utcnow().strftime('%d.%m.%Y')}\n📊 Jami {total_rows} ta yozuv"

        for chat_id in chat_ids:
            _send_telegram_document(chat_id, content, filename, caption)
    except Exception as e:
        print(f"⚠ Kunlik backup xatosi: {e}")
    finally:
        db.close()


try:
    from apscheduler.schedulers.background import BackgroundScheduler
    _scheduler = BackgroundScheduler(timezone="Asia/Tashkent")
    # Har kuni tunda soat 23:30 da (Toshkent vaqti bilan) ishga tushadi
    _scheduler.add_job(run_daily_backup, "cron", hour=23, minute=30, id="daily_backup")
    _scheduler.start()
    print("✓ Kunlik avtomatik backup rejalashtiruvchisi ishga tushdi (har kuni 23:30, Toshkent vaqti)")
except Exception as e:
    print(f"⚠ Backup rejalashtiruvchisini ishga tushirib bo'lmadi: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
