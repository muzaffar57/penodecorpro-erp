"""
PenoDecorPro ERP — Asosiy server
=================================
"""

import os
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import init_database, get_db
import schemas
import crud
import services
import auth
from models import UserRole, Inventory

# ============================================================
# TELEGRAM XABAR (qoplamachi hodimga)
# ============================================================
import urllib.request
import json as _json

# @penodecorprobot tokeni — o'zgartirmang
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
# Qoplamachi hodimning Telegram chat_id si
TELEGRAM_COATING_ID = "8461987934"

def _send_telegram(text: str):
    """Qoplamachi hodimga Telegram xabar yuboradi."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("⚠ TELEGRAM_BOT_TOKEN yo'q")
        return
    try:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = _json.dumps({
            "chat_id":    TELEGRAM_COATING_ID,
            "text":       text,
            "parse_mode": "Markdown"
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)
        print(f"✓ Telegram xabar yuborildi")
    except Exception as e:
        print(f"⚠ Telegram xabar yuborilmadi: {e}")


def _send_telegram_to(chat_id: str, text: str):
    """Berilgan chat_id ga Telegram xabar yuboradi."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("⚠ TELEGRAM_BOT_TOKEN yo'q")
        return
    try:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = _json.dumps({
            "chat_id":    chat_id,
            "text":       text,
            "parse_mode": "Markdown"
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)
        print(f"✓ Telegram xabar yuborildi: {chat_id}")
    except Exception as e:
        print(f"⚠ Mijozga Telegram xabar yuborilmadi: {e}")

# Baza yaratilganligini tekshiramiz
init_database()

# Birinchi admin yaratish (baza bo'sh bo'lsa)
from database import SessionLocal
_db = SessionLocal()
try:
    auth.create_default_admin(_db)
finally:
    _db.close()

# FastAPI ilovani yaratamiz
app = FastAPI(
    title="PenoDecorPro ERP",
    description="Ishlab chiqarish boshqaruv tizimi",
    version="1.0.0",
    debug=True
)

# HTML shablonlar papkasi
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Static fayllar (CSS, rasmlar)
import os
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ============================================================
# AUTH SAHIFALAR
# ============================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    user = auth.get_current_user(request, db)
    if user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"error": None, "username": ""})


@app.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    from models import User
    user = db.query(User).filter(
        User.username == username,
        User.is_active == True
    ).first()

    if not user or not auth.verify_password(password, user.password_hash):
        return templates.TemplateResponse(request, "login.html", {
            "error": "Login yoki parol noto'g'ri!",
            "username": username
        })

    token = auth.create_session(user.id)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        key="session_token", value=token,
        httponly=True, max_age=3600 * 8, samesite="lax"
    )
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
async def users_page(request: Request, db: Session = Depends(get_db),
                     current_user=Depends(auth.admin_only)):
    users = auth.get_all_users(db)
    return templates.TemplateResponse(request, "users.html", {
        "users": users, "current_user": current_user,
        "now": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "active_page": "users"
    })


@app.post("/api/users")
def api_create_user(data: dict, db: Session = Depends(get_db),
                    current_user=Depends(auth.admin_only)):
    try:
        role = UserRole(data.get("role", "manager"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Noto'g'ri rol")
    user = auth.create_user(db, data["username"], data["password"],
                             role, data.get("full_name", ""))
    return {"id": user.id, "username": user.username, "role": user.role.value}


@app.post("/api/users/{user_id}/toggle")
def api_toggle_user(user_id: int, db: Session = Depends(get_db),
                    current_user=Depends(auth.admin_only)):
    user = auth.toggle_user_active(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"is_active": user.is_active}


@app.post("/api/users/{user_id}/password")
def api_change_password(user_id: int, data: dict, db: Session = Depends(get_db),
                        current_user=Depends(auth.admin_only)):
    new_pass = data.get("new_password", "")
    if len(new_pass) < 6:
        raise HTTPException(status_code=400, detail="Parol kamida 6 belgi")
    if not auth.change_password(db, user_id, new_pass):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


# ============================================================
# SAHIFALAR (HTML)
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    current_user = auth.get_current_user(request, db)
    if not current_user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "home.html", {
        "current_user": current_user,
        "active_page": "home"
    })


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db),
                         current_user=Depends(auth.admin_only)):
    stats = services.get_dashboard_stats(db)
    return templates.TemplateResponse(request, "dashboard.html", {
        "stats": stats, "current_user": current_user, "active_page": "dashboard"
    })


