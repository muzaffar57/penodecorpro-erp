"""
PenoDecorPro ERP — Auth (Login) tizimi
========================================
Cookie asosida sessiya, rol bo'yicha ruxsatlar.

Rollar (kech118 — egasi qarori: rollarni admin o'zi boshqaradi): korxona rollari `rollar` jadvalida, ruxsat katalogi va
tayyor rollar (Admin, Menejer, Omborchi, Moliyachi) — `ruxsatlar.py`; marshrut qorovuli — `ruxsat(band, amal)`.
Admin (`users.role == ADMIN`) — hamma narsa.
"""

import hashlib
import secrets
import bcrypt
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import get_db
from models import User, UserRole, Rol


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


# ============================================================
# kech116 (U-01, O'LCHANGAN — audit kech114, jonli `/logs`): mijozning HAQIQIY IP manzili
# ============================================================
# Railway ilovaga ichki proksi orqali ulanadi — `request.client.host` doim 100.64.0.x (CGNAT, 23 xil manzil 100 ta kirishda).
# Natija: «Tizim jurnallari» dagi IP ustuni hech narsa bildirmasdi, kirish cheklovi (5 xato → 15 daqiqa) esa BITTA proksi
# manzilidan kelayotgan HAMMA foydalanuvchini (boshqa korxonalarni ham) birga bloklashi mumkin edi.
# `uvicorn --proxy-headers --forwarded-allow-ips='*'` YECHIM EMAS (O'LCHANGAN, uvicorn 0.30.6 `ProxyHeadersMiddleware`):
# '*' da `X-Forwarded-For` ning ENG CHAP (mijoz o'zi yozishi mumkin bo'lgan) manzilini oladi — soxta sarlavha bilan IP
# cheklovini aylanib o'tish mumkin bo'lardi. Qoida (texnik — Claude):
#   * ulanish manzili ichki (xususiy / CGNAT / loopback / link-local) bo'lsa — so'rov proksidan keldi: `X-Forwarded-For`
#     dagi ENG O'NG ochiq manzil (chekka proksi uni o'zi qo'shadi; mijoz yuborgan soxta qiymatlar undan CHAPDA qoladi),
#     bo'lmasa `X-Real-IP` (ochiq bo'lsa), aks holda ulanish manzili;
#   * ulanish manzili ochiq (to'g'ridan-to'g'ri ulanish) — sarlavhalarga ISHONILMAYDI.
_ICHKI_TARMOQLAR = None


def _ichki_tarmoqlar():
    global _ICHKI_TARMOQLAR
    if _ICHKI_TARMOQLAR is None:
        import ipaddress
        _ICHKI_TARMOQLAR = [ipaddress.ip_network(x) for x in (
            "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16",
            "0.0.0.0/8", "::1/128", "fc00::/7", "fe80::/10", "::/128")]
    return _ICHKI_TARMOQLAR


def _toza_ip(qiymat):
    """Sarlavhadagi bitta manzil → normallashgan IP matni (port, qavslar olib tashlanadi) yoki None (IP emas)."""
    import ipaddress
    t = (qiymat or "").strip().strip('"')
    if not t or len(t) > 64:
        return None
    if t.startswith("["):                       # [2001:db8::1]:443
        t = t[1:t.find("]")] if "]" in t else t[1:]
    elif t.count(":") == 1:                     # 203.0.113.7:5678
        t = t.split(":", 1)[0]
    try:
        ip = ipaddress.ip_address(t)
    except ValueError:
        return None
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    return str(ip)


def _ichki_manzilmi(ip_matn) -> bool:
    """IP ichki tarmoqdami (proksi / konteyner / loopback). IP bo'lmagan qiymat — ichki EMAS (ishonilmaydi)."""
    import ipaddress
    t = _toza_ip(ip_matn)
    if not t:
        return False
    ip = ipaddress.ip_address(t)
    return any(ip in n for n in _ichki_tarmoqlar() if n.version == ip.version)


