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
import bcrypt
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
    """Parolni bcrypt bilan shifrlaydi — har bir parol uchun boshqa
    "tuz" (salt) ishlatiladi, hatto ikki kishi bir xil parol qo'ysa ham,
    natija boshqa-boshqa bo'ladi (lug'at/rainbow-table hujumlariga
    ancha chidamli, eski SHA-256 dan farqli)."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _is_bcrypt_hash(hashed: str) -> bool:
    return hashed.startswith(("$2b$", "$2a$", "$2y$"))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Kiritilgan parolni bazadagi hash bilan solishtiradi. ESKI (SHA-256)
    va YANGI (bcrypt) — ikkala formatni ham qo'llab-quvvatlaydi, shunda
    hali eski formatda saqlangan foydalanuvchilar ham to'siqsiz kira oladi."""
    if _is_bcrypt_hash(hashed_password):
        try:
            return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
        except ValueError:
            return False
    # Eski format (SHA-256) — orqaga moslik uchun
    return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password


def verify_and_upgrade_password(db: Session, user, plain_password: str) -> bool:
    """verify_password bilan bir xil natija qaytaradi, lekin QO'SHIMCHA:
    agar parol TO'G'RI bo'lsa-yu, hali ESKI (SHA-256) formatda saqlangan
    bo'lsa — muvaffaqiyatli kirishning O'ZIDA, foydalanuvchiga sezdirmasdan,
    bcrypt formatiga yangilaydi. Shunday qilib, har bir foydalanuvchi vaqt
    o'tishi bilan (parolni majburan tiklashsiz) xavfsizroq formatga o'tadi."""
    ok = verify_password(plain_password, user.password_hash)
    if ok and not _is_bcrypt_hash(user.password_hash):
        user.password_hash = hash_password(plain_password)
        db.commit()
    return ok


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


def cleanup_expired_sessions(db: Session) -> dict:
    """Muddati o'tgan barcha sessiyalarni (Admin panel VA Hodim panel)
    bazadan tozalaydi."""
    from models import UserSession, EmployeeSession
    now = datetime.utcnow()
    n_user = db.query(UserSession).filter(UserSession.expires_at < now).delete()
    n_emp = db.query(EmployeeSession).filter(EmployeeSession.expires_at < now).delete()
    db.commit()
    return {"user_sessions": n_user, "employee_sessions": n_emp}


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
# Joriy KORXONA (tenant) — SaaS ko'p-tenantlilik poydevori
# ============================================================
# 2026-09-18, 1-QADAM. Bu yerdan boshlab, "bu so'rov qaysi korxonaniki?"
# degan savolga javob beradigan YAGONA, markaziy manba mavjud.
# Keyingi bosqichlarda har bir jadval va har bir so'rov shu qiymat
# bo'yicha filtrlanadi.

# O'TISH DAVRI uchun. Hozircha tizimda bitta korxona bor va bazadagi
# users.company_id ustunida DEFAULT 1 turibdi. Ikkalasi ham, barcha
# yozuv nuqtalari company_id ni ANIQ yuboradigan bo'lgandan keyin
# olib tashlanadi.
DEFAULT_COMPANY_ID = 1


def company_id_of(user) -> int:
    """Berilgan foydalanuvchining korxona (tenant) raqamini qaytaradi.

    Kodning allaqachon `user` obyekti bor joylari uchun — qo'shimcha
    baza so'rovisiz. Qiymat bo'lmasa, JIMGINA 1 ga tushib qolmaydi,
    balki aniq xato beradi: ko'p-tenantli tizimda "qaysi korxona
    ekani noma'lum" holatini taxmin bilan to'ldirish — bir korxonaning
    ma'lumotini boshqasiga ko'rsatib qo'yishning eng qisqa yo'li."""
    company_id = getattr(user, "company_id", None)
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail=("Foydalanuvchi hech qaysi korxonaga biriktirilmagan. "
                    "Administratorga murojaat qiling."),
        )
    return company_id


def get_current_company_id(
    request: Request,
    db: Session = Depends(get_db)
) -> int:
    """FastAPI bog'liqligi (dependency) — joriy so'rovning korxona raqami.

    Ishlatilishi (keyingi bosqichlarda, endpointlarda):
        @app.get("/api/orders")
        def list_orders(company_id: int = Depends(auth.get_current_company_id),
                        db: Session = Depends(get_db)):
            return db.query(Order).filter(Order.company_id == company_id).all()

    ESLATMA: Hodim paneli (Employee) hali company_id ga ega emas —
    unga mos funksiya `employees` jadvaliga ustun qo'shilgandan keyin
    (keyingi to'lqinda) yoziladi. Telegram bot/webhook yo'llarida ham
    foydalanuvchi sessiyasi yo'q, ular alohida ko'rib chiqiladi."""
    user = require_login(request, db)
    return company_id_of(user)


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
    """Omborxona (to'liq boshqarish), Xomashyo ta'minoti,
    Retseptlar — faqat Admin va Omborchi."""
    return require_role([UserRole.ADMIN, UserRole.WAREHOUSE])(request, db)