@app.get("/masters", response_class=HTMLResponse)
async def masters_page(request: Request, db: Session = Depends(get_db),
                       current_user=Depends(auth.admin_or_manager)):
    masters = crud.get_masters(db)
    return templates.TemplateResponse(request, "masters.html", {
        "masters": masters, "current_user": current_user, "active_page": "masters"
    })


@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, db: Session = Depends(get_db),
                         current_user=Depends(auth.admin_only)):
    items = crud.get_inventory(db)
    return templates.TemplateResponse(request, "inventory.html", {
        "items": items, "current_user": current_user, "active_page": "inventory"
    })


@app.get("/recipes", response_class=HTMLResponse)
async def recipes_page(request: Request, db: Session = Depends(get_db),
                       current_user=Depends(auth.admin_only)):
    recipes = crud.get_recipes(db)
    return templates.TemplateResponse(request, "recipes.html", {
        "recipes": recipes, "current_user": current_user, "active_page": "recipes"
    })


@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request, db: Session = Depends(get_db),
                        current_user=Depends(auth.admin_manager_accountant)):
    projects = crud.get_projects_with_stats(db)
    return templates.TemplateResponse(request, "projects.html", {
        "projects": projects, "current_user": current_user, "active_page": "projects"
    })


@app.post("/api/projects/{project_id}/payment")
def api_add_payment(project_id: int, amount: float, db: Session = Depends(get_db),
                    current_user=Depends(auth.admin_manager_accountant)):
    updated = crud.add_payment(db, project_id, amount)
    if not updated:
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    return {"status": "ok", "total_paid": float(updated.total_paid)}


@app.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request, db: Session = Depends(get_db),
                      current_user=Depends(auth.admin_or_manager)):
    orders = crud.get_orders(db)
    projects = crud.get_projects(db)
    masters = crud.get_masters(db, only_active=True)
    recipes = crud.get_recipes(db)
    return templates.TemplateResponse(request, "orders.html", {
        "orders": orders, "projects": projects,
        "masters": masters, "recipes": recipes,
        "current_user": current_user, "active_page": "orders"
    })


# ============================================================
# API — MASTER
# ============================================================
@app.post("/api/masters", response_model=schemas.MasterRead)
def api_create_master(master: schemas.MasterCreate, db: Session = Depends(get_db),
                      current_user=Depends(auth.admin_or_manager)):
    new_master = crud.create_master(db, master)

    # Usta Telegram ID si bo'lsa — xush kelibsiz SMS yuboramiz
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
def api_delete_master_permanent(master_id: int, db: Session = Depends(get_db),
                                current_user=Depends(auth.admin_only)):
    """Ustani bazadan to'liq o'chirish (faqat Admin)."""
    from models import Master
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(status_code=404, detail="Usta topilmadi")
    db.delete(master)
    db.commit()
    return {"status": "ok"}


@app.get("/api/masters", response_model=List[schemas.MasterRead])
def api_get_masters(only_active: bool = False, db: Session = Depends(get_db),
                    current_user=Depends(auth.admin_or_manager)):
    return crud.get_masters(db, only_active=only_active)

@app.delete("/api/masters/{master_id}")
def api_delete_master(master_id: int, db: Session = Depends(get_db),
                      current_user=Depends(auth.admin_or_manager)):
    if not crud.delete_master(db, master_id):
        raise HTTPException(status_code=404, detail="Usta topilmadi")
    return {"status": "ok"}


# ============================================================
# API — INVENTORY
# ============================================================
@app.post("/api/inventory", response_model=schemas.InventoryRead)
def api_create_item(item: schemas.InventoryCreate, db: Session = Depends(get_db),
                    current_user=Depends(auth.admin_or_manager)):
    return crud.add_item(db, item)

@app.get("/api/inventory", response_model=List[schemas.InventoryRead])
def api_get_inventory(db: Session = Depends(get_db),
                      current_user=Depends(auth.admin_or_manager)):
    return crud.get_inventory(db)

@app.post("/api/inventory/{item_id}/stock", response_model=schemas.InventoryRead)
def api_update_stock(item_id: int, change: schemas.StockChange, db: Session = Depends(get_db),
                     current_user=Depends(auth.admin_or_manager)):
    updated = crud.update_stock(db, item_id, change.quantity_change)
    if not updated:
        raise HTTPException(status_code=404, detail="Xomashyo topilmadi")
    return updated