def mijoz_ip(request) -> Optional[str]:
    """kech116 (U-01): so'rov yuborgan mijozning haqiqiy IP manzili (yuqoridagi qoida). Kirish jurnali va kirish cheklovi
    shundan foydalanadi."""
    ulanish = request.client.host if getattr(request, "client", None) else None
    if not ulanish or not _ichki_manzilmi(ulanish):
        return ulanish
    xff = request.headers.get("x-forwarded-for", "") or ""
    for qism in reversed(xff.split(",")):
        ip = _toza_ip(qism)
        if ip and not _ichki_manzilmi(ip):
            return ip
    real = _toza_ip(request.headers.get("x-real-ip", "") or "")
    if real and not _ichki_manzilmi(real):
        return real
    return ulanish


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

    # 2026-09-19 — Faza 1: joriy so'rovning korxonasini kontekstga yozamiz.
    # Shundan keyin `tenant_context` moduli HAR BIR ORM so'roviga avtomatik
    # `company_id` shartini qo'shadi — funksiya filtrni unutsa ham ma'lumot
    # sizib chiqmaydi. Kontekst bo'sh bo'lsa (login, cron, migratsiya)
    # filtr qo'llanmaydi, ya'ni fon vazifalari avvalgidek ishlaydi.
    if user is not None:
        try:
            from tenant_context import set_current_company
            set_current_company(db, getattr(user, "company_id", None))
        except Exception:
            pass
        _korxona_bloklanganmi(db, getattr(user, "company_id", None),
                              platforma=getattr(user, "is_platform_admin", False),
                              yop=lambda: delete_session(db, token))
    return user


def _korxona_bloklanganmi(db: Session, company_id, platforma=False, yop=None):
    """kech111 — PLATFORMA bloki (egasi QARORI kech109 / kech110): korxonasi bloklangan (qo'lda yoki obuna
    muddatidan 3 kun keyin avtomatik — `obuna.py`, YAGONA manba) foydalanuvchi / hodim so'rovi rad etiladi.

    HAR SO'ROVDA tekshiriladi: ochiq sessiyalar ham darhol to'xtaydi (kunlik ish o'tkazib yuborilsa ham muddat
    o'tgani kirishda hisoblanadi). Rad — 403, `obuna.BLOK_SARLAVHA` belgisi bilan: `/api/` — JSON sababi bilan,
    sahifa — `/login?b=…` (hodim paneli — `/hodim/login?b=…`) ga yo'naltiriladi (`main.custom_http_exception_handler`).
    Shu sessiya o'chiriladi (`yop`) — ochilgandan keyin qayta kiriladi. Platforma admini HECH QACHON bloklanmaydi.
    Tekshiruvning o'zi xato bersa (baza nosozligi) — kirish TO'XTATILMAYDI: blok to'lov chorasi, xavfsizlik
    chegarasi emas; bitta nosozlik barcha mijozlarni tashqarida qoldirmasin."""
    if platforma or company_id is None:
        return
    try:
        import obuna as _obuna
        rad = _obuna.kirish_rad_sababi(db, company_id)
    except Exception:
        return
    if not rad:
        return
    xabar, belgi = rad
    if yop is not None:
        try:
            yop()
        except Exception:
            pass
    raise HTTPException(status_code=403, detail=xabar, headers={_obuna.BLOK_SARLAVHA: belgi})


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

# kech118 (ROLLAR VA RUXSATLAR — egasi QARORI 15:23): marshrutlar endi ROL RUXSATI bilan qo'riqlanadi — `ruxsat(band,
# amal)` (katalog va tayyor rollar — `ruxsatlar.py`, YAGONA manba). Eski rol-ro'yxatli qorovullar (admin_or_manager,
# admin_or_financier, …) olib tashlandi: har marshrut → (band, amal) xaritasi va tayyor rollar ESKI huquqlardan
# hisoblangan (work/k119/tayinlash.py); tekshiruv — tools/test_rollar.py (marshrut × eski rol kirish matritsasi).
# Qolganlari: `admin_only` — FAQAT Admin (foydalanuvchilar va rollar boshqaruvi — topshirilmaydi), `all_staff` — har
# qanday korxona foydalanuvchisi, `platform_admin_only` — platforma egasi.
import ruxsatlar as _rx