def admin_warehouse_or_manager(request: Request, db: Session = Depends(get_db)) -> User:
    """Tayyor mahsulot — Admin, Omborchi VA Hodim (Manager) — 2026-09'da,
    Hodimga ham shu bo'limni ochib berish so'ralgani uchun qo'shildi."""
    return require_role([UserRole.ADMIN, UserRole.WAREHOUSE, UserRole.MANAGER])(request, db)


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
                role: UserRole, full_name: str = "",
                company_id: int = None) -> User:
    # 2026-09-18 — M1: company_id endi MAJBURIY.
    # Ilgari berilmasa DEFAULT_COMPANY_ID (=1) qo'yilardi — ya'ni B korxona
    # admini yangi foydalanuvchi yaratsa, u A korxonaga tushib qolardi.
    # Endi chaqiruvchi uni joriy foydalanuvchining korxonasidan uzatadi.
    # Yagona istisno — bo'sh bazadagi birinchi admin (create_default_admin),
    # u ataylab DEFAULT_COMPANY_ID bilan chaqiriladi.
    if not company_id:
        raise HTTPException(
            status_code=500,
            detail="Ichki xato: foydalanuvchi yaratishda korxona aniqlanmadi.")
    """Yangi foydalanuvchi yaratadi.

    company_id — qaysi korxonaga tegishli ekani. Berilmasa, O'TISH DAVRI
    uchun DEFAULT_COMPANY_ID ishlatiladi. Buni ATAYLAB aniq yozib
    qo'ydik (bazadagi DEFAULT ga tayanish o'rniga): yangi, bo'sh bazada
    ustunda DEFAULT bo'lmaydi, va u holda foydalanuvchi yaratish NOT NULL
    xatosi bilan yiqilardi.

    Keyingi bosqichda bu parametr MAJBURIY bo'ladi va chaqiruvchi uni
    get_current_company_id() dan oladi."""
    username = username.strip()
    # Username band emasligini tekshiramiz
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu username band")

    user = User(
        company_id=company_id,
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


def get_all_users(db: Session, company_id: int) -> list:
    """Faqat berilgan korxonaning foydalanuvchilari.

    2026-09-18 — M1: company_id endi MAJBURIY. Ilgari ixtiyoriy edi va
    chaqiruvda berilmasdi — natijada admin BARCHA korxonalar ro'yxatini
    ko'rardi (ularning id lari bilan birga, bu esa keyingi hujum uchun
    kerak bo'lgan ma'lumot)."""
    return (db.query(User)
            .filter(User.company_id == company_id)
            .order_by(User.username).all())


def toggle_user_active(db: Session, user_id: int, company_id: int) -> Optional[User]:
    """Foydalanuvchini faollashtiradi yoki o'chiradi.

    2026-09-18 — M1: company_id shart. Ilgari faqat id bo'yicha qidirilardi,
    ya'ni A korxona admini B korxona adminini o'chirib qo'yishi mumkin edi."""
    user = db.query(User).filter(
        User.id == user_id, User.company_id == company_id).first()
    if not user:
        return None
    user.is_active = not user.is_active
    db.commit()
    return user


def change_password(db: Session, user_id: int, new_password: str,
                    company_id: int = None) -> bool:
    """Parolni yangilaydi.

    2026-09-18 — M1: company_id shart (eng jiddiy topilma). Ilgari faqat id
    bo'yicha qidirilardi — A korxona admini B korxona adminining parolini
    almashtirib, o'sha korxonaga to'liq kirish huquqini olishi mumkin edi."""
    if not company_id:
        raise HTTPException(
            status_code=500,
            detail="Ichki xato: parol o'zgartirishda korxona aniqlanmadi.")
    user = db.query(User).filter(
        User.id == user_id, User.company_id == company_id).first()
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


def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """PIN kodni tekshiradi. MUHIM: bcrypt — tasodifiy "tuz" ishlatgani
    uchun, ikkita hash'ni to'g'ridan-to'g'ri solishtirib bo'lmaydi (bir xil
    PIN har safar BOSHQA hash beradi) — shuning uchun har doim shu funksiya
    orqali (verify_password kabi, checkpw bilan) tekshiriladi."""
    return verify_password(plain_pin, hashed_pin)


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


def order_of_company(db: Session, order_id: int, company_id: int):
    """Buyurtmani FAQAT shu korxona ichidan topadi (M2)."""
    from models import Order
    return db.query(Order).filter(
        Order.id == order_id, Order.company_id == company_id).first()


def project_of_company(db: Session, project_id: int, company_id: int):
    """Loyihani FAQAT shu korxona ichidan topadi (M2)."""
    from models import Project
    return db.query(Project).filter(
        Project.id == project_id, Project.company_id == company_id).first()


def return_of_company(db: Session, return_id: int, company_id: int):
    """Qaytarishni FAQAT shu korxona ichidan topadi (M2)."""
    from models import ReturnItem
    return db.query(ReturnItem).filter(
        ReturnItem.id == return_id, ReturnItem.company_id == company_id).first()


def delivery_of_company(db: Session, delivery_id: int, company_id: int):
    """Yetkazishni ota (buyurtma) orqali tekshiradi — Delivery'da
    company_id ustuni yo'q (M2)."""
    from models import Delivery, Order
    return (db.query(Delivery)
            .join(Order, Order.id == Delivery.order_id)
            .filter(Delivery.id == delivery_id,
                    Order.company_id == company_id).first())


def employee_of_company(db: Session, emp_id: int, company_id: int):
    """Xodimni FAQAT shu korxona ichidan topadi.

    2026-09-18 — M1. Xodim endpointlari faqat id bo'yicha ishlardi, ya'ni
    A korxona admini B korxona xodimini tahrirlashi, o'chirishi, avans
    yozishi yoki unga telefon+PIN belgilashi mumkin edi.

    Topilmasa None qaytaradi — chaqiruvchi 404 beradi. Ataylab 404, 403
    emas: boshqa korxonada bunday id borligini ham oshkor qilmaslik uchun."""
    return db.query(Employee).filter(
        Employee.id == emp_id, Employee.company_id == company_id).first()


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
            full_name="Bosh Administrator",
            company_id=DEFAULT_COMPANY_ID
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