@app.post("/api/inventory/{item_id}/price")
def api_update_price(item_id: int, data: dict, db: Session = Depends(get_db),
                     current_user=Depends(auth.admin_only)):
    """Xomashyo narxini yangilash."""
    item = db.query(crud.Inventory).filter(crud.Inventory.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Topilmadi")
    item.price_per_unit = data.get("price_per_unit", 0)
    db.commit()
    return {"status": "ok", "price_per_unit": item.price_per_unit}


@app.post("/api/inventory/full-stock-report")
def api_full_stock_report(db: Session = Depends(get_db),
                          current_user=Depends(auth.admin_only)):
    """Barcha xomashyolar holati haqida Telegram SMS yuborish."""
    from models import Inventory as Inv
    from datetime import datetime
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
        msg += f"━━━ KAM QOLGANLAR ({len(kam)} ta) ━━━\n"
        msg += "\n".join(kam) + "\n\n"

    msg += f"━━━ YETARLI ({len(yetarli)} ta) ━━━\n"
    msg += "\n".join(yetarli)
    msg += f"\n\n🏗 *PenoDecorPro* — Andijon"

    _send_telegram(msg)
    return {"message": f"Ombor hisoboti yuborildi! ({len(items)} ta xomashyo)"}


@app.post("/api/inventory/low-stock-alert")
def api_low_stock_alert(db: Session = Depends(get_db),
                        current_user=Depends(auth.admin_only)):
    """Kam qolgan xomashyolar haqida Telegram SMS yuborish."""
    low_items = crud.get_low_stock_items(db)

    if not low_items:
        return {"sent": False, "message": "Barcha xomashyolar yetarli — SMS yuborilmadi!"}

    lines = []
    for item in low_items:
        qty = float(item.stock_quantity)
        min_q = float(item.min_stock)
        deficit = min_q - qty
        emoji = "🔴" if qty <= min_q * 0.5 else "🟡"
        lines.append(
            f"{emoji} {item.item_name}: "
            f"{qty:.1f} {item.unit} qoldi "
            f"(min: {min_q:.0f}, yetishmaydi: {deficit:.1f})"
        )

    msg = (
        f"⚠️ *Ombor ogohlantirishlari!*\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines) +
        f"\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"Zudlik bilan buyurtma bering! 🚨\n\n"
        f"🏗 *PenoDecorPro* — Andijon"
    )

    _send_telegram(msg)

    return {
        "sent": True,
        "message": f"{len(low_items)} ta kam qolgan xomashyo haqida SMS yuborildi!"
    }


@app.delete("/api/inventory/{item_id}")
def api_delete_item(item_id: int, db: Session = Depends(get_db),
                    current_user=Depends(auth.admin_only)):
    if not crud.delete_item(db, item_id):
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"status": "ok"}


# ============================================================
# API — RECIPE
# ============================================================
@app.post("/api/recipes", response_model=schemas.RecipeRead)
def api_create_recipe(recipe: schemas.RecipeCreate, db: Session = Depends(get_db),
                      current_user=Depends(auth.admin_only)):
    return crud.create_recipe(db, recipe)

@app.get("/api/recipes", response_model=List[schemas.RecipeRead])
def api_get_recipes(db: Session = Depends(get_db),
                    current_user=Depends(auth.admin_or_manager)):
    return crud.get_recipes(db)


# ============================================================
# API — PROJECT
# ============================================================
@app.post("/api/projects", response_model=schemas.ProjectRead)
def api_create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db),
                       current_user=Depends(auth.admin_or_manager)):
    return crud.create_project(db, project)

@app.get("/api/projects", response_model=List[schemas.ProjectRead])
def api_get_projects(db: Session = Depends(get_db),
                     current_user=Depends(auth.admin_or_manager)):
    return crud.get_projects(db)

@app.put("/api/projects/{project_id}", response_model=schemas.ProjectRead)
def api_update_project(project_id: int, project: schemas.ProjectUpdate,
                       db: Session = Depends(get_db),
                       current_user=Depends(auth.admin_or_manager)):
    updated = crud.update_project(db, project_id, project)
    if not updated:
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    return updated

