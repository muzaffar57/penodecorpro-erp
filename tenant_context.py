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
import contextvars
import os
from contextlib import contextmanager

_current_company: contextvars.ContextVar = contextvars.ContextVar(
    "current_company_id", default=None)

# Filtr yoqilganmi
ENABLED = os.getenv("TENANT_FILTER", "0") == "1"

# Statistika — staging'da tekshirish uchun
_stats = {"filtered": 0, "skipped_no_context": 0, "skipped_system": 0}


def set_current_company(company_id):
    """Joriy so'rovning korxonasini belgilaydi (autentifikatsiyadan keyin)."""
    return _current_company.set(company_id)


def get_current_company():
    return _current_company.get()


def reset_current_company(token=None):
    if token is not None:
        _current_company.reset(token)
    else:
        _current_company.set(None)


@contextmanager
def system_context():
    """Tizim amali — filtr vaqtincha o'chadi (backup, migratsiya, cron)."""
    token = _current_company.set(None)
    try:
        yield
    finally:
        _current_company.reset(token)


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
            if obj.__name__ in seen:
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
        cid = _current_company.get()
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