# Eski rol turlari (`users.role`) nomlari — rad sababi uchun (`require_role`). kech118 nomlar lug'ati (egasi qarori):
# login roli «Menejer» (ilgari «Hodim» — u endi oylik oladigan ishchi).
ROL_NOMI = {
    UserRole.ADMIN: "Admin",
    UserRole.MANAGER: "Menejer",
    UserRole.ACCOUNTANT: "Moliyachi",
    UserRole.WAREHOUSE: "Omborchi",
    UserRole.MASTER: "Usta",
}


def rollar_matni(rollar) -> str:
    """[UserRole, ...] → «Admin va Menejer» / «Admin, Menejer va Omborchi» (takrorsiz, berilgan tartibda)."""
    nomlar = []
    for r in rollar:
        n = ROL_NOMI.get(r) or str(getattr(r, "value", r))
        if n not in nomlar:
            nomlar.append(n)
    if len(nomlar) <= 1:
        return "".join(nomlar)
    return ", ".join(nomlar[:-1]) + " va " + nomlar[-1]


def require_role(allowed_roles: list):
    """Eski rol turi bo'yicha qorovul (faqat `admin_only` va `all_staff` uchun qoldi)."""
    def checker(
        request: Request,
        db: Session = Depends(get_db)
    ) -> User:
        user = require_login(request, db)
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Bu bo'lim faqat {rollar_matni(allowed_roles)} uchun ochiq"
            )
        return user
    return checker


_RUXSAT_QOROVULLARI = {}


def _ruxsat_qorovuli(tur: str, juftlar: tuple):
    """Rol ruxsati qorovuli (FastAPI bog'lamasi). `tur`: 'bitta' — bitta (band, amal); 'biri' — birortasi yetadi
    (sahifalar); 'hammasi' — hammasi kerak. Har talab uchun BITTA funksiya (eslab qolinadi): FastAPI bir so'rovda bir xil
    bog'lamani bir marta chaqiradi; nomi (`ruxsat__band__amal`) — marshrutlar xaritasi va testlar uchun."""
    for b, a in juftlar:
        if b not in _rx.BANDLAR or a not in _rx.BANDLAR[b]["amallar"]:
            raise ValueError(f"ruxsat katalogida yo'q: {b}.{a}")
    kalit = (tur, juftlar)
    f = _RUXSAT_QOROVULLARI.get(kalit)
    if f is not None:
        return f

    def qorovul(request: Request, db: Session = Depends(get_db)) -> User:
        user = require_login(request, db)
        bor = [_rx.bormi(user, b, a) for b, a in juftlar]
        if (any(bor) if tur == "biri" else all(bor)):
            return user
        b, a = next(j for j, x in zip(juftlar, bor) if not x) if tur != "biri" else juftlar[0]
        raise HTTPException(status_code=403, detail=_rx.rad_matni(b, a))

    nom = "ruxsat__" + ("__yoki__" if tur == "biri" else "__va__").join(f"{b}__{a}" for b, a in juftlar)
    qorovul.__name__ = qorovul.__qualname__ = nom
    qorovul.ruxsat_talabi = (tur, juftlar)
    _RUXSAT_QOROVULLARI[kalit] = qorovul
    return qorovul


def ruxsat(band: str, amal: str):
    """Marshrut qorovuli: rolda (band, amal) ruxsati bo'lsin. Ishlatilishi: `current_user=Depends(auth.ruxsat("buyurtma",
    "yaratish"))`. Admin — doim o'tadi. Yo'q — 403 («Sizning rolingizda … ruxsati yo'q»)."""
    return _ruxsat_qorovuli("bitta", ((band, amal),))


