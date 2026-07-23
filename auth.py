"""
PenoDecorPro ERP — Auth (Login) tizimi
========================================
Cookie asosida sessiya, rol bo'yicha ruxsatlar.

Rollar:
- ADMIN      — hamma narsaga kirish
- MANAGER    — loyihalar, buyurtmalar, omborxona, ustalar
- ACCOUNTANT — faqat loyihalar va dashboard (to'lov ko'rish)
- MASTER     — faqat o'zining buyurtmalari
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserRole


# ============================================================
# Parol funksiyalari
# ============================================================

def hash_password(password: str) -> str:
    """Parolni SHA-256 bilan shifrlaydi.
    Keyinchalik bcrypt ga o'tish uchun faqat shu funksiyani o'zgartirish kifoya."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Kiritilgan parolni bazadagi hash bilan solishtiradi."""
    return hash_password(plain_password) == hashed_password


# ============================================================
# Sessiya funksiyalari
# ============================================================

# ============================================================
# Sessiya saqlash — BAZADA (xotirada emas!)
# MUHIM: avval xotirada (_sessions dict) saqlanardi — bu, server
# qayta ishga tushganda (Railway uyqu/uyg'onish, har bir deploy)
# BARCHA foydalanuvchilarni tizimdan chiqarib yuborar edi, chunki
# xotira tozalanadi. Endi bazada saqlanadi — server qayta ishga
# tushsa ham, sessiya SAQLANIB QOLADI.
# ============================================================

# Sessiya muddati — 8 soat
SESSION_HOURS = 8


def create_session(db: Session, user_id: int) -> str:
    """Yangi sessiya token yaratadi va BAZAGA saqlaydi."""
    from models import UserSession
    token = secrets.token_urlsafe(32)
    entry = UserSession(
        token=token, user_id=user_id,
        expires_at=datetime.utcnow() + timedelta(hours=SESSION_HOURS)
    )
    db.add(entry)
    db.commit()
    return token


def get_session(db: Session, token: str) -> Optional[dict]:
    """Token bo'yicha sessiyani BAZADAN qaytaradi. Muddati o'tgan bo'lsa o'chiradi."""
    from models import UserSession
    entry = db.query(UserSession).filter(UserSession.token == token).first()
    if not entry:
        return None
    if entry.expires_at < datetime.utcnow():
        db.delete(entry)
        db.commit()
        return None
    return {"user_id": entry.user_id, "expires": entry.expires_at}


def delete_session(db: Session, token: str):
    """Sessiyani bazadan o'chiradi (logout)."""
    from models import UserSession
    db.query(UserSession).filter(UserSession.token == token).delete()
    db.commit()


def cleanup_expired_sessions(db: Session):
    """Muddati o'tgan barcha sessiyalarni bazadan tozalaydi."""
    from models import UserSession
    db.query(UserSession).filter(UserSession.expires_at < datetime.utcnow()).delete()
    db.commit()


# ============================================================
# Joriy foydalanuvchini olish
# ============================================================

def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Cookie dan token olib, joriy foydalanuvchini qaytaradi.
    Login sahifasiga yo'naltirish kerak bo'lsa — None qaytaradi."""
    token = request.cookies.get("session_token")
    if not token:
        return None

    session = get_session(db, token)
    if not session:
        return None

    user = db.query(User).filter(
        User.id == session["user_id"],
        User.is_active == True
    ).first()
    return user


def require_login(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """Foydalanuvchi login qilganligini tekshiradi.
    Agar login qilinmagan bo'lsa — 401 xato."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Iltimos, tizimga kiring",
            headers={"Location": "/login"}
        )
    return user


# ============================================================
# Rol bo'yicha ruxsatlar
# ============================================================

