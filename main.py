"""
PenoDecorPro ERP — Asosiy server
=================================
"""

import os
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import init_database, get_db
import schemas
import crud
import services
import auth
from models import UserRole, Inventory, OrderStatus

import urllib.request
import json as _json

TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_COATING_ID = "8461987934"

def fmt_money(n) -> str:
    """1234567.5 -> '1 234 568'"""
    try:
        return f"{round(float(n)):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def _send_telegram(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("⚠ TELEGRAM_BOT_TOKEN yo'q")
        return
    try:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = _json.dumps({"chat_id": TELEGRAM_COATING_ID, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        print(f"✓ Telegram xabar yuborildi")
    except Exception as e:
        print(f"⚠ Telegram xabar yuborilmadi: {e}")


def _send_telegram_to(chat_id: str, text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("⚠ TELEGRAM_BOT_TOKEN yo'q")
        return
    try:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = _json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        print(f"✓ Telegram xabar yuborildi: {chat_id}")
    except Exception as e:
        print(f"⚠ Mijozga Telegram xabar yuborilmadi: {e}")

def _send_telegram_document(chat_id: str, file_bytes: bytes, filename: str, caption: str = ""):
    """Telegram orqali fayl (masalan zaxira nusxa) yuboradi."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token or not chat_id:
        print("⚠ TELEGRAM_BOT_TOKEN yoki chat_id yo'q — fayl yuborilmadi")
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

        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{filename}"\r\nContent-Type: application/json\r\n\r\n'.encode())
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


init_database()


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

        if migrations:
            with engine.connect() as conn:
                for sql in migrations:
                    try:
                        conn.execute(text(sql))
                        conn.commit()
                        print(f"✓ Migratsiya: {sql[:60]}...")
                    except Exception as e:
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
            except Exception:
                pass

            try:
                conn.execute(text("""
                    UPDATE finished_products SET unit = 'metr'
                    WHERE LOWER(category) = 'panel' AND unit != 'metr'
                """))
                conn.commit()
            except Exception:
                pass

            # Mavjud "Penoplast" nomli pozitsiyalarni belgilaymiz
            try:
                conn.execute(text(
                    "UPDATE inventory SET is_penoplast = TRUE "
                    "WHERE LOWER(item_name) LIKE '%penoplast%' AND is_penoplast = FALSE"
                ))
                conn.commit()
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
            except Exception:
                pass
    except Exception as e:
        print(f"⚠ Migratsiya xatosi: {e}")


_migrate_payment_columns()

from database import SessionLocal
_db = SessionLocal()
try:
    auth.create_default_admin(_db)
finally:
    _db.close()

app = FastAPI(title="PenoDecorPro ERP", description="Ishlab chiqarish boshqaruv tizimi", version="1.0.0", debug=True)

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

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
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user or not auth.verify_password(password, user.password_hash):
        return templates.TemplateResponse(request, "login.html", {"error": "Login yoki parol noto'g'ri!", "username": username})
    token = auth.create_session(user.id)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(key="session_token", value=token, httponly=True, max_age=3600 * 8, samesite="lax")
    return response


@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    if token:
        auth.delete_session(token)
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("session_token")
    return response


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    users = auth.get_all_users(db)
    return templates.TemplateResponse(request, "users.html", {"users": users, "current_user": current_user, "now": datetime.now().strftime("%d.%m.%Y %H:%M"), "active_page": "users"})


@app.post("/api/users")
def api_create_user(data: dict, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    try:
        role = UserRole(data.get("role", "manager"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Noto'g'ri rol")
    user = auth.create_user(db, data["username"], data["password"], role, data.get("full_name", ""))
    return {"id": user.id, "username": user.username, "role": user.role.value}


@app.post("/api/users/{user_id}/toggle")
def api_toggle_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    user = auth.toggle_user_active(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"is_active": user.is_active}


@app.post("/api/users/{user_id}/password")
def api_change_password(user_id: int, data: dict, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    new_pass = data.get("new_password", "")
    if len(new_pass) < 6:
        raise HTTPException(status_code=400, detail="Parol kamida 6 belgi")
    if not auth.change_password(db, user_id, new_pass):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    current_user = auth.get_current_user(request, db)
    if not current_user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "home.html", {"current_user": current_user, "active_page": "home"})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    stats = services.get_dashboard_stats(db)
    return templates.TemplateResponse(request, "dashboard.html", {"stats": stats, "current_user": current_user, "active_page": "dashboard"})


@app.get("/masters")
async def masters_page_redirect():
    """Eski Ustalar sahifasi endi Ustalar KPI / Hodimlar bo'limiga ko'chdi."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/kpi", status_code=307)


@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    items = crud.get_inventory(db)
    kpi = services.get_inventory_kpi(db)
    suppliers = crud.get_suppliers(db)
    return templates.TemplateResponse(request, "inventory.html", {"items": items, "kpi": kpi, "suppliers": suppliers, "current_user": current_user, "active_page": "inventory"})


@app.post("/api/inventory/{item_id}/image")
def api_upload_inventory_image(item_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                                current_user=Depends(auth.admin_only)):
    from models import Inventory
    item = db.query(Inventory).filter(Inventory.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Xomashyo topilmadi")
    url = _save_upload(file, "inventory", ALLOWED_IMAGE_EXT)
    item.image_url = url
    db.commit()
    return {"image_url": url}


@app.get("/api/inventory/kpi")
def api_inventory_kpi(db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return services.get_inventory_kpi(db)


@app.get("/recipes", response_class=HTMLResponse)
async def recipes_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    recipes = crud.get_recipes(db)
    insights = {r.id: crud.get_recipe_insights(db, r.id) for r in recipes}
    return templates.TemplateResponse(request, "recipes.html", {"recipes": recipes, "insights": insights, "current_user": current_user, "active_page": "recipes"})


@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_manager_accountant)):
    projects = crud.get_projects_with_stats(db)
    kpi = crud.get_projects_dashboard_stats(db)
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
    ).filter(Order.status.notin_([OrderStatus.DRAFT, OrderStatus.CANCELLED])).group_by(Order.project_id).all()

    result = {}
    for project_id, total, ready in rows:
        result[project_id] = round((ready / total) * 100) if total else 0
    return result


@app.get("/api/projects/dashboard-stats")
def api_projects_dashboard_stats(db: Session = Depends(get_db), current_user=Depends(auth.admin_manager_accountant)):
    return crud.get_projects_dashboard_stats(db)


@app.post("/api/projects/{project_id}/payment")
def api_add_payment(project_id: int, amount: float, db: Session = Depends(get_db), current_user=Depends(auth.admin_manager_accountant)):
    updated = crud.add_payment(db, project_id, amount)
    if not updated:
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    return {"status": "ok", "total_paid": float(updated.total_paid)}


@app.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    orders = crud.get_orders(db)
    projects = crud.get_projects(db)
    masters = crud.get_masters(db, only_active=True)
    recipes = crud.get_recipes(db)
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
        "current_user": current_user, "active_page": "orders"
    })