def ruxsat_biri(*juftlar):
    """Sahifa qorovuli: berilgan (band, amal) juftlaridan BIRORTASI yetadi."""
    return _ruxsat_qorovuli("biri", tuple(juftlar))


def ruxsat_hammasi(*juftlar):
    """Qorovul: berilgan (band, amal) juftlarining HAMMASI kerak (masalan buyurtma foydasi — Tannarx va Buyurtmalar)."""
    return _ruxsat_qorovuli("hammasi", tuple(juftlar))


# Tayyor checker funksiyalar — main.py da ishlatiladi
def platform_admin_only(request: Request, db: Session = Depends(get_db)) -> User:
    """PLATFORMA admini — SaaS egasi (Faza 3).

    Farqi: `admin_only` — bu KORXONA admini. Har bir mijozning admini
    shu huquqqa ega, ya'ni u o'z korxonasini to'liq boshqaradi. Lekin
    platforma darajasidagi amallar (Telegram bot tokeni sozlamasi,
    butun bazani Telegram'ga yuborish) hech qanday tenant admini uchun
    ochiq bo'lmasligi kerak — M8 auditida aynan shu aniqlangan edi.
    """
    user = require_login(request, db)
    if not getattr(user, "is_platform_admin", False):
        raise HTTPException(
            status_code=403,
            detail="Bu amal faqat platforma administratori uchun")
    return user


def admin_only(request: Request, db: Session = Depends(get_db)) -> User:
    """FAQAT Admin — foydalanuvchilar va rollar boshqaruvi (rolga topshirilmaydi: aks holda istalgan rol o'zini Admin
    qila olardi)."""
    return require_role([UserRole.ADMIN])(request, db)


def all_staff(request: Request, db: Session = Depends(get_db)) -> User:
    return require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.ACCOUNTANT, UserRole.MASTER, UserRole.WAREHOUSE])(request, db)


# ============================================================
# Foydalanuvchi CRUD (faqat admin uchun)
# ============================================================

def _login_egasi(db: Session, username: str):
    """kech108 (K107-2): login (`User.username`) BUTUN TIZIM bo'yicha yagona (`ix_users_username`) — egasi har qanday
    korxonadan. Tizim so'rovi (`skip_tenant_filter`): TENANT_FILTER=1 da global filtr so'rovni joriy korxona bilan
    cheklardi va boshqa korxonadagi band login ko'rinmasdi (INSERT → unique xatosi → 500). Faqat bandlikni tekshirish
    uchun (foydalanuvchi ma'lumoti chaqiruvchiga qaytmaydi — `create_user` faqat None / emasligini ko'radi)."""
    return (db.query(User).execution_options(skip_tenant_filter=True)
            .filter(User.username == username).first())


