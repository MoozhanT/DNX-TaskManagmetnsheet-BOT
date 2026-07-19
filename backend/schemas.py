"""شکل داده‌ای که API می‌گیرد یا برمی‌گرداند (Pydantic)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ───────────────────────── احراز هویت پنل وب ─────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminSetup(BaseModel):
    username: str
    password: str


class AdminLogin(BaseModel):
    username: str
    password: str


# ───────────────────────── اعضای تیم ─────────────────────────

class MemberOut(BaseModel):
    id: str
    full_name: str
    telegram_username: Optional[str] = None
    is_admin_bot: bool = False
    # عمداً telegram_chat_id اینجا نیست تا در پاسخ API لو نرود

    class Config:
        from_attributes = True


class MemberUpdate(BaseModel):
    full_name: Optional[str] = None
    is_admin_bot: Optional[bool] = None


# ───────────────────────── تسک‌ها ─────────────────────────

class TaskOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: str
    due_date: Optional[datetime] = None
    reminded: bool
    completed_at: Optional[datetime] = None
    created_at: datetime
    assignee: Optional[MemberOut] = None

    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    due_date: Optional[datetime] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = None


# ───────────────────── مسیرهای داخلی (سرویس بات، /internal/*) ─────────────────────
# این‌ها فقط توسط سرویس بات (روی سرور دیگر) با کلید مشترک INTERNAL_API_KEY صدا زده می‌شوند.

class BotMemberRegister(BaseModel):
    telegram_chat_id: int
    telegram_username: Optional[str] = None
    full_name: str


class BotMemberOut(BaseModel):
    id: str
    full_name: str


class BotTaskCreate(BaseModel):
    telegram_chat_id: int
    title: str
    due_date: Optional[datetime] = None


class BotTaskOut(BaseModel):
    id: str
    title: str
    due_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class BotTaskDone(BaseModel):
    telegram_chat_id: int
