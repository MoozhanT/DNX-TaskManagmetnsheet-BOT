"""توابع مشترک بین API، بات و scheduler برای کار با تسک‌ها."""

from datetime import datetime, timedelta
from typing import Optional

import models
from config import REMINDER_OFFSET_MINUTES


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