def create_user(db: Session, username: str, password: str,
                role: UserRole, full_name: str = "",
                company_id: int = None, rol_id: int = None) -> User:
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
    # Username band emasligini tekshiramiz.
    # kech108 (K107-2, O'LCHANGAN): login BUTUN TIZIM bo'yicha yagona (`ix_users_username`) — tekshiruv ham butun tizim
    # bo'yicha (tizim so'rovi, `skip_tenant_filter`). Ilgari TENANT_FILTER=1 da global filtr so'rovni joriy korxona bilan
    # cheklardi: boshqa korxonadagi login ko'rinmas, INSERT unique xatosi bilan 500 berardi (400 o'rniga).
    existing = _login_egasi(db, username)
    if existing:
        raise HTTPException(status_code=400, detail="Bu username band")

    # kech118 (ROLLAR): har yangi foydalanuvchi korxonaning ROLIGA biriktiriladi. `rol_id` berilsa — shu rol (korxonaniki
    # bo'lishi SHART), `role` rolga moslanadi (Admin roli — ADMIN); berilmasa — `role` turining tayyor roli.
    if rol_id is not None:
        rol = rol_of_company(db, rol_id, company_id)
        if rol is None:
            raise HTTPException(status_code=400, detail="Rol topilmadi")
        role = rol_turi(rol)
    else:
        rol = tayyor_rol(db, company_id, _rx.ENUM_ROL.get(getattr(role, "value", role), "menejer"))

    user = User(
        company_id=company_id,
        username=username,
        password_hash=hash_password(password),
        role=role,
        rol_id=rol.id if rol is not None else None,
        full_name=full_name,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # kech108 (K107-2): parallel yaratish — tekshiruvdan keyin boshqa so'rov shu loginni yozib ulgurgan
        db.rollback()
        if _login_egasi(db, username) is not None:
            raise HTTPException(status_code=400, detail="Bu username band")
        raise
    db.refresh(user)
    return user


# ============================================================
# Rollar (kech118 — egasi QARORI 15:23: «Hodim rollarini admin o'zi boshqaradigan qilaylik»)
# ============================================================

def rol_of_company(db: Session, rol_id, company_id: int):
    """Rol FAQAT shu korxonadan (boshqa korxonaniki / yo'q — None)."""
    try:
        rid = int(rol_id)
    except (TypeError, ValueError):
        return None
    return db.query(Rol).filter(Rol.id == rid, Rol.company_id == company_id).first()


def rol_turi(rol) -> UserRole:
    """Rol → `users.role` qiymati: Admin roli — ADMIN; tayyor rollar — eski turi; o'zi yaratilgan — MANAGER (faqat
    ma'lumot uchun: huquq rol ruxsatlaridan olinadi)."""
    return UserRole(_rx.ROL_ENUM.get(rol.kod or "", "manager"))


def tayyor_rollar(db: Session, company_id: int, kodlar=None) -> dict:
    """Korxonaning tayyor rollari {kod: Rol}; yo'qlari andozadan yaratiladi (COMMIT qiladi — chaqiruvchida yozilmagan
    o'zgarish qolmasin). `kodlar` — qaysilari (standart: Admin, Menejer, Omborchi, Moliyachi). Parallel yaratishda
    (noyoblik xatosi) — qayta o'qiladi. Nom band bo'lsa (admin shu nomli o'z rolini yaratgan) — «Menejer (tayyor)»."""
    kodlar = tuple(kodlar or _rx.TAYYOR_TARTIB)
    bor = {r.kod: r for r in db.query(Rol).filter(Rol.company_id == company_id, Rol.kod.in_(kodlar)).all()}
    yoq = [k for k in kodlar if k not in bor]
    if not yoq:
        return bor
    nomlar = {(n or "").strip().lower() for (n,) in db.query(Rol.nom).filter(Rol.company_id == company_id).all()}
    for k in yoq:
        a = _rx.TAYYOR_ROLLAR[k]
        nom = a["nom"] if a["nom"].lower() not in nomlar else f"{a['nom']} (tayyor)"
        nomlar.add(nom.lower())
        db.add(Rol(company_id=company_id, nom=nom, tavsif=a["tavsif"], kod=k,
                   ruxsatlar=_rx.ruxsatlar_json(a["ruxsatlar"]), created_at=datetime.utcnow()))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return {r.kod: r for r in db.query(Rol).filter(Rol.company_id == company_id, Rol.kod.in_(kodlar)).all()}


def tayyor_rol(db: Session, company_id: int, kod: str):
    return tayyor_rollar(db, company_id, (kod,)).get(kod)


def rol_foydalanuvchilari(db: Session, rol_id: int, company_id: int) -> list:
    return (db.query(User).filter(User.company_id == company_id, User.rol_id == rol_id)
            .order_by(User.username).all())


def rol_biriktir(db: Session, user_id: int, rol_id: int, company_id: int, bajaruvchi) -> tuple:
    """Foydalanuvchiga rol biriktiradi. Qoidalar: faqat o'z korxonasi; O'Z rolini o'zgartirib bo'lmaydi (Admin o'zini
    tasodifan Admin emas qilib qo'ymasin); korxonada kamida bitta FAOL Admin qoladi. Qaytaradi: (user, eski_rol_nomi)."""
    user = db.query(User).filter(User.id == user_id, User.company_id == company_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    rol = rol_of_company(db, rol_id, company_id)
    if rol is None:
        raise HTTPException(status_code=400, detail="Rol topilmadi")
    if bajaruvchi is not None and user.id == bajaruvchi.id:
        raise HTTPException(status_code=400, detail="O'z rolingizni o'zgartira olmaysiz")
    yangi_tur = rol_turi(rol)
    if user.role == UserRole.ADMIN and yangi_tur != UserRole.ADMIN and user.is_active:
        boshqa = (db.query(User).filter(User.company_id == company_id, User.role == UserRole.ADMIN,
                                        User.is_active == True, User.id != user.id).count())   # noqa: E712
        if not boshqa:
            raise HTTPException(status_code=400, detail="Korxonada kamida bitta faol Admin qolishi kerak")
    eski = user.rol_nomi
    user.rol_id = rol.id
    user.role = yangi_tur
    user.__dict__.pop("_ruxsat_kesh", None)
    db.flush()
    return user, eski


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
                    company_id: int = None, saqlanadigan_token: str = None) -> bool:
    """Parolni yangilaydi.

    2026-09-18 — M1: company_id shart (eng jiddiy topilma). Ilgari faqat id
    bo'yicha qidirilardi — A korxona admini B korxona adminining parolini
    almashtirib, o'sha korxonaga to'liq kirish huquqini olishi mumkin edi.

    kech116 (G6-06, O'LCHANGAN — audit kech114): parol almashtirilgach o'sha odamning boshqa kompyuter / telefondagi
    kirishi YOPILMASDI (8 soatgacha ishlayverardi) — ishdan ketgan odamni «parolini almashtirib» chiqarib bo'lmasdi.
    Endi shu foydalanuvchining HAMMA sessiyalari parol bilan BITTA tranzaksiyada o'chiriladi; faqat
    `saqlanadigan_token` (o'z parolini almashtirayotgan odamning JORIY sessiyasi) qoladi."""
    from models import UserSession
    if not company_id:
        raise HTTPException(
            status_code=500,
            detail="Ichki xato: parol o'zgartirishda korxona aniqlanmadi.")
    user = db.query(User).filter(
        User.id == user_id, User.company_id == company_id).first()
    if not user:
        return False
    user.password_hash = hash_password(new_password)
    _sq = db.query(UserSession).filter(UserSession.user_id == user.id)
    if saqlanadigan_token:
        _sq = _sq.filter(UserSession.token != saqlanadigan_token)
    _sq.delete(synchronize_session=False)
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
    if employee is not None:
        # kech111 — korxonasi bloklangan hodim paneli ham yopiladi (`_korxona_bloklanganmi`).
        _korxona_bloklanganmi(db, getattr(employee, "company_id", None),
                              yop=lambda: delete_employee_session(db, token))
    return employee


def inventory_of_company(db: Session, item_id: int, company_id: int):
    """Materialni FAQAT shu korxona ichidan topadi (M3)."""
    from models import Inventory
    return db.query(Inventory).filter(
        Inventory.id == item_id, Inventory.company_id == company_id).first()


def recipe_of_company(db: Session, recipe_id: int, company_id: int):
    """Retseptni FAQAT shu korxona ichidan topadi (M3)."""
    from models import Recipe
    return db.query(Recipe).filter(
        Recipe.id == recipe_id, Recipe.company_id == company_id).first()


def supplier_of_company(db: Session, supplier_id: int, company_id: int):
    """Ta'minotchini FAQAT shu korxona ichidan topadi (M3)."""
    from models import Supplier
    return db.query(Supplier).filter(
        Supplier.id == supplier_id, Supplier.company_id == company_id).first()


def purchase_of_company(db: Session, purchase_id: int, company_id: int):
    """Xaridni ota (material) orqali tekshiradi — InventoryPurchase'da
    company_id ustuni yo'q (M3)."""
    from models import InventoryPurchase, Inventory
    return (db.query(InventoryPurchase)
            .join(Inventory, Inventory.id == InventoryPurchase.inventory_id)
            .filter(InventoryPurchase.id == purchase_id,
                    Inventory.company_id == company_id).first())


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


def finished_product_of_company(db: Session, fp_id: int, company_id: int):
    """Tayyor mahsulotni FAQAT shu korxona ichidan topadi (M4).

    2026-09-18 — M4. Tayyor mahsulot endpointlari faqat id bo'yicha
    ishlardi (`/api/finished/{fp_id}/...`), ya'ni A korxona xodimi
    B korxonaning mahsulotini ko'rishi, tahrirlashi, sotishi, brak
    qilishi yoki o'chirishi mumkin edi.

    Topilmasa None qaytaradi — chaqiruvchi 404 beradi. Ataylab 404,
    403 emas: boshqa korxonada bunday id borligini oshkor qilmaslik
    uchun."""
    from models import FinishedProduct
    return db.query(FinishedProduct).filter(
        FinishedProduct.id == fp_id,
        FinishedProduct.company_id == company_id).first()


def cash_transaction_of_company(db: Session, tx_id: int, company_id: int):
    """Kassa yozuvini FAQAT shu korxona ichidan topadi (M6)."""
    from models import CashTransaction
    return db.query(CashTransaction).filter(
        CashTransaction.id == tx_id,
        CashTransaction.company_id == company_id).first()


def expense_of_company(db: Session, tx_id: int, company_id: int):
    """Xarajat tranzaksiyasini FAQAT shu korxona ichidan topadi (M6)."""
    from models import ExpenseTransaction
    return db.query(ExpenseTransaction).filter(
        ExpenseTransaction.id == tx_id,
        ExpenseTransaction.company_id == company_id).first()


def transport_expense_of_company(db: Session, exp_id: int, company_id: int):
    """Transport xarajatini FAQAT shu korxona ichidan topadi (M6)."""
    from models import TransportExpense
    return db.query(TransportExpense).filter(
        TransportExpense.id == exp_id,
        TransportExpense.company_id == company_id).first()


def obligation_of_company(db: Session, obligation_id: int, company_id: int):
    """Doimiy majburiyatni FAQAT shu korxona ichidan topadi (M6)."""
    from models import RecurringObligation
    return db.query(RecurringObligation).filter(
        RecurringObligation.id == obligation_id,
        RecurringObligation.company_id == company_id).first()


def supplier_payment_of_company(db: Session, payment_id: int, company_id: int):
    """Ta'minotchiga to'lovni ota (Supplier) orqali tekshiradi —
    SupplierPayment'da company_id ustuni yo'q (M6)."""
    from models import SupplierPayment, Supplier
    return (db.query(SupplierPayment)
            .join(Supplier, Supplier.id == SupplierPayment.supplier_id)
            .filter(SupplierPayment.id == payment_id,
                    Supplier.company_id == company_id).first())


def master_of_company(db: Session, master_id: int, company_id: int):
    """Ustani FAQAT shu korxona ichidan topadi (M5).

    2026-09-18 — M5. Usta endpointlari faqat id bo'yicha ishlardi
    (`/api/masters/{master_id}`, `.../kpi`, `.../kpi-detail`), ya'ni
    A korxona admini B korxonaning ustasini o'qishi, tahrirlashi,
    KPI foizini o'zgartirishi va o'chirishi mumkin edi — jonli
    sinovda tasdiqlangan.

    Topilmasa None qaytaradi — chaqiruvchi 404 beradi. Ataylab 404,
    403 emas: boshqa korxonada bunday id borligini oshkor qilmaslik
    uchun."""
    from models import Master
    return db.query(Master).filter(
        Master.id == master_id, Master.company_id == company_id).first()


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