# Har bir sahifaga kimlar kira oladi
# ESLATMA: bu lug'at hozircha DASTURDA ishlatilmaydi — haqiqiy nazorat har bir
# endpoint'dagi Depends(auth.X) orqali amalga oshadi. Shu yerda faqat izoh/hujjat
# sifatida yangi tuzilishga moslab qo'yildi.
PAGE_PERMISSIONS = {
    "/dashboard":  [UserRole.ADMIN, UserRole.ACCOUNTANT],
    "/masters":    [UserRole.ADMIN, UserRole.ACCOUNTANT],
    "/inventory":  [UserRole.ADMIN, UserRole.WAREHOUSE, UserRole.MANAGER],
    "/recipes":    [UserRole.ADMIN, UserRole.WAREHOUSE],
    "/projects":   [UserRole.ADMIN, UserRole.MANAGER, UserRole.ACCOUNTANT],
    "/orders":     [UserRole.ADMIN, UserRole.MANAGER, UserRole.MASTER],
    "/returns":    [UserRole.ADMIN, UserRole.MANAGER, UserRole.WAREHOUSE],
    "/users":      [UserRole.ADMIN],
}


def require_role(allowed_roles: list):
    """Dekorator — faqat ruxsat etilgan rollar sahifaga kira oladi.

    Ishlatilishi:
        user = require_role([UserRole.ADMIN, UserRole.MANAGER])(request, db)
    """
    def checker(
        request: Request,
        db: Session = Depends(get_db)
    ) -> User:
        user = require_login(request, db)
        if user.role not in allowed_roles:
            roles_str = ", ".join([r.value for r in allowed_roles])
            raise HTTPException(
                status_code=403,
                detail=f"Bu sahifaga faqat {roles_str} kira oladi"
            )
        return user
    return checker


# Tayyor checker funksiyalar — main.py da ishlatiladi
def admin_only(request: Request, db: Session = Depends(get_db)) -> User:
    return require_role([UserRole.ADMIN])(request, db)


def admin_or_manager(request: Request, db: Session = Depends(get_db)) -> User:
    """Buyurtma/Loyiha/Yetkazish — Hodim (Menejer)ning asosiy ish maydoni."""
    return require_role([UserRole.ADMIN, UserRole.MANAGER])(request, db)


def orders_page_access(request: Request, db: Session = Depends(get_db)) -> User:
    """Buyurtmalar SAHIFASI — Admin, Hodim va Usta (Usta faqat o'zining
    buyurtmalarini ko'rish uchun kiradi)."""
    return require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.MASTER])(request, db)


def admin_manager_accountant(request: Request, db: Session = Depends(get_db)) -> User:
    return require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.ACCOUNTANT])(request, db)


def admin_or_financier(request: Request, db: Session = Depends(get_db)) -> User:
    """Moliya, Hisobotlar, Qarzdorlik, Ustalar KPI, xodim avansini tasdiqlash —
    faqat Admin va Moliyachi (ACCOUNTANT roli)."""
    return require_role([UserRole.ADMIN, UserRole.ACCOUNTANT])(request, db)


def admin_or_warehouse(request: Request, db: Session = Depends(get_db)) -> User:
    """Omborxona (to'liq boshqarish), Xomashyo ta'minoti, Tayyor mahsulot,
    Retseptlar — faqat Admin va Omborchi."""
    return require_role([UserRole.ADMIN, UserRole.WAREHOUSE])(request, db)


def inventory_view(request: Request, db: Session = Depends(get_db)) -> User:
    """Omborni FAQAT KO'RISH (miqdor) — Hodim buyurtma yaratayotganda xomashyo
    yetarli-yetarli emasligini bilishi uchun, lekin boshqarish huquqisiz."""
    return require_role([UserRole.ADMIN, UserRole.WAREHOUSE, UserRole.MANAGER])(request, db)


def order_payments(request: Request, db: Session = Depends(get_db)) -> User:
    """To'lov qo'shish — Hodim (o'z buyurtmasiga) va Moliyachi (barchasiga)."""
    return require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.ACCOUNTANT])(request, db)


def manager_or_warehouse(request: Request, db: Session = Depends(get_db)) -> User:
    """Qaytarishlar — ham Hodim (buyurtma tomonidan), ham Omborchi (ombor
    tomonidan) kirishi kerak bo'lgan, ikkalasiga umumiy joy."""
    return require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.WAREHOUSE])(request, db)


def all_staff(request: Request, db: Session = Depends(get_db)) -> User:
    return require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.ACCOUNTANT, UserRole.MASTER, UserRole.WAREHOUSE])(request, db)


