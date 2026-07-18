import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./penodecor_erp.db")

# Railway postgres:// → postgresql+pg8000://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+pg8000://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+pg8000://", 1)

if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _sql_type_for_column(col):
    """SQLAlchemy ustun turini Postgres/SQLite uchun mos SQL turiga aylantiradi."""
    from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, Numeric

    t = col.type
    if isinstance(t, String):
        length = getattr(t, "length", None) or 255
        return f"VARCHAR({length})"
    if isinstance(t, Text):
        return "TEXT"
    if isinstance(t, Boolean):
        return "BOOLEAN"
    if isinstance(t, Integer):
        return "INTEGER"
    if isinstance(t, Float):
        return "FLOAT"
    if isinstance(t, Numeric):
        precision = getattr(t, "precision", 12) or 12
        scale = getattr(t, "scale", 2) or 2
        return f"NUMERIC({precision},{scale})"
    if isinstance(t, DateTime):
        return "TIMESTAMP"
    return "TEXT"  # noma'lum tur bo'lsa, xavfsiz variant


def sync_missing_columns():
    """Kod (models.py) bilan haqiqiy baza jadvallarini solishtiradi.

    Agar modelda bor, lekin bazada yo'q ustun topilsa — uni AVTOMATIK qo'shadi
    (faqat ADD COLUMN, hech qachon o'chirish yoki o'zgartirish qilmaydi).

    Xavfsizlik: faqat NULL bo'lishi mumkin bo'lgan (nullable) ustunlarni qo'shadi,
    chunki mavjud jadvalga NOT NULL ustun standart qiymatsiz qo'shib bo'lmaydi.
    Har bir ustun alohida try/except bilan o'ralgan — bittasi xato bersa ham,
    server ishga tushishda to'xtab qolmaydi.
    """
    from sqlalchemy import inspect, text

    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
    except Exception as e:
        print(f"⚠️ Ustunlarni tekshirishda xato (o'tkazib yuborildi): {e}")
        return

    added = []
    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue  # Yangi jadval — create_all() allaqachon to'liq yaratgan
        try:
            existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        except Exception as e:
            print(f"⚠️ '{table_name}' jadvalini tekshirishda xato: {e}")
            continue

        for col in table.columns:
            if col.name in existing_cols:
                continue
            if not col.nullable and col.default is None and col.server_default is None:
                # NOT NULL va standart qiymatsiz ustunni xavfsiz qo'sha olmaymiz — o'tkazib yuboramiz
                print(f"⚠️ '{table_name}.{col.name}' qo'lda qo'shilishi kerak (NOT NULL, standart qiymatsiz)")
                continue
            try:
                sql_type = _sql_type_for_column(col)
                default_clause = ""
                # MUHIM: standart qiymatni ham SQL darajasida yozamiz — aks holda
                # ESKI qatorlar bu ustunda NULL bo'lib qoladi (Python darajasidagi
                # "default=" faqat YANGI qatorlarga ta'sir qiladi, eskilarga emas).
                if col.default is not None and getattr(col.default, "is_scalar", False):
                    val = col.default.arg
                    if isinstance(val, bool):
                        default_clause = f" DEFAULT {'TRUE' if val else 'FALSE'}"
                    elif isinstance(val, (int, float)):
                        default_clause = f" DEFAULT {val}"
                    elif isinstance(val, str):
                        escaped = val.replace("'", "''")
                        default_clause = f" DEFAULT '{escaped}'"
                with engine.connect() as conn:
                    conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {col.name} {sql_type}{default_clause}'))
                    conn.commit()
                added.append(f"{table_name}.{col.name}")
            except Exception as e:
                print(f"⚠️ '{table_name}.{col.name}' ustunini qo'shishda xato: {e}")

    if added:
        print(f"✅ Avtomatik qo'shilgan ustunlar: {', '.join(added)}")
    else:
        print("✅ Barcha ustunlar bazada mavjud — qo'shish shart emas")


def init_database():
    Base.metadata.create_all(bind=engine)
    print("✅ Baza va jadvallar yaratildi!")
    sync_missing_columns()

if __name__ == "__main__":
    init_database()
