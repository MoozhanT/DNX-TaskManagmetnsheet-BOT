"""
مدل‌های دیتابیس:
  - admin_users   (حساب ورود به پنل وب)
  - members       (اعضای تیم، هرکدام می‌توانند به یک چت تلگرام وصل باشند)
  - tasks         (تسک‌ها، هرکدام به یک عضو اختصاص داده می‌شوند)
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, String, ForeignKey, DateTime, BigInteger
from sqlalchemy.orm import relationship

from database import Base


def new_id(prefix: str) -> str:
    """ساخت یک id کوتاه و یکتا، مثل m_ab12cd34 یا t_9f0a1b2c"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class AdminUser(Base):
    """حساب ورود به پنل وب (مدیریت/گزارش‌گیری)؛ از اعضای تیم که با بات کار می‌کنند جداست."""

    __tablename__ = "admin_users"

    id = Column(String, primary_key=True, default=lambda: new_id("a"))
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Member(Base):
    """یک عضو تیم. رکورد با اولین باری که کاربر به بات دستور /start می‌زند ساخته می‌شود."""

    __tablename__ = "members"

    id = Column(String, primary_key=True, default=lambda: new_id("m"))
    # قبل از /start این مقدار خالی است (نمی‌شود از قبل چت‌آیدی کسی را حدس زد)
    telegram_chat_id = Column(BigInteger, unique=True, nullable=True)
    telegram_username = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    # اگر True باشد، در آینده می‌تواند دستورهای مدیریتی بات (مثل تخصیص تسک به دیگران) را اجرا کند
    is_admin_bot = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    tasks = relationship(
        "Task",
        back_populates="assignee",
        foreign_keys="Task.assignee_id",
    )


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: new_id("t"))
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)

    assignee_id = Column(String, ForeignKey("members.id"), nullable=True)
    created_by_id = Column(String, ForeignKey("members.id"), nullable=True)

    status = Column(String, nullable=False, default="pending")  # pending | done

    due_date = Column(DateTime, nullable=True)
    # زمان دقیقی که باید یادآوری ارسال شود (= due_date منهای REMINDER_OFFSET_MINUTES)
    reminder_at = Column(DateTime, nullable=True)
    # وقتی یادآوری یک‌بار ارسال شد True می‌شود تا دوباره ارسال نشود
    reminded = Column(Boolean, nullable=False, default=False)

    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assignee = relationship("Member", back_populates="tasks", foreign_keys=[assignee_id])
    created_by = relationship("Member", foreign_keys=[created_by_id])
