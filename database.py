"""
PenoDecorPro ERP — Ma'lumotlar bazasiga ulanish
================================================
Local: SQLite (penodecor_erp.db)
Railway: PostgreSQL (DATABASE_URL environment variable)
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

# Railway da DATABASE_URL environment variable bo'ladi
# Local da SQLite ishlatiladi
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./penodecor_erp.db"
)

# Railway PostgreSQL URL ni to'g'irlash
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Engine yaratish
if "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    Base.metadata.create_all(bind=engine)
    print("✅ Baza va jadvallar yaratildi!")


if __name__ == "__main__":
    init_database()