@app.delete("/api/projects/{project_id}")
def api_delete_project(project_id: int, db: Session = Depends(get_db),
                       current_user=Depends(auth.admin_or_manager)):
    if not crud.delete_project(db, project_id):
        raise HTTPException(status_code=404, detail="Loyiha topilmadi")
    return {"status": "ok"}


# ============================================================
# API — ORDER
# ============================================================
@app.post("/api/orders/coating-notify-new")
def api_coating_notify_with_loy(order_id: int, loy_kg: float,
                                 db: Session = Depends(get_db),
                                 current_user=Depends(auth.admin_or_manager)):
    pass


@app.post("/api/orders", response_model=schemas.OrderRead)
def api_create_order(order: schemas.OrderCreate, loy_kg: Optional[float] = None,
                     db: Session = Depends(get_db),
                     current_user=Depends(auth.admin_or_manager)):
    """Buyurtma yaratish — ombordan xomashyo ayiradi, yetmasa xabar beradi."""

    # Avval xomashyo yetishini tekshiramiz
    check = services.check_inventory_for_order(db, order)
    if not check["enough"]:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "message": "Xomashyo yetishmayapti!",
            "shortages": check["shortages"]
        })

    # Buyurtmani saqlaymiz
    new_order = crud.create_order(db, order)

    # Ombordan ayiramiz
    services.deduct_inventory_for_order(db, new_order)

    # Ombor min qoldiqqa yetganini tekshiramiz — yetgan bo'lsa SMS
    low_items = crud.get_low_stock_items(db)
    if low_items:
        lines = []
        for item in low_items:
            qty = float(item.stock_quantity)
            min_q = float(item.min_stock)
            deficit = min_q - qty
            emoji = "🔴" if qty <= min_q * 0.5 else "🟡"
            lines.append(
                f"{emoji} {item.item_name}: "
                f"{qty:.1f} {item.unit} qoldi "
                f"(min: {min_q:.0f}, yetishmaydi: {deficit:.1f})"
            )
        msg = (
            f"⚠️ *Ombor ogohlantirishlari!*\n\n"
            f"*{new_order.order_number}* buyurtmadan keyin:\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(lines) +
            f"\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"Zudlik bilan buyurtma bering! 🚨\n\n"
            f"🏗 *PenoDecorPro* — Andijon"
        )
        _send_telegram(msg)

    return new_order

@app.get("/api/orders", response_model=List[schemas.OrderRead])
def api_get_orders(project_id: Optional[int] = None, db: Session = Depends(get_db),
                   current_user=Depends(auth.admin_or_manager)):
    return crud.get_orders(db, project_id=project_id)

@app.get("/api/orders/{order_id}", response_model=schemas.OrderRead)
def api_get_order(order_id: int, db: Session = Depends(get_db),
                  current_user=Depends(auth.admin_or_manager)):
    """Bitta buyurtmani olish."""
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    # items ni yuklash
    _ = order.items
    _ = order.project
    _ = order.master
    return order


