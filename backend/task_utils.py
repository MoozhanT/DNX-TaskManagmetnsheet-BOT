"""توابع مشترک بین API، بات و scheduler برای کار با تسک‌ها."""

from datetime import datetime, timedelta
from typing import Optional

import jdatetime

import models
from config import REMINDER_OFFSET_MINUTES

_PERSIAN_MONTH_NAMES = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def format_jalali_datetime(dt: Optional[datetime]) -> str:
    """تاریخ میلادی را برای نمایش به کاربر به تاریخ جلالی تبدیل می‌کند."""
    if dt is None:
        return "بدون موعد"
    jalali_date = jdatetime.date.fromgregorian(date=dt.date())
    month_name = _PERSIAN_MONTH_NAMES[jalali_date.month - 1]
    return f"{jalali_date.day} {month_name} {jalali_date.year} ساعت {dt.strftime('%H:%M')}"


def first_name(full_name: str) -> str:
    """اسم کوچک را از اسم کامل جدا می‌کند، برای لحن دوستانه‌تر پیام‌ها (مثلاً «موژان جان»)."""
    return full_name.strip().split()[0] if full_name.strip() else full_name


def compute_reminder_at(due_date: Optional[datetime]) -> Optional[datetime]:
    """زمان یادآوری را از روی موعد تسک حساب می‌کند (موعد منهای REMINDER_OFFSET_MINUTES)."""
    if due_date is None:
        return None
    return due_date - timedelta(minutes=REMINDER_OFFSET_MINUTES)


def apply_due_date(task: models.Task, due_date: Optional[datetime]) -> None:
    """موعد تسک را عوض می‌کند و زمان یادآوری/پرچم reminded را همراهش به‌روز می‌کند."""
    task.due_date = due_date
    task.reminder_at = compute_reminder_at(due_date)
    task.reminded = False


def format_task_line(task: models.Task) -> str:
    due = task.due_date.strftime("%Y-%m-%d %H:%M") if task.due_date else "بدون موعد"
    short_id = task.id.split("_", 1)[1]
    return f"• [{short_id}] {task.title} — موعد: {due}"


def find_task_by_short_id(db, short_id: str) -> Optional[models.Task]:
    """کاربر در چت معمولاً فقط بخش کوتاه id (بدون پیشوند t_) را می‌فرستد."""
    lookup_id = short_id if short_id.startswith("t_") else f"t_{short_id}"
    return db.query(models.Task).filter(models.Task.id == lookup_id).first()
