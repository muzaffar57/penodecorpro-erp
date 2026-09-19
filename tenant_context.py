"""
tenant_context.py — so'rov davomidagi "joriy korxona" konteksti va
SQLAlchemy darajasidagi AVTOMATIK tenant filtri.

NIMA UCHUN KERAK
----------------
M1–M8 davomida 519 ta so'rovga qo'lda `company_id` filtri qo'yildi. Bu
ishladi, lekin mo'rt: BITTA unutilgan `db.query()` yetadi va bir
korxonaning ma'lumoti boshqasiga ko'rinadi. Amalda shu xato sinfi besh
marta takrorlandi (M4, M5, M6, M7 va F1a).

Bu modul himoyani QO'LDAN OLIB, arxitekturaga o'tkazadi: joriy so'rovda
korxona ma'lum bo'lsa, SQLAlchemy'ning HAR BIR ORM `SELECT` iga
avtomatik `WHERE company_id = :joriy` qo'shiladi. Funksiya filtr qo'yishni
unutsa ham ma'lumot sizib chiqmaydi.

QANDAY ISHLAYDI
---------------
  • `set_current_company(cid)` — autentifikatsiyadan keyin chaqiriladi
    (`auth.get_current_user`), korxonani so'rov kontekstiga yozadi.
  • `do_orm_execute` hodisasi — har bir ORM so'roviga
    `with_loader_criteria` orqali shart qo'shadi.
  • Kontekst bo'sh bo'lsa (login, ishga tushish migratsiyalari, cron,
    kunlik backup) — filtr QO'LLANMAYDI, ya'ni eski xatti-harakat
    saqlanadi. Bu ATAYLAB: fon vazifalari jimgina buzilmasin.
  • `system_context()` — tizim amallari uchun vaqtincha o'chirish.

XAVFSIZLIK CHEGARASI
--------------------
Bu filtr ORM `SELECT` larini qamraydi. U QAMRAMAYDI:
  • xom SQL (`text(...)`) — loyihada faqat migratsiya va diagnostika,
    ular alohida tekshirilgan;
  • YOZISH — u `models._tenant_guard` va `company_id NOT NULL` bilan
    himoyalangan (M8/F1).
Shuning uchun bu qatlam mavjud qo'lda qo'yilgan filtrlarni O'RNINI
BOSMAYDI, ularning ustiga qo'shimcha to'r bo'ladi.

YOQISH
------
Muhit o'zgaruvchisi: TENANT_FILTER=1  (standart holatda O'CHIQ).
Ataylab o'chiq: avval staging'da tasdiqlanadi, keyin yoqiladi.
"""
import os
from contextlib import contextmanager

# MUHIM QAROR (2026-09-19, jonli sinovdan keyin):
# Dastlab `contextvars` ishlatilgan edi, lekin u ISHLAMADI — FastAPI
# sinxron bog'liqliklarni alohida oqimda (threadpool) ishga tushiradi va
# har biriga kontekstning NUSXASINI beradi; Starlette'ning
# `BaseHTTPMiddleware` i ham qiymatni pastga o'tkazmaydi. Natijada filtr
# yoqilgan bo'lsa ham hech qachon qo'llanmadi.
#
# Endi korxona SESSIYA OBYEKTINING O'ZIGA (`Session.info`) yoziladi.
# FastAPI bitta so'rovda `get_db` ni bir marta chaqiradi, ya'ni butun
# so'rov davomida AYNI sessiya ishlatiladi — va obyekt oqimlar orasida
# bemalol o'tadi. Fon vazifalari o'z sessiyasini yaratadi, unda bu
# qiymat bo'lmaydi — filtr qo'llanmaydi, eski xatti-harakat saqlanadi.
_KEY = "tenant_company_id"

# Filtr yoqilganmi
ENABLED = os.getenv("TENANT_FILTER", "0") == "1"