@app.post("/api/orders/{order_id}/coating-notify")
def api_coating_notify(order_id: int, loy_kg: float,
                       db: Session = Depends(get_db),
                       current_user=Depends(auth.admin_or_manager)):
    """Yangi buyurtma uchun qoplamachi hodimga loy SMS yuborish va loy_kg ni saqlash."""
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

    # loy_kg ni order.notes ga saqlaymiz
    if loy_kg > 0:
        existing = order.notes or ''
        if 'loy_kg=' not in existing:
            order.notes = (existing + f',loy_kg={loy_kg}').strip(',')
        else:
            parts = [p for p in existing.split(',') if 'loy_kg=' not in p]
            parts.append(f'loy_kg={loy_kg}')
            order.notes = ','.join(parts)
        db.commit()

        # SMS yuborish
        msg = (
            f"🏗 *PenoDecorPro — Yangi buyurtma*\n\n"
            f"📋 Buyurtma: *{order.order_number}*\n"
            f"👤 Mijoz: {order.project.client_name if order.project else '—'}\n"
            f"🧱 Loy tayyorlang: *{int(loy_kg)} kg*\n\n"
            f"⏰ {__import__('datetime').datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        _send_telegram(msg)
    return {"status": "ok"}


@app.post("/api/orders/{order_id}/ready")
def api_mark_order_ready(order_id: int, loy_kg: Optional[float] = None,
                         db: Session = Depends(get_db),
                         current_user=Depends(auth.admin_or_manager)):
    """Buyurtmani TAYYOR qilish — to'liq avtomatika."""
    result = services.complete_order(db, order_id, loy_kg)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)

    order = crud.get_order(db, order_id)
    if order:
        # Loy miqdori bo'lsa qoplamachi hodimga xabar
        if loy_kg and loy_kg > 0:
            msg = (
                f"🏗 *PenoDecorPro — Yangi topshiriq*\n\n"
                f"📋 Buyurtma: *{order.order_number}*\n"
                f"👤 Mijoz: {order.project.client_name if order.project else '—'}\n"
                f"🧱 Loy tayyorlang: *{int(loy_kg)} kg*\n\n"
                f"⏰ {__import__('datetime').datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            _send_telegram(msg)

        # Mijozga xabar (agar Telegram ID bo'lsa)
        if order.project and order.project.notes:
            notes = order.project.notes or ''
            tg_id = None
            # notes dan tg_id= ni topamiz
            if 'tg_id=' in notes:
                try:
                    tg_id = notes.split('tg_id=')[1].split(',')[0].strip()
                except:
                    pass
            # Agar tg_id raqam bo'lsa yuboramiz
            if tg_id and tg_id.lstrip('-').isdigit():
                client_msg = (
                    f"✅ *Buyurtmangiz tayyor!*\n\n"
                    f"📋 Buyurtma: *{order.order_number}*\n"
                    f"👤 Mijoz: {order.project.client_name}\n"
                    f"🏗 PenoDecorPro — Andijon\n\n"
                    f"Buyurtmangizni olishingiz mumkin!\n"
                    f"⏰ {__import__('datetime').datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )
                _send_telegram_to(tg_id, client_msg)

    return result


@app.post("/api/orders/mark-all-ready")
def api_mark_all_ready(loy_kg: Optional[float] = None, db: Session = Depends(get_db),
                       current_user=Depends(auth.admin_or_manager)):
    """Barcha 'Jarayonda' buyurtmalarni TAYYOR qilish."""
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

    return {
        "processed": processed,
        "total_pending": len(pending),
        "failed": failed,
        "total_inventory_changes": total_inventory_changes
    }


@app.delete("/api/orders/{order_id}")
def api_delete_order(order_id: int, db: Session = Depends(get_db),
                     current_user=Depends(auth.admin_or_manager)):
    if not crud.delete_order(db, order_id):
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    return {"status": "ok"}


@app.delete("/api/order-items/{item_id}")
def api_delete_order_item(item_id: int, db: Session = Depends(get_db),
                          current_user=Depends(auth.admin_or_manager)):
    if not crud.delete_order_item(db, item_id):
        raise HTTPException(status_code=404, detail="Detal topilmadi")
    return {"status": "ok"}


@app.put("/api/order-items/{item_id}")
def api_update_order_item(item_id: int, data: dict, db: Session = Depends(get_db),
                          current_user=Depends(auth.admin_or_manager)):
    updated = crud.update_order_item(db, item_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Detal topilmadi")
    return {"status": "ok"}


# ============================================================
# API — DASHBOARD
# ============================================================
@app.get("/api/dashboard/stats")
def api_dashboard_stats(db: Session = Depends(get_db),
                        current_user=Depends(auth.admin_manager_accountant)):
    return services.get_dashboard_stats(db)

@app.get("/api/dashboard/charts")
def api_dashboard_charts(db: Session = Depends(get_db),
                         current_user=Depends(auth.admin_manager_accountant)):
    return services.get_chart_data(db)

@app.get("/api/warnings/low-stock")
def api_low_stock(db: Session = Depends(get_db)):
    return {"warnings": services.get_low_stock_warnings(db)}


@app.get("/debts", response_class=HTMLResponse)
async def debts_page(request: Request, db: Session = Depends(get_db),
                     current_user=Depends(auth.admin_or_manager)):
    """Qarzdorlar sahifasi."""
    from models import Project
    from sqlalchemy import func
    all_projects = db.query(Project).filter(
        Project.total_budget > Project.total_paid
    ).order_by(Project.total_budget.desc()).all()

    debts = [p for p in all_projects if float(p.total_budget or 0) - float(p.total_paid or 0) > 0]
    total_debt = sum(float(p.total_budget or 0) - float(p.total_paid or 0) for p in debts)
    total_paid = sum(float(p.total_paid or 0) for p in debts)
    total_budget = sum(float(p.total_budget or 0) for p in debts)

    return templates.TemplateResponse(request, "debts.html", {
        "debts": debts,
        "total_debt": total_debt,
        "total_paid": total_paid,
        "total_budget": total_budget,
        "current_user": current_user,
        "active_page": "debts"
    })


@app.get("/finance", response_class=HTMLResponse)
async def finance_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(auth.admin_only)
):
    """Oylik moliyaviy hisobot — faqat Admin."""
    return templates.TemplateResponse(request, "finance.html", {
        "current_user": current_user, "active_page": "finance"
    })


@app.get("/api/finance/report")
def api_finance_report(
    year: int, month: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.admin_only)
):
    """Oylik hisobot ma'lumotlari."""
    return services.get_monthly_report(db, year, month)


@app.post("/api/finance/expense")
def api_save_expense(
    year: int, month: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(auth.admin_only)
):
    """Oylik xarajatlarni saqlash."""
    services.save_monthly_expense(db, year, month, data)
    return {"status": "ok"}


@app.get("/api/orders/{order_id}/profit")
def api_order_profit(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.admin_only)
):
    """Buyurtma foyda va tan narxini hisoblash — faqat Admin."""
    return services.calculate_order_profit(db, order_id)