@app.post("/api/masters", response_model=schemas.MasterRead)
def api_create_master(master: schemas.MasterCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    new_master = crud.create_master(db, master)
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
    from models import Master
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(status_code=404, detail="Usta topilmadi")
    db.delete(master)
    db.commit()
    return {"status": "ok"}


@app.get("/api/masters", response_model=List[schemas.MasterRead])
def api_get_masters(only_active: bool = False, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return crud.get_masters(db, only_active=only_active)


@app.put("/api/masters/{master_id}", response_model=schemas.MasterRead)
def api_update_master(master_id: int, data: schemas.MasterUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    updated = crud.update_master(db, master_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Usta topilmadi")
    return updated


@app.delete("/api/masters/{master_id}")
def api_delete_master(master_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    if not crud.delete_master(db, master_id):
        raise HTTPException(status_code=404, detail="Usta topilmadi")
    return {"status": "ok"}


@app.post("/api/inventory", response_model=schemas.InventoryRead)
def api_create_item(item: schemas.InventoryCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return crud.add_item(db, item)


@app.get("/api/inventory", response_model=List[schemas.InventoryRead])
def api_get_inventory(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return crud.get_inventory(db)


@app.post("/api/inventory/{item_id}/stock", response_model=schemas.InventoryRead)
def api_update_stock(item_id: int, change: schemas.StockChange, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Qoldiqni narxsiz tuzatish (inventarizatsiya, kamomad va h.k.)."""
    updated = crud.update_stock(db, item_id, change.quantity_change,
                                 performed_by=current_user.full_name or current_user.username,
                                 notes=change.reason)
    if not updated:
        raise HTTPException(status_code=404, detail="Xomashyo topilmadi")
    return updated


@app.put("/api/inventory/{item_id}")
def api_update_inventory_item(item_id: int, data: schemas.InventoryUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Xomashyo ma'lumotlarini yangilash (nomi, min qoldiq, kategoriya va h.k.)."""
    updated = crud.update_item(db, item_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok", "category": updated.category}


@app.post("/api/inventory/{item_id}/purchase")
def api_purchase_stock(item_id: int, data: schemas.StockPurchase, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Ombor kirimi — xarid narxi bilan. O'rtacha vaznli narx hisoblanadi.
    paid_now > 0 bo'lsa — bir vaqtning o'zida xarid HAM yoziladi, HAM to'lov qilinadi,
    qolgan qismi avtomatik qarz sifatida qoladi."""
    who = current_user.full_name or current_user.username

    total_amount = round(data.quantity * data.price_per_unit)
    paid_now = min(data.paid_now, total_amount)   # ortiqcha to'lanmasin
    debt_remains = total_amount - paid_now
    is_credit = debt_remains > 0.01   # server o'zi hisoblaydi — frontenddan kelgan is_credit e'tiborga olinmaydi

    result = crud.purchase_stock(db, item_id, data.quantity, data.price_per_unit,
                                  purchased_by=who, notes=data.notes,
                                  supplier_id=data.supplier_id, is_credit=is_credit,
                                  volume_per_unit=data.volume_per_unit)
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
            created_by=who
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
            paid_by=who
        )

    # Nasiya bo'lsa — kompaniya qarzi oshgani haqida ogohlantirish
    if is_credit and data.supplier_id:
        supplier = crud.get_supplier(db, data.supplier_id)
        if supplier:
            debt_info = crud.get_supplier_debt(db, data.supplier_id)
            all_debt = sum(s["debt"] for s in crud.get_suppliers_with_debt(db))
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
                      db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Xaridlar tarixi."""
    items = crud.get_purchases(db, limit=limit, item_id=item_id)
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
        "notes": p.notes
    } for p in items]


@app.get("/api/inventory/purchase-stats")
def api_purchase_stats(year: Optional[int] = None, month: Optional[int] = None,
                       db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Material bo'yicha xarid statistikasi (oylik)."""
    return crud.get_purchase_stats(db, year=year, month=month)


@app.post("/api/transport-expenses")
def api_create_transport(data: schemas.TransportExpenseCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Kirish transporti xarajatini qo'shish."""
    who = current_user.full_name or current_user.username
    exp = crud.create_transport_expense(db, data, created_by=who)
    return {"status": "ok", "id": exp.id, "amount": float(exp.amount)}


@app.get("/api/transport-expenses")
def api_get_transport(limit: int = 100, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Kirish transporti tarixi."""
    items = crud.get_transport_expenses(db, limit=limit)
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
    if not crud.delete_transport_expense(db, exp_id):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


# ============================================================
# EMPLOYEES — Moslashuvchan hodim to'lovi
# ============================================================

@app.post("/api/employees")
def api_create_employee(data: schemas.EmployeeCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    emp = crud.create_employee(db, data)
    return {"status": "ok", "id": emp.id}


@app.get("/api/employees")
def api_get_employees(only_active: bool = True, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    items = crud.get_employees(db, only_active=only_active)
    return [{
        "id": e.id, "name": e.name, "position": e.position,
        "pay_type": e.pay_type.value,
        "fixed_amount": float(e.fixed_amount or 0),
        "percent_value": float(e.percent_value or 0),
        "per_unit_rate": float(e.per_unit_rate or 0),
        "per_unit_type": e.per_unit_type,
        "is_active": e.is_active,
        "notes": e.notes
    } for e in items]


@app.post("/api/employees/{employee_id}/advance")
def api_create_employee_advance(employee_id: int, amount: float, notes: Optional[str] = None,
                                  adv_date: Optional[str] = None,
                                  db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Hodimga avans (oldindan pul) berilganini qayd etadi.
    adv_date — YYYY-MM-DD formatida, ixtiyoriy (berilmasa — bugungi sana)."""
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
    return {
        "advances": services.get_employee_advances_list(db, employee_id, year, month),
        "total": services.get_employee_advances_total(db, employee_id, year, month)
    }


@app.delete("/api/employees/advance/{advance_id}")
def api_delete_employee_advance(advance_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    if not crud.delete_employee_advance(db, advance_id):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


@app.put("/api/employees/{emp_id}")
def api_update_employee(emp_id: int, data: schemas.EmployeeUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    emp = crud.update_employee(db, emp_id, data)
    if not emp:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


@app.delete("/api/employees/{emp_id}")
def api_delete_employee(emp_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    if not crud.delete_employee(db, emp_id):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


# ============================================================
# MASTER KPI — Yillik KPI (sotuvdan %)
# ============================================================

@app.put("/api/masters/{master_id}/kpi")
def api_update_master_kpi(master_id: int, data: schemas.MasterKpiUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    m = crud.update_master_kpi(db, master_id, data.kpi_percent)
    if not m:
        raise HTTPException(status_code=404, detail="Usta topilmadi")
    return {"status": "ok", "kpi_percent": m.kpi_percent}


@app.get("/api/masters/kpi-report")
def api_masters_kpi_report(year: Optional[int] = None, include_inactive: bool = False,
                            db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    from datetime import datetime
    y = year or datetime.now().year
    return crud.get_masters_kpi_report(db, y, include_inactive=include_inactive)


@app.get("/api/masters/{master_id}/kpi-detail")
def api_master_kpi_detail(master_id: int, year: Optional[int] = None,
                           db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    from datetime import datetime
    y = year or datetime.now().year
    return crud.get_master_kpi_detail(db, master_id, y)


@app.get("/api/transport-stats")
def api_transport_stats(year: Optional[int] = None, month: Optional[int] = None,
                        db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Transport xarajatlari statistikasi (kirish + chiqish)."""
    return crud.get_transport_stats(db, year=year, month=month)


# ============================================================
# SUPPLIERS — Yetkazib beruvchilar va nasiya qarzi
# ============================================================

@app.get("/suppliers", response_class=HTMLResponse)
async def suppliers_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return templates.TemplateResponse(request, "suppliers.html", {"current_user": current_user, "active_page": "suppliers"})


@app.post("/api/suppliers")
def api_create_supplier(data: schemas.SupplierCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    s = crud.create_supplier(db, data)
    return {"status": "ok", "id": s.id}


@app.get("/api/suppliers")
def api_get_suppliers(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return crud.get_suppliers_with_debt(db)


@app.put("/api/suppliers/{supplier_id}")
def api_update_supplier(supplier_id: int, data: schemas.SupplierUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    s = crud.update_supplier(db, supplier_id, data)
    if not s:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


@app.delete("/api/suppliers/{supplier_id}")
def api_delete_supplier(supplier_id: int, force: bool = False, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Yetkazib beruvchini o'chirish. Qarzi bo'lsa force=true kerak."""
    result = crud.delete_supplier(db, supplier_id, force=force)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return {"status": "ok"}


@app.get("/api/suppliers/{supplier_id}/history")
def api_supplier_history(supplier_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None,
                         page: int = 1, page_size: int = 20,
                         db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Yetkazib beruvchi tarixi. start_date/end_date — YYYY-MM-DD formatida (ixtiyoriy).
    page/page_size — xaridlar ro'yxati sahifalanadi (standart: 20 tadan)."""
    from datetime import datetime as dt

    s = crud.get_supplier(db, supplier_id)
    if not s:
        raise HTTPException(status_code=404, detail="Topilmadi")

    sd = dt.strptime(start_date, "%Y-%m-%d") if start_date else None
    ed = dt.strptime(end_date, "%Y-%m-%d") if end_date else None

    history = crud.get_supplier_history(db, supplier_id, start_date=sd, end_date=ed,
                                         page=page, page_size=page_size)
    return {"name": s.name, "phone": s.phone, **history}


@app.put("/api/inventory/purchases/{purchase_id}")
def api_update_purchase(purchase_id: int, data: schemas.PurchaseUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Xarid yozuvini tahrirlash — ombordagi joriy miqdor/narxga ta'sir qilmaydi."""
    updated = crud.update_purchase(db, purchase_id, data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok", "total_amount": float(updated.total_amount)}


@app.delete("/api/inventory/purchases/{purchase_id}")
def api_delete_purchase(purchase_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Xarid yozuvini o'chirish — ombordagi joriy miqdor/narxga ta'sir qilmaydi."""
    if not crud.delete_purchase(db, purchase_id):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


@app.post("/api/suppliers/{supplier_id}/payment")
def api_supplier_payment(supplier_id: int, data: schemas.SupplierPaymentCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    who = current_user.full_name or current_user.username
    data.supplier_id = supplier_id
    p = crud.create_supplier_payment(db, data, paid_by=who)
    debt_info = crud.get_supplier_debt(db, supplier_id)
    return {"status": "ok", "payment_id": p.id, **debt_info}


@app.delete("/api/suppliers/payments/{payment_id}")
def api_delete_supplier_payment(payment_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    if not crud.delete_supplier_payment(db, payment_id):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


@app.get("/api/suppliers/debt-total")
def api_suppliers_debt_total(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Barcha yetkazib beruvchilarga jami qarz — dashboard uchun."""
    suppliers = crud.get_suppliers_with_debt(db)
    total = sum(s["debt"] for s in suppliers)
    return {"total_debt": total, "supplier_count": sum(1 for s in suppliers if s["debt"] > 0)}


@app.get("/api/inventory/purchase-trend")
def api_purchase_trend(months: int = 6, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Oxirgi N oy xarid tendensiyasi."""
    return crud.get_purchase_stats_range(db, months=months)


@app.post("/api/inventory/{item_id}/price")
def api_update_price(item_id: int, data: dict, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    item = db.query(crud.Inventory).filter(crud.Inventory.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Topilmadi")
    item.price_per_unit = data.get("price_per_unit", 0)
    if "volume_per_unit" in data:
        item.volume_per_unit = data.get("volume_per_unit")
    db.commit()
    return {"status": "ok", "price_per_unit": item.price_per_unit}


@app.post("/api/inventory/full-stock-report")
def api_full_stock_report(db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    from models import Inventory as Inv
    items = db.query(Inv).order_by(Inv.item_name).all()
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
def api_low_stock_alert(db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    low_items = crud.get_low_stock_items(db)
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


@app.delete("/api/inventory/{item_id}")
def api_delete_item(item_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    result = crud.delete_item(db, item_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return {"status": "ok", "soft": result["soft"], "message": result["message"]}


@app.post("/api/recipes", response_model=schemas.RecipeRead)
def api_create_recipe(recipe: schemas.RecipeCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return crud.create_recipe(db, recipe)


@app.put("/api/recipes/{recipe_id}", response_model=schemas.RecipeRead)
def api_update_recipe(recipe_id: int, data: schemas.RecipeCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    recipe = crud.update_recipe(db, recipe_id, data)
    if not recipe:
        raise HTTPException(status_code=404, detail="Retsept topilmadi")
    return recipe


@app.post("/api/recipes/{recipe_id}/image")
def api_upload_recipe_image(recipe_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                             current_user=Depends(auth.admin_only)):
    from models import Recipe
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Retsept topilmadi")
    url = _save_upload(file, "recipes", ALLOWED_IMAGE_EXT)
    recipe.image_url = url
    db.commit()
    return {"image_url": url}


@app.delete("/api/recipes/{recipe_id}")
def api_delete_recipe(recipe_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    from models import Recipe
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Retsept topilmadi")
    db.delete(recipe)
    db.commit()
    return {"status": "ok"}


@app.get("/api/recipes", response_model=List[schemas.RecipeRead])
def api_get_recipes(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return crud.get_recipes(db)


@app.post("/api/projects", response_model=schemas.ProjectRead)
def api_create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return crud.create_project(db, project)


@app.get("/api/projects", response_model=List[schemas.ProjectRead])
def api_get_projects(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return crud.get_projects(db)


@app.put("/api/projects/{project_id}", response_model=schemas.ProjectRead)
def api_update_project(project_id: int, project: schemas.ProjectUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    updated = crud.update_project(db, project_id, project)
    if not updated:
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    return updated


@app.delete("/api/projects/{project_id}")
def api_delete_project(project_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    if not crud.delete_project(db, project_id):
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    return {"status": "ok"}


@app.post("/api/orders/coating-notify-new")
def api_coating_notify_with_loy(order_id: int, loy_kg: float, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    pass


@app.post("/api/orders", response_model=schemas.OrderRead)
def api_create_order(order: schemas.OrderCreate, loy_kg: Optional[float] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    check = services.check_inventory_for_order(db, order)
    if not check["enough"]:
        raise HTTPException(status_code=400, detail={"success": False, "message": "Xomashyo yetishmayapti!", "shortages": check["shortages"]})
    # Termopanel (bazalt) uchun ham tekshiramiz
    tcheck = services.check_termopanel_for_order(db, order)
    if not tcheck["enough"]:
        raise HTTPException(status_code=400, detail={"success": False, "message": "Bazalt xomashyosi yetishmayapti!", "shortages": tcheck["shortages"]})
    # Tayyor mahsulot yetadimi
    fcheck = crud.check_finished_for_order(db, order.items)
    if not fcheck["enough"]:
        raise HTTPException(status_code=400, detail={"success": False, "message": "Tayyor mahsulot yetishmayapti!", "shortages": fcheck["shortages"]})
    new_order = crud.create_order(db, order)
    services.deduct_inventory_for_order(db, new_order)
    services.deduct_termopanel_for_order(db, new_order, order)
    low_items = crud.get_low_stock_items(db)
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
    return crud.get_orders(db, project_id=project_id)


@app.get("/api/orders/{order_id}")
def api_get_order(order_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    order = crud.get_order(db, order_id)
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
        "closed_at": order.closed_at.isoformat() if order.closed_at else None,
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
            "order_qty_normalized": i.order_qty_normalized,
            "delivery_unit": i.delivery_unit,
            "price_per_unit_final": round(float(i.total_price or 0) / i.order_qty_normalized) if i.order_qty_normalized else 0,
            "cost_price_per_unit": services.get_order_item_unit_cost(db, order, i)
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
                     db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Buyurtmani tahrirlash — ombor faqat FARQ bo'yicha to'g'rilanadi."""
    result = crud.update_order_full(db, order_id, order)
    if not result["success"]:
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
        ord_obj = crud.get_order(db, order_id)
        msg = (f"⚠️ *Ombor ogohlantirishlari!*\n\n*{ord_obj.order_number}* tahrirlangandan keyin:\n\n"
               + "━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
               + "\n━━━━━━━━━━━━━━━━━━━\n\nZudlik bilan buyurtma bering! 🚨\n\n🏗 *PenoDecorPro* — Andijon")
        _send_telegram(msg)

    return result


@app.post("/api/orders/{order_id}/termopanel-loy")
def api_complete_termopanel_loy(order_id: int, actual_loy_kg: float, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Termopanel buyurtmasi yakunlanganda — reja/haqiqiy loy farqini to'g'irlaydi."""
    result = crud.complete_termopanel_loy(db, order_id, actual_loy_kg)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.put("/api/orders/{order_id}/loy")
def api_update_loy(order_id: int, loy_kg: float, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Loy rejasini o'zgartirish."""
    result = crud.update_order_loy(db, order_id, loy_kg)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.post("/api/orders/{order_id}/coating-notify")
def api_coating_notify(order_id: int, loy_kg: float, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Rejalashtirilgan loy: xomashyoni ayiradi + qoplamachiga xabar."""
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

    inventory_log = []

    if loy_kg > 0:
        # Rejani notes ga yozamiz
        services._set_planned_loy(order, loy_kg)
        db.commit()
        db.refresh(order)

        # Qoralama bo'lmasa — xomashyoni darhol ayiramiz
        if order.status != OrderStatus.DRAFT:
            inventory_log = services.deduct_loy_ingredients(db, order, loy_kg)

            msg = (
                f"🏗 *PenoDecorPro — Yangi buyurtma*\n\n"
                f"📋 Buyurtma: *{order.order_number}*\n"
                f"👤 Mijoz: {order.project.client_name if order.project else '—'}\n"
                f"🧱 Loy tayyorlang: *{int(loy_kg)} kg*\n\n"
                f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            _send_telegram(msg)

    return {"status": "ok", "inventory_log": inventory_log}


@app.post("/api/orders/{order_id}/ready")
def api_mark_order_ready(order_id: int, loy_kg: Optional[float] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    result = services.complete_order(db, order_id, loy_kg)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    order = crud.get_order(db, order_id)
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
                except:
                    pass
            if tg_id and tg_id.lstrip('-').isdigit():
                client_msg = (
                    f"✅ *Buyurtmangiz tayyor!*\n\n"
                    f"📋 Buyurtma: *{order.order_number}*\n"
                    f"👤 Mijoz: {order.project.client_name}\n"
                    f"🏗 PenoDecorPro — Andijon\n\n"
                    f"Buyurtmangizni olishingiz mumkin!\n"
                    f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )
                _send_telegram_to(tg_id, client_msg)
    return result


@app.post("/api/orders/mark-all-ready")
def api_mark_all_ready(loy_kg: Optional[float] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    from models import Order, OrderStatus
    pending = db.query(Order).filter(Order.status != OrderStatus.READY).all()
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
    order = crud.get_order(db, order_id)
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

    if can_return:
        if has_delivery:
            # Qisman topshirilgan — faqat qolgan qismi qaytadi
            log.extend(services.return_inventory_for_order_partial(db, order))
        else:
            # Hech narsa topshirilmagan — hammasi qaytadi
            log.extend(services.return_inventory_for_order(db, order))
            log.extend(services.return_termopanel_for_order(db, order))

        # Tayyor mahsulotlar qaytadi (faqat hech narsa topshirilmagan bo'lsa)
        if not has_delivery:
            log.extend(crud._return_finished_for_order(db, order))

        # Loy ingredientlari — reja/haqiqiy solishtirib qaytariladi.
        # actual_loy_kg berilgan bo'lsa (hodim "qancha ishlatildi" deb yozgan) —
        # ortgan qismi aniq qaytadi. Berilmagan va hech narsa topshirilmagan
        # bo'lsa — eski xulq: to'liq rejalashtirilgan miqdor qaytadi.
        planned_loy = services._get_planned_loy(order) + crud.get_termopanel_planned_loy(order)

        if actual_loy_kg is not None:
            diff = planned_loy - float(actual_loy_kg)
            if diff > 0.01:
                log.extend(services.return_loy_ingredients(db, order, diff))
            elif diff < -0.01:
                log.extend(services.deduct_loy_ingredients(db, order, abs(diff)))
        elif not has_delivery and planned_loy > 0:
            log.extend(services.return_loy_ingredients(db, order, planned_loy))

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
    should_soft_delete = (
        has_delivery
        or order.status in (OrderStatus.READY, OrderStatus.DELIVERED)
        or float(order.paid_amount or 0) > 0
    )

    if not crud.delete_order(db, order_id, soft=should_soft_delete):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

    if log:
        print(f"✓ {order_num} o'chirildi. Omborga qaytdi: {log}")
    else:
        print(f"✓ {order_num} o'chirildi. Xomashyo qaytmadi: {reason}")

    return {"status": "ok", "inventory_log": log, "returned": bool(log), "reason": reason,
            "soft_deleted": should_soft_delete}


@app.delete("/api/order-items/{item_id}")
def api_delete_order_item(item_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    if not crud.delete_order_item(db, item_id):
        raise HTTPException(status_code=404, detail="Detal topilmadi")
    return {"status": "ok"}


@app.put("/api/order-items/{item_id}")
def api_update_order_item(item_id: int, data: dict, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    updated = crud.update_order_item(db, item_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Detal topilmadi")
    return {"status": "ok"}


@app.get("/api/dashboard/stats")
def api_dashboard_stats(db: Session = Depends(get_db), current_user=Depends(auth.admin_manager_accountant)):
    return services.get_dashboard_stats(db)


@app.get("/api/dashboard/today")
def api_dashboard_today(db: Session = Depends(get_db), current_user=Depends(auth.admin_manager_accountant)):
    return services.get_today_stats(db)


@app.get("/api/dashboard/charts")
def api_dashboard_charts(db: Session = Depends(get_db), current_user=Depends(auth.admin_manager_accountant)):
    return services.get_chart_data(db)


@app.get("/api/warnings/low-stock")
def api_low_stock(db: Session = Depends(get_db)):
    return {"warnings": services.get_low_stock_warnings(db)}


@app.get("/api/notifications")
def api_notifications(db: Session = Depends(get_db), current_user=Depends(auth.require_login)):
    return services.get_notifications(db)


@app.get("/api/dashboard/today-tasks")
def api_today_tasks(db: Session = Depends(get_db), current_user=Depends(auth.require_login)):
    return services.get_today_tasks(db)


@app.get("/api/dashboard/production-periods")
def api_production_periods(db: Session = Depends(get_db), current_user=Depends(auth.admin_manager_accountant)):
    return services.get_production_period_stats(db)


@app.get("/api/inventory/movements")
def api_inventory_movements(item_id: Optional[int] = None, movement_type: Optional[str] = None,
                             order_id: Optional[int] = None, limit: int = 100, db: Session = Depends(get_db)):
    """Ombor harakatlari jurnali — kirim va chiqimlar tarixi (faqat o'qish)."""
    from models import InventoryMovement
    q = db.query(InventoryMovement)
    if item_id:
        q = q.filter(InventoryMovement.inventory_id == item_id)
    if movement_type in ("in", "out"):
        q = q.filter(InventoryMovement.movement_type == movement_type)
    if order_id:
        q = q.filter(InventoryMovement.order_id == order_id)
    rows = q.order_by(InventoryMovement.created_at.desc()).limit(limit).all()
    return [schemas.InventoryMovementRead.model_validate(r) for r in rows]


@app.get("/api/projects/{project_id}/detail-stats")
def api_project_detail_stats(project_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_manager_accountant)):
    """Loyiha detali uchun qo'shimcha ko'rsatkichlar — faqat o'qish, mavjud
    calculate_order_profit() dan foydalanadi, hech narsani o'zgartirmaydi."""
    import services
    from models import Order, OrderStatus

    orders = db.query(Order).filter(Order.project_id == project_id).all()
    status_counts = {}
    total_profit = 0.0
    for o in orders:
        st = o.status.value
        status_counts[st] = status_counts.get(st, 0) + 1
        if o.status == OrderStatus.READY:
            try:
                total_profit += float(services.calculate_order_profit(db, o.id).get("foyda", 0))
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
async def debts_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    from models import Project
    all_projects = db.query(Project).filter(Project.total_budget > Project.total_paid).order_by(Project.total_budget.desc()).all()
    debts = [p for p in all_projects if float(p.total_budget or 0) - float(p.total_paid or 0) > 0]
    total_debt = sum(float(p.total_budget or 0) - float(p.total_paid or 0) for p in debts)
    total_paid = sum(float(p.total_paid or 0) for p in debts)
    total_budget = sum(float(p.total_budget or 0) for p in debts)
    return templates.TemplateResponse(request, "debts.html", {"debts": debts, "total_debt": total_debt, "total_paid": total_paid, "total_budget": total_budget, "current_user": current_user, "active_page": "debts"})


@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return templates.TemplateResponse(request, "reports.html", {"current_user": current_user, "active_page": "reports"})


@app.get("/api/reports/top-products")
def api_reports_top_products(days: int = 90, limit: int = 15, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return services.get_top_products_report(db, days=days, limit=limit)


@app.get("/api/reports/top-materials")
def api_reports_top_materials(days: int = 90, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return services.get_top_materials_report(db, days=days)


@app.get("/api/reports/top-customers")
def api_reports_top_customers(days: int = 90, limit: int = 10, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return services.get_top_customers_report(db, days=days, limit=limit)


@app.get("/api/reports/top-suppliers")
def api_reports_top_suppliers(days: int = 90, limit: int = 10, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return services.get_top_suppliers_report(db, days=days, limit=limit)


@app.get("/api/reports/comparison")
def api_reports_comparison(year: int, month: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return services.get_monthly_comparison(db, year, month)


@app.get("/api/reports/forecast")
def api_reports_forecast(year: int, month: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return services.get_simple_forecast(db, year, month)


@app.get("/api/reports/alerts")
def api_reports_alerts(db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return services.get_business_alerts(db)


@app.get("/api/reports/business-health")
def api_reports_business_health(db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return services.get_business_health(db)


@app.get("/finance", response_class=HTMLResponse)
async def finance_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return templates.TemplateResponse(request, "finance.html", {"current_user": current_user, "active_page": "finance"})


@app.get("/api/finance/report")
def api_finance_report(year: int, month: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return services.get_monthly_report(db, year, month)


@app.get("/api/finance/daily")
def api_finance_daily(target_date: Optional[str] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Bitta kun uchun moliyaviy ko'rinish (savdo/foyda/tan narx + xarajatlar).
    target_date berilmasa — bugungi kun olinadi. Format: YYYY-MM-DD"""
    from datetime import date as date_cls
    if target_date:
        d = date_cls.fromisoformat(target_date)
    else:
        d = date_cls.today()
    return services.get_daily_finance_summary(db, d)


@app.get("/api/finance/history")
def api_finance_history(months: int = 12, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return services.get_finance_history(db, months)


@app.post("/api/finance/transactions")
def api_create_expense_transaction(data: schemas.ExpenseTransactionCreate, db: Session = Depends(get_db),
                                    current_user=Depends(auth.admin_only)):
    tx = crud.create_expense_transaction(db, data.model_dump(), performed_by=current_user.full_name or current_user.username, source="manual")
    return schemas.ExpenseTransactionRead.model_validate(tx)


@app.get("/api/finance/transactions")
def api_list_expense_transactions(year: Optional[int] = None, month: Optional[int] = None,
                                   day: Optional[int] = None, category: Optional[str] = None,
                                   db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    rows = crud.get_expense_transactions(db, year=year, month=month, day=day, category=category)
    return [schemas.ExpenseTransactionRead.model_validate(r) for r in rows]


@app.delete("/api/finance/transactions/{tx_id}")
def api_delete_expense_transaction(tx_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    ok = crud.delete_expense_transaction(db, tx_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Tranzaksiya topilmadi")
    return {"status": "ok"}


@app.post("/api/finance/expense")
def api_save_expense(year: int, month: int, data: dict, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    services.save_monthly_expense(db, year, month, data, performed_by=current_user.full_name or current_user.username)
    return {"status": "ok"}


@app.get("/api/orders/{order_id}/profit")
def api_order_profit(order_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    return services.calculate_order_profit(db, order_id)


@app.get("/api/orders/{order_id}/pdf")
def api_order_pdf(order_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import Response
    import pdf_service
    import traceback
    order = crud.get_order(db, order_id)
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
async def returns_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    returns = crud.get_return_items(db)
    orders  = crud.get_orders(db)
    projects = crud.get_projects(db)
    return templates.TemplateResponse(request, "returns.html", {
        "returns": returns, "orders": orders, "projects": projects,
        "current_user": current_user
    })


@app.get("/api/projects/{project_id}/items")
def api_get_project_items(project_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Loyihadagi barcha buyurtmalar detallari — brak yozish uchun (narxsiz)."""
    from models import Order, OrderStatus

    orders = db.query(Order).filter(
        Order.project_id == project_id,
        Order.status.notin_([OrderStatus.DRAFT, OrderStatus.CANCELLED])
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
def api_create_return(data: schemas.ReturnItemCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return crud.create_return_item(db, data)


@app.get("/api/returns")
def api_get_returns(order_id: Optional[int] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return crud.get_return_items(db, order_id=order_id)


@app.get("/api/returns/stats")
def api_return_stats(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return crud.get_return_stats(db)


@app.post("/api/returns/{return_id}/refund")
def api_mark_refunded(return_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    who = current_user.full_name or current_user.username
    item = crud.mark_refunded(db, return_id, refunded_by=who)
    if not item:
        raise HTTPException(status_code=404, detail="Qaytarish topilmadi")
    return {"status": "ok", "is_refunded": item.is_refunded}


@app.delete("/api/returns/{return_id}")
def api_delete_return(return_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    if not crud.delete_return_item(db, return_id):
        raise HTTPException(status_code=404, detail="Qaytarish topilmadi")
    return {"status": "ok"}


# ============================================================
# PAYMENTS — To'lovlar API
# ============================================================

@app.post("/api/payments")
def api_create_payment(data: schemas.PaymentCreate, write_off_remainder: bool = False, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Yangi to'lov qo'shish.
    write_off_remainder=true bo'lsa — to'lovdan keyin qolgan (kichik) qarz
    CHEGIRMA sifatida yozib yuboriladi (jami summadan ham ayiriladi —
    shuning uchun FOYDA hisobotida ham to'g'ri, kamroq ko'rsatiladi)."""
    if not data.received_by:
        data.received_by = current_user.full_name or current_user.username
    try:
        payment = crud.create_payment(db, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    order = crud.get_order(db, data.order_id)

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
        "paid_amount": order.paid_amount,
        "debt_amount": order.debt_amount,
        "payment_status": order.payment_status.value,
        "is_archived": order.is_archived,
        "write_off": write_off_info
    }


@app.get("/api/payments")
def api_get_payments(order_id: Optional[int] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """To'lovlar ro'yxati."""
    payments = crud.get_payments(db, order_id=order_id)
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
def api_delete_payment(payment_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """To'lovni o'chirish."""
    if not crud.delete_payment(db, payment_id):
        raise HTTPException(status_code=404, detail="To'lov topilmadi")
    return {"status": "ok"}


@app.put("/api/orders/{order_id}/agreed-amount")
def api_update_agreed_amount(order_id: int, data: schemas.OrderAgreedUpdate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Kelishilgan summani (chegirmadan keyingi narx) yangilash."""
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
def api_set_default_penoplast(item_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Asosiy plotnost qilib belgilash."""
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
    result = crud.activate_draft_order(db, order_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


# ============================================================
# FINISHED PRODUCTS — Tayyor mahsulotlar ombori
# ============================================================

@app.get("/finished", response_class=HTMLResponse)
async def finished_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Tayyor mahsulotlar sahifasi."""
    items = crud.get_finished_products(db)
    penoplasts = services.get_penoplast_list(db)
    default_p = services.get_default_penoplast(db)
    recipes = crud.get_recipes(db)
    stats = crud.get_finished_stats(db)
    return templates.TemplateResponse(request, "finished.html", {
        "items": items, "penoplasts": penoplasts,
        "default_penoplast_id": default_p.id if default_p else None,
        "recipes": recipes, "stats": stats,
        "current_user": current_user, "active_page": "finished"
    })


@app.get("/api/system/telegram-debug")
def api_telegram_debug(current_user=Depends(auth.admin_only)):
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


@app.post("/api/system/backup/send-now")
def api_backup_send_now(current_user=Depends(auth.admin_only)):
    """Kunlik avtomatik backup vazifasini HOZIROQ, qo'lda ishga tushiradi
    (23:30 ni kutmasdan, Telegram ulanishini sinab ko'rish uchun)."""
    run_daily_backup()
    return {"status": "ok", "message": "Backup yuborildi (agar BACKUP_TELEGRAM_CHAT_ID sozlangan bo'lsa)"}


@app.get("/api/system/backup")
def api_system_backup(db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Butun bazaning to'liq zaxira nusxasini JSON fayl sifatida yuklab beradi."""
    import json
    from fastapi.responses import Response

    backup_data = crud.export_full_backup(db)
    filename = f"penodecorpro-backup-{datetime.utcnow().strftime('%Y-%m-%d_%H-%M')}.json"
    content = json.dumps(backup_data, ensure_ascii=False, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/api/system/factory-reset")
def api_factory_reset(confirm: str = "", db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """DIQQAT: QAYTARIB BO'LMAYDIGAN AMAL!
    Foydalanuvchilardan (login) TASHQARI — BARCHA ma'lumotni butunlay o'chiradi:
    buyurtmalar, ombor, retseptlar, ustalar, yetkazib beruvchilar, loyihalar va h.k.
    Xavfsizlik uchun — aniq tasdiqlash so'zisiz ishlamaydi."""
    REQUIRED_PHRASE = "HAMMASINI-OCHIR"
    if confirm != REQUIRED_PHRASE:
        raise HTTPException(
            status_code=400,
            detail=f"Xavfsizlik uchun, so'rovga ?confirm={REQUIRED_PHRASE} qo'shing. "
                   "DIQQAT: bu amal QAYTARIB BO'LMAYDI!"
        )
    result = crud.factory_reset_all_data(db)
    return {"status": "ok", "message": "Barcha ma'lumot tozalandi (Foydalanuvchilardan tashqari)", "deleted": result}


@app.get("/kpi", response_class=HTMLResponse)
async def kpi_page(request: Request, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Ustalar yillik KPI va moslashuvchan hodim to'lovi sahifasi."""
    return templates.TemplateResponse(request, "kpi.html", {
        "current_user": current_user, "active_page": "kpi"
    })


@app.get("/api/finished")
def api_get_finished(source: Optional[str] = None, only_available: bool = False,
                     db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Tayyor mahsulotlar ro'yxati."""
    items = crud.get_finished_products(db, source=source, only_available=only_available)
    return [{
        "id": fp.id,
        "name": fp.name,
        "category": fp.category,
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
        "production_status": fp.production_status.value if fp.production_status else None,
        "recipe_id": fp.recipe_id,
        "created_at": fp.created_at.isoformat() if fp.created_at else None,
        "created_by": fp.created_by,
        "notes": fp.notes,
        "image_url": fp.image_url,
        "total_value": round(float(fp.quantity or 0) * float(fp.unit_price or 0))
    } for fp in items]


@app.post("/api/finished/{fp_id}/image")
def api_upload_finished_image(fp_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                               current_user=Depends(auth.admin_or_manager)):
    from models import FinishedProduct
    fp = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()
    if not fp:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
    url = _save_upload(file, "finished", ALLOWED_IMAGE_EXT)
    fp.image_url = url
    db.commit()
    return {"image_url": url}


@app.get("/api/finished/stats")
def api_finished_stats(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    return crud.get_finished_stats(db)


@app.get("/api/finished/search")
def api_search_finished(q: str = "", db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Nom bo'yicha qidirish — buyurtmada taklif uchun."""
    return {"items": crud.search_finished_products(db, q)}


@app.post("/api/finished/produce")
def api_produce(data: schemas.ProduceCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Tayyor mahsulot ishlab chiqarish."""
    who = current_user.full_name or current_user.username
    result = crud.produce_finished_product(db, data, created_by=who)
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


@app.post("/api/finished/produce-termopanel")
def api_produce_termopanel(data: schemas.TermopanelProduceCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Bazalt asosidagi termopanel ishlab chiqarish (kvadrat metr bo'yicha)."""
    who = current_user.full_name or current_user.username
    result = crud.produce_termopanel(db, data, created_by=who)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)

    low_items = crud.get_low_stock_items(db)
    if low_items:
        lines = []
        for item in low_items:
            qty = float(item.stock_quantity)
            min_q = float(item.min_stock)
            emoji = "🔴" if qty <= min_q * 0.5 else "🟡"
            lines.append(f"{emoji} {item.item_name}: {qty:.1f} {item.unit} qoldi (min: {min_q:.0f})")
        msg = ("⚠️ *Ombor ogohlantirishlari!*\n\nTermopanel ishlab chiqarilgandan keyin:\n\n"
               + "━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
               + "\n━━━━━━━━━━━━━━━━━━━\n\n🏗 *PenoDecorPro* — Andijon")
        _send_telegram(msg)

    return result


@app.post("/api/finished/{fp_id}/complete")
def api_complete_production(fp_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Mahsulotni 'Tayyor' deb belgilash — sotuvga tayyor."""
    result = crud.complete_production(db, fp_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.get("/api/finished/{fp_id}/profit")
def api_finished_profit(fp_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_only)):
    """Tayyor mahsulot foydasi (faqat admin)."""
    result = crud.get_finished_profit(db, fp_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.post("/api/finished/{fp_id}/add")
def api_add_production(fp_id: int, data: schemas.StockAdjust,
                       db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Tayyor mahsulotga miqdor qo'shish — xomashyo proporsional yechiladi."""
    result = crud.add_to_production(db, fp_id, data.quantity)
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
                          db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Tayyor mahsulot miqdorini kamaytirish (brak/singan) — xomashyo qaytmaydi."""
    result = crud.reduce_production(db, fp_id, data.quantity, data.reason)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.put("/api/finished/{fp_id}")
def api_update_finished(fp_id: int, data: schemas.FinishedProductUpdate,
                        db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Tayyor mahsulotni tahrirlash."""
    fp = crud.update_finished_product(db, fp_id, data.model_dump(exclude_unset=True))
    if not fp:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok", "quantity": float(fp.quantity), "unit_price": float(fp.unit_price or 0)}


@app.delete("/api/finished/{fp_id}")
def api_delete_finished(fp_id: int, return_to_stock: bool = False,
                        db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Tayyor mahsulotni o'chirish."""
    if not crud.delete_finished_product(db, fp_id, return_to_stock=return_to_stock):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


# ============================================================
# DELIVERIES — Yetkazishlar
# ============================================================

@app.get("/api/orders/{order_id}/delivery-status")
def api_delivery_status(order_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Buyurtmaning yetkazish holati."""
    result = crud.get_delivery_status(db, order_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/api/deliveries")
def api_create_delivery(data: schemas.DeliveryCreate, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Yangi yetkazish."""
    who = current_user.full_name or current_user.username
    result = crud.create_delivery(db, data, delivered_by=who)
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

    return result


@app.get("/api/deliveries/{delivery_id}/pdf")
def api_delivery_pdf(delivery_id: int, db: Session = Depends(get_db)):
    """Yetkazish nakladnoyi (PDF)."""
    from fastapi.responses import Response
    import delivery_pdf
    import traceback

    d = crud.get_delivery(db, delivery_id)
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
def api_summary_pdf(order_id: int, ids: str = "", db: Session = Depends(get_db)):
    """Hisob-kitob varaqasi — tanlangan nakladnoylar bo'yicha.
    ids — vergul bilan ajratilgan delivery ID lar: '3,5,7'. Bo'sh bo'lsa — hammasi."""
    from fastapi.responses import Response


# ============================================================
# MAHSULOT RASMI VA BUYURTMA FAYLLARI (faqat qo'shimcha — hisob-kitobga ta'sir qilmaydi)
# ============================================================

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_FILE_EXT = ALLOWED_IMAGE_EXT | {".pdf"}
MAX_UPLOAD_SIZE = 8 * 1024 * 1024  # 8 MB


def _save_upload(file: UploadFile, subfolder: str, allowed_ext: set) -> str:
    import uuid
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"Ruxsat etilmagan fayl turi: {ext}")
    contents = file.file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="Fayl hajmi 8 MB dan katta bo'lmasin")
    folder = os.path.join(static_dir, "uploads", subfolder)
    os.makedirs(folder, exist_ok=True)
    fname = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(folder, fname), "wb") as f:
        f.write(contents)
    return f"/static/uploads/{subfolder}/{fname}"


@app.post("/api/order-items/{item_id}/image")
def api_upload_order_item_image(item_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                                 current_user=Depends(auth.require_login)):
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
                                 current_user=Depends(auth.require_login)):
    from models import OrderItem
    item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Detal topilmadi")
    item.image_url = None
    db.commit()
    return {"status": "ok"}


@app.post("/api/orders/{order_id}/attachments")
def api_upload_order_attachment(order_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                                 current_user=Depends(auth.require_login)):
    from models import OrderAttachment, Order
    order = db.query(Order).filter(Order.id == order_id).first()
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
def api_list_order_attachments(order_id: int, db: Session = Depends(get_db)):
    from models import OrderAttachment
    atts = db.query(OrderAttachment).filter(OrderAttachment.order_id == order_id).order_by(OrderAttachment.uploaded_at.desc()).all()
    return [schemas.OrderAttachmentRead.model_validate(a) for a in atts]


@app.delete("/api/orders/attachments/{attachment_id}")
def api_delete_order_attachment(attachment_id: int, db: Session = Depends(get_db),
                                 current_user=Depends(auth.require_login)):
    from models import OrderAttachment
    att = db.query(OrderAttachment).filter(OrderAttachment.id == attachment_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Fayl topilmadi")
    try:
        fpath = os.path.join(static_dir, att.file_url.replace("/static/", "", 1))
        if os.path.exists(fpath):
            os.remove(fpath)
    except Exception:
        pass
    db.delete(att)
    db.commit()
    return {"status": "ok"}
    import delivery_pdf
    import traceback

    order = crud.get_order(db, order_id)
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
    if not crud.delete_delivery(db, delivery_id):
        raise HTTPException(status_code=404, detail="Yetkazish topilmadi")
    return {"status": "ok"}


@app.get("/api/loy-cost")
def api_loy_cost(recipe_id: Optional[int] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """1 kg loyning tan narxi (retsept bo'yicha)."""
    return services.get_loy_cost_per_kg(db, recipe_id)


@app.get("/api/loy-stock")
def api_loy_stock(recipe_id: Optional[int] = None, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Tayyor loy zaxirasi."""
    from models import Recipe
    recipe = None
    if recipe_id:
        recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        recipe = db.query(Recipe).first()
    if not recipe:
        return {"stock_kg": 0, "name": None}

    stock = services.get_or_create_loy_stock(db, recipe)
    if not stock:
        return {"stock_kg": 0, "name": None}
    return {
        "stock_kg": float(stock.stock_quantity or 0),
        "name": stock.item_name,
        "recipe": recipe.name.value if hasattr(recipe.name, 'value') else str(recipe.name)
    }


@app.get("/api/orders/{order_id}/planned-loy")
def api_planned_loy(order_id: int, db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Buyurtmada rejalashtirilgan loy miqdori — oddiy detallar + termopanel (bazalt) birga."""
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    order_planned = services._get_planned_loy(order)
    termo_planned = crud.get_termopanel_planned_loy(order)
    return {"planned_loy": order_planned + termo_planned}


@app.get("/api/dashboard/deliveries")
def api_delivery_stats(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Yetkazish statistikasi."""
    return crud.get_delivery_stats(db)


@app.get("/api/dashboard/debts")
def api_debt_stats(db: Session = Depends(get_db), current_user=Depends(auth.admin_or_manager)):
    """Qarzdorlik statistikasi."""
    return crud.get_debt_stats(db)


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
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
        keyboard = {"keyboard": [[{"text": "💰 Bonuslarim"}, {"text": "🪪 Mening ID raqamim"}]], "resize_keyboard": True, "persistent": True}
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
            from models import Master, Order, OrderStatus
            master = db.query(Master).filter(Master.telegram_id == chat_id, Master.is_active == True).first()
            if not master:
                reply = "❌ Siz ustalar ro'yxatida topilmadingiz.\n\nIltimos, administrator bilan bog'laning.\n\n📞 PenoDecorPro — Andijon"
            else:
                orders = db.query(Order).filter(Order.master_id == master.id, Order.status == OrderStatus.READY).order_by(Order.completed_at.desc()).all()
                jami_bonus = 0.0
                buyurtmalar_text = ""
                for i, o in enumerate(orders[:10]):
                    sotuv = float(o.total_amount or 0)
                    bonus = sotuv * float(master.cashback_percent) / 100
                    jami_bonus += bonus
                    buyurtmalar_text += f"• {o.order_number} — {int(sotuv):,} so'm → *{int(bonus):,} so'm* ✅\n"
                faol = db.query(Order).filter(Order.master_id == master.id, Order.status != OrderStatus.READY).count()
                reply = f"📊 *Sizning bonuslaringiz*\n\n👤 {master.name}\n🎯 Bonus foizi: *{master.cashback_percent}%*\n\n━━━━━━━━━━━━━━━━━━━\n"
                if buyurtmalar_text:
                    reply += f"📋 *Oxirgi buyurtmalar:*\n{buyurtmalar_text}\n"
                if faol > 0:
                    reply += f"⏳ Jarayondagi buyurtmalar: *{faol} ta*\n\n"
                reply += f"━━━━━━━━━━━━━━━━━━━\n💰 *Jami bonus: {int(jami_bonus):,} so'm*\n\n🏗 PenoDecorPro — Andijon"
        except Exception as e:
            reply = "⚠️ Xatolik yuz berdi. Iltimos qayta urinib ko'ring."
        finally:
            db.close()

        keyboard = {"keyboard": [[{"text": "💰 Bonuslarim"}, {"text": "🪪 Mening ID raqamim"}]], "resize_keyboard": True, "persistent": True}
        try:
            url = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN', '')}/sendMessage"
            send_data = _json.dumps({"chat_id": chat_id, "text": reply, "parse_mode": "Markdown", "reply_markup": keyboard}).encode("utf-8")
            req = urllib.request.Request(url, data=send_data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            _send_telegram_to(chat_id, reply)

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
        backup_data = crud.export_full_backup(db)
        content = _json_mod.dumps(backup_data, ensure_ascii=False, indent=2).encode("utf-8")
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
