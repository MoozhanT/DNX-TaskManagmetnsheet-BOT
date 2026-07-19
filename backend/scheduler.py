"""
دو job زمان‌بندی‌شده در همین پراسه‌ی بک‌اند اجرا می‌شوند:
  - check_reminders: هر چند دقیقه یک‌بار (REMINDER_CHECK_INTERVAL_MINUTES) تسک‌هایی که موعد
    یادآوری‌شان رسیده را پیدا می‌کند و ارسال پیامش را به سرویس بات (روی سرور دیگر) می‌سپارد.
  - sheet_sync.sync_sheet_tasks: هر چند دقیقه یک‌بار (SHEET_SYNC_INTERVAL_MINUTES) تسک‌های
    گوگل‌شیت تیم را به دیتابیس این پروژه همگام می‌کند.
"""

import logging
from datetime import datetime

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import models
import sheet_sync
from config import (
    GERMANY_RELAY_URL,
    INTERNAL_API_KEY,
    REMINDER_CHECK_INTERVAL_MINUTES,
    SHEET_CSV_URL,
    SHEET_SYNC_INTERVAL_MINUTES,
)
from database import SessionLocal

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _send_via_relay(chat_id: int, text: str) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{GERMANY_RELAY_URL.rstrip('/')}/relay/send",
            json={"chat_id": chat_id, "text": text},
            headers={"X-Internal-Key": INTERNAL_API_KEY},
        )
        response.raise_for_status()


async def check_reminders():
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        due_tasks = (
            db.query(models.Task)
            .filter(
                models.Task.status == "pending",
                models.Task.reminded.is_(False),
                models.Task.reminder_at.isnot(None),
                models.Task.reminder_at <= now,
            )
            .all()
        )
        for task in due_tasks:
            # پرچم را همین‌جا ست می‌کنیم تا حتی اگر ارسال پیام خطا بدهد، دوباره تلاش نکنیم و کاربر را اسپم نکنیم
            task.reminded = True
            if task.assignee and task.assignee.telegram_chat_id:
                due_text = task.due_date.strftime("%Y-%m-%d %H:%M") if task.due_date else "—"
                text = f"⏰ یادآوری تسک: {task.title}\nموعد: {due_text}"
                try:
                    await _send_via_relay(task.assignee.telegram_chat_id, text)
                except Exception:
                    logger.exception("ارسال یادآوری برای تسک %s ناموفق بود", task.id)
        db.commit()
    finally:
        db.close()


async def _sync_sheet_safely():
    try:
        await sheet_sync.sync_sheet_tasks()
    except Exception:
        logger.exception("همگام‌سازی گوگل‌شیت ناموفق بود")


def start():
    if GERMANY_RELAY_URL:
        scheduler.add_job(check_reminders, "interval", minutes=REMINDER_CHECK_INTERVAL_MINUTES)
    else:
        logger.warning("GERMANY_RELAY_URL تنظیم نشده؛ یادآوری‌های تلگرام غیرفعال می‌مانند.")

    if SHEET_CSV_URL:
        scheduler.add_job(
            _sync_sheet_safely,
            "interval",
            minutes=SHEET_SYNC_INTERVAL_MINUTES,
            next_run_time=datetime.utcnow(),
        )
    else:
        logger.warning("SHEET_CSV_URL تنظیم نشده؛ همگام‌سازی گوگل‌شیت غیرفعال می‌ماند.")

    if scheduler.get_jobs():
        scheduler.start()


def shutdown():
    if scheduler.running:
        scheduler.shutdown()