@app.get("/api/orders/{order_id}/pdf")
def api_order_pdf(
    order_id: int,
    db: Session = Depends(get_db)
):
    """Buyurtma uchun PDF nakladnoy chiqarish."""
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
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "message": "PenoDecorPro ERP ishlamoqda!"}


# ============================================================
# RETURNS — SAHIFA VA API
# ============================================================

@app.get("/returns", response_class=HTMLResponse)
async def returns_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(auth.admin_or_manager)
):
    """Qaytarishlar sahifasi."""
    returns = crud.get_return_items(db)
    orders  = crud.get_orders(db)
    return templates.TemplateResponse(request, "returns.html", {
        "returns": returns,
        "orders": orders,
        "current_user": current_user
    })


@app.post("/api/returns")
def api_create_return(
    data: schemas.ReturnItemCreate,
    db: Session = Depends(get_db),
    current_user=Depends(auth.admin_or_manager)
):
    """Yangi qaytarish qo'shish."""
    return crud.create_return_item(db, data)


@app.get("/api/returns")
def api_get_returns(
    order_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user=Depends(auth.admin_or_manager)
):
    """Qaytarishlar ro'yxati."""
    return crud.get_return_items(db, order_id=order_id)


@app.get("/api/returns/stats")
def api_return_stats(
    db: Session = Depends(get_db),
    current_user=Depends(auth.admin_or_manager)
):
    """Qaytarishlar statistikasi."""
    return crud.get_return_stats(db)


@app.post("/api/returns/{return_id}/refund")
def api_mark_refunded(
    return_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.admin_or_manager)
):
    """Qaytarishni to'landi deb belgilash."""
    item = crud.mark_refunded(db, return_id)
    if not item:
        raise HTTPException(status_code=404, detail="Qaytarish topilmadi")
    return {"status": "ok", "is_refunded": item.is_refunded}


@app.delete("/api/returns/{return_id}")
def api_delete_return(
    return_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.admin_or_manager)
):
    """Qaytarishni o'chirish."""
    if not crud.delete_return_item(db, return_id):
        raise HTTPException(status_code=404, detail="Qaytarish topilmadi")
    return {"status": "ok"}