# ============================================================
# Foydalanuvchi CRUD (faqat admin uchun)
# ============================================================

def create_user(db: Session, username: str, password: str,
                role: UserRole, full_name: str = "") -> User:
    """Yangi foydalanuvchi yaratadi."""
    # Username band emasligini tekshiramiz
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu username band")

    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        full_name=full_name,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_all_users(db: Session) -> list:
    """Barcha foydalanuvchilarni qaytaradi."""
    return db.query(User).order_by(User.username).all()


def toggle_user_active(db: Session, user_id: int) -> Optional[User]:
    """Foydalanuvchini faollashtiradi yoki o'chiradi."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    user.is_active = not user.is_active
    db.commit()
    return user


def change_password(db: Session, user_id: int, new_password: str) -> bool:
    """Parolni yangilaydi."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    user.password_hash = hash_password(new_password)
    db.commit()
    return True


# ============================================================
# XODIM PANELI — alohida, cheklangan sessiya tizimi
# (User/parol tizimidan MUSTAQIL — faqat telefon+PIN bilan)
# Sessiya BAZADA saqlanadi (server qayta ishga tushsa ham chiqarilmasin uchun).
# ============================================================

from models import Employee

EMPLOYEE_SESSION_HOURS = 24 * 14  # 14 kun — xodim tez-tez qayta kirmasin


def hash_pin(pin: str) -> str:
    """PIN kodni shifrlaydi (parol bilan bir xil usulda)."""
    return hash_password(pin)


def create_employee_session(db: Session, employee_id: int) -> str:
    from models import EmployeeSession
    token = secrets.token_urlsafe(32)
    entry = EmployeeSession(
        token=token, employee_id=employee_id,
        expires_at=datetime.utcnow() + timedelta(hours=EMPLOYEE_SESSION_HOURS)
    )
    db.add(entry)
    db.commit()
    return token


def get_employee_session(db: Session, token: str) -> Optional[dict]:
    from models import EmployeeSession
    entry = db.query(EmployeeSession).filter(EmployeeSession.token == token).first()
    if not entry:
        return None
    if entry.expires_at < datetime.utcnow():
        db.delete(entry)
        db.commit()
        return None
    return {"employee_id": entry.employee_id, "expires": entry.expires_at}


def delete_employee_session(db: Session, token: str):
    from models import EmployeeSession
    db.query(EmployeeSession).filter(EmployeeSession.token == token).delete()
    db.commit()


def get_current_employee(request: Request, db: Session = Depends(get_db)) -> Optional[Employee]:
    """Cookie dan token olib, joriy xodimni qaytaradi."""
    token = request.cookies.get("emp_session_token")
    if not token:
        return None
    session = get_employee_session(db, token)
    if not session:
        return None
    employee = db.query(Employee).filter(
        Employee.id == session["employee_id"],
        Employee.is_active == True
    ).first()
    return employee


def require_employee_login(request: Request, db: Session = Depends(get_db)) -> Employee:
    """Xodim login qilganligini tekshiradi."""
    employee = get_current_employee(request, db)
    if not employee:
        raise HTTPException(
            status_code=401,
            detail="Iltimos, tizimga kiring",
            headers={"Location": "/hodim/login"}
        )
    return employee





def create_default_admin(db: Session):
    """Agar hech qanday foydalanuvchi bo'lmasa — standart admin yaratadi."""
    import os
    password = os.environ.get("ADMIN_PASSWORD", "Admin123!")

    count = db.query(User).count()
    if count == 0:
        create_user(
            db=db,
            username="admin",
            password=password,
            role=UserRole.ADMIN,
            full_name="Bosh Administrator"
        )
        print("✓ Standart admin yaratildi!")
    else:
        # Agar RESET_ADMIN_PASSWORD=true bo'lsa — admin parolini yangilaydi
        reset = os.environ.get("RESET_ADMIN_PASSWORD", "false").lower()
        if reset == "true":
            admin = db.query(User).filter(User.username == "admin").first()
            if admin:
                admin.password_hash = hash_password(password)
                db.commit()
                print(f"✓ Admin paroli yangilandi!")
