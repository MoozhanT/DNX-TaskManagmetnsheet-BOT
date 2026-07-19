"""
اتصال به دیتابیس.
پیش‌فرض: SQLite (یک فایل ساده به اسم app.db کنار همین پروژه)

آدرس دیتابیس از متغیر محیطی DATABASE_URL هم قابل تنظیم است — این برای
Docker لازم است تا app.db داخل یک volume (مثلاً /app/data/app.db) ذخیره شود
و با هر rebuild پاک نشود. اگر این متغیر ست نشده باشد، همان رفتار قبلی
(فایل app.db کنار پروژه) ادامه پیدا می‌کند.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./app.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    # فقط برای SQLite لازم است؛ روی دیتابیس‌های دیگر (Postgres و ...) این گزینه نامعتبر است
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """این تابع در هر درخواست، یک session دیتابیس می‌سازد و در پایان می‌بندد."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
