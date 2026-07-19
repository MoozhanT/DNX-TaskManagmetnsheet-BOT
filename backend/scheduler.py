"""
Scheduler یادآوری تسک‌ها: هر چند دقیقه یک‌بار (REMINDER_CHECK_INTERVAL_MINUTES) بررسی می‌کند
کدام تسک‌ها به زمان یادآوری‌شان رسیده‌اند و برای مسئولشان در تلگرام پیام می‌فرستد.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import bot as bot_module
import models
from config import REMINDER_CHECK_INTERVAL_MINUTES
from database import SessionLocal

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


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
                    await bot_module.send_reminder(task.assignee.telegram_chat_id, text)
                except Exception:
                    logger.exception("ارسال یادآوری برای تسک %s ناموفق بود", task.id)
        db.commit()
    finally:
        db.close()


def start():
    if bot_module.bot is None:
        logger.warning("TELEGRAM_BOT_TOKEN تنظیم نشده؛ scheduler یادآوری اجرا نمی‌شود.")
        return
    scheduler.add_job(check_reminders, "interval", minutes=REMINDER_CHECK_INTERVAL_MINUTES)
    scheduler.start()


def shutdown():
    if scheduler.running:
        scheduler.shutdown()