# ============================================================
# TELEGRAM WEBHOOK — USTA BONUS TEKSHIRUVI
# ============================================================

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Telegram bot webhook — ustalar bonus so'rovini qabul qiladi."""
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

    # Faqat /bonus va /start komandalarini qabul qilamiz
    if text in ["/bonus", "/start", "/balanс", "/balans"]:
        db = SessionLocal()
        try:
            from models import Master, Order, OrderStatus

            # /start da klaviatura tugmalar ko'rsatamiz
            if text == "/start":
                keyboard = {
                    "keyboard": [
                        [{"text": "💰 Bonuslarim"}, {"text": "🪪 Mening ID raqamim"}],
                    ],
                    "resize_keyboard": True,
                    "persistent": True
                }
                welcome_msg = (
                    f"Assalomu alaykum! 👋\n\n"
                    f"*PenoDecorPro* bot ga xush kelibsiz!\n\n"
                    f"Quyidagi tugmalardan foydalaning:"
                )
                # Klaviatura bilan yuborish
                try:
                    url = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN', '')}/sendMessage"
                    send_data = _json.dumps({
                        "chat_id": chat_id,
                        "text": welcome_msg,
                        "parse_mode": "Markdown",
                        "reply_markup": keyboard
                    }).encode("utf-8")
                    req = urllib.request.Request(url, data=send_data,
                                                 headers={"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=5)
                except Exception as e:
                    print(f"Keyboard SMS xatosi: {e}")
                return {"ok": True}

        except Exception as e:
            reply = "⚠️ Xatolik yuz berdi."
        finally:
            db.close()

    # ID so'rovi
    if text in ["/id", "🪪 mening id raqamim", "mening id raqamim"]:
        reply = (
            f"🪪 *Sizning Telegram ID raqamingiz:*\n\n"
            f"`{chat_id}`\n\n"
            f"Shu raqamni nusxalab administratorga yuboring — "
            f"ustalar ro'yxatiga qo'shilasiz va bonuslaringizni "
            f"kuzatib borishingiz mumkin bo'ladi! 👷"
        )
        _send_telegram_to(chat_id, reply)
        return {"ok": True}

    if text in ["/bonus", "💰 bonuslarim", "bonuslarim", "/balanс", "/balans"]:
        db = SessionLocal()
        try:
            from models import Master, Order, OrderStatus
            from sqlalchemy import func

            # Telegram ID bo'yicha ustani topamiz
            master = db.query(Master).filter(
                Master.telegram_id == chat_id,
                Master.is_active == True
            ).first()

            if not master:
                reply = (
                    "❌ Siz ustalar ro'yxatida topilmadingiz.\n\n"
                    "Iltimos, administrator bilan bog'laning.\n\n"
                    "📞 PenoDecorPro — Andijon"
                )
            else:
                # Barcha tayyor buyurtmalarni topamiz
                orders = db.query(Order).filter(
                    Order.master_id == master.id,
                    Order.status == OrderStatus.READY
                ).order_by(Order.completed_at.desc()).all()

                jami_bonus = 0.0
                buyurtmalar_text = ""

                for i, o in enumerate(orders[:10]):  # Oxirgi 10 ta
                    sotuv = float(o.total_amount or 0)
                    bonus = sotuv * float(master.cashback_percent) / 100
                    jami_bonus += bonus
                    buyurtmalar_text += (
                        f"• {o.order_number} — "
                        f"{int(sotuv):,} so'm → "
                        f"*{int(bonus):,} so'm* ✅\n"
                    )

                # Faol buyurtmalar
                faol = db.query(Order).filter(
                    Order.master_id == master.id,
                    Order.status != OrderStatus.READY
                ).count()

                reply = (
                    f"📊 *Sizning bonuslaringiz*\n\n"
                    f"👤 {master.name}\n"
                    f"🎯 Bonus foizi: *{master.cashback_percent}%*\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                )

                if buyurtmalar_text:
                    reply += f"📋 *Oxirgi buyurtmalar:*\n{buyurtmalar_text}\n"

                if faol > 0:
                    reply += f"⏳ Jarayondagi buyurtmalar: *{faol} ta*\n\n"

                reply += (
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 *Jami bonus: {int(jami_bonus):,} so'm*\n\n"
                    f"🏗 PenoDecorPro — Andijon"
                )

        except Exception as e:
            reply = f"⚠️ Xatolik yuz berdi. Iltimos qayta urinib ko'ring."
        finally:
            db.close()

        # Javob klaviatura bilan yuboramiz
        keyboard = {
            "keyboard": [
                [{"text": "💰 Bonuslarim"}, {"text": "🪪 Mening ID raqamim"}],
            ],
            "resize_keyboard": True,
            "persistent": True
        }
        try:
            url = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN', '')}/sendMessage"
            send_data = _json.dumps({
                "chat_id": chat_id,
                "text": reply,
                "parse_mode": "Markdown",
                "reply_markup": keyboard
            }).encode("utf-8")
            req = urllib.request.Request(url, data=send_data,
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            _send_telegram_to(chat_id, reply)

    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