# Statistika — staging'da tekshirish uchun
_stats = {"filtered": 0, "skipped_no_context": 0, "skipped_system": 0}


def set_current_company(db, company_id):
    """So'rovning korxonasini SESSIYAGA bog'laydi (autentifikatsiyadan keyin)."""
    try:
        db.info[_KEY] = company_id
    except Exception:
        pass


def get_current_company(db):
    try:
        return db.info.get(_KEY)
    except Exception:
        return None


def reset_current_company(db):
    try:
        db.info.pop(_KEY, None)
    except Exception:
        pass


@contextmanager
def system_context(db):
    """Tizim amali — filtr shu sessiyada vaqtincha o'chadi
    (backup, migratsiya, cron, platforma diagnostikasi)."""
    prev = get_current_company(db)
    reset_current_company(db)
    try:
        yield
    finally:
        if prev is not None:
            set_current_company(db, prev)


def get_stats():
    return dict(_stats)


def install(Session):
    """SQLAlchemy sessiyasiga avtomatik filtrni o'rnatadi."""
    from sqlalchemy import event
    from sqlalchemy.orm import with_loader_criteria
    import models as _m

    # Filtrlanadigan modellar: `company_id` ustuni BOR bo'lganlar.
    # Ota orqali aniqlanadiganlar (Payment, Delivery va h.k.) bu yerda
    # qamralmaydi — ular uchun mavjud qo'lda qo'yilgan filtrlar ishlaydi.
    # Global filtrdan ATAYLAB chetlatilgan modellar.
    #
    # `ErrorLog` (2026-09-19, Faza 3 dan keyin jonli sinovda aniqlangan):
    # unda `company_id` ustuni bor, lekin u NULL bo'lishi MUMKIN va NULL
    # aynan "platforma xatosi" degani — fon vazifasi, ishga tushish yoki
    # login oldidagi xato. Global filtr `company_id = N` shartini qo'shsa,
    # NULL qatorlar kesilib ketadi va tizim egasi platforma xatolarini
    # umuman ko'rmay qoladi (M7 dan keyingi holat qaytadi).
    # Bu jadvalning kirish nazorati `crud.get_error_logs()` da ATAYLAB
    # "o'z korxonasi YOKI NULL" tarzida yozilgan — shuning uchun bu yerda
    # ikkinchi marta cheklash kerak emas va zararli.
    EXCLUDED_FROM_FILTER = {"ErrorLog"}

    tenant_models = []
    seen = set()
    for mod_name in ("models", "production_models"):
        try:
            mod = __import__(mod_name)
        except Exception:
            continue
        for obj in vars(mod).values():
            if not isinstance(obj, type):
                continue
            if not hasattr(obj, "__tablename__") or not hasattr(obj, "company_id"):
                continue
            if obj.__name__ in seen or obj.__name__ in EXCLUDED_FROM_FILTER:
                continue
            seen.add(obj.__name__)
            tenant_models.append(obj)

    @event.listens_for(Session, "do_orm_execute")
    def _apply_tenant_filter(orm_execute_state):
        if not ENABLED:
            return
        if not orm_execute_state.is_select:
            return
        # Ichki yuklash (lazy load) va maxsus belgilangan so'rovlarni tashlab ketmaymiz —
        # ular ham filtrlanishi kerak. Lekin ataylab "tizim" deb belgilanganini o'tkazamiz.
        if orm_execute_state.execution_options.get("skip_tenant_filter"):
            _stats["skipped_system"] += 1
            return
        sess = orm_execute_state.session
        cid = sess.info.get(_KEY) if sess is not None else None
        if cid is None:
            _stats["skipped_no_context"] += 1
            return
        _stats["filtered"] += 1
        for model in tenant_models:
            orm_execute_state.statement = orm_execute_state.statement.options(
                with_loader_criteria(model, model.company_id == cid,
                                     include_aliases=True)
            )

    return len(tenant_models)
