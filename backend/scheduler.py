"""
سه job زمان‌بندی‌شده در همین پراسه‌ی بک‌اند اجرا می‌شوند:
  - check_reminders: هر چند دقیقه یک‌بار (REMINDER_CHECK_INTERVAL_MINUTES) تسک‌هایی که موعد
    یادآوری‌شان رسیده را پیدا می‌کند و ارسال پیامش را به سرویس بات (روی سرور دیگر) می‌سپارد.
  - send_daily_digest: هر روز ساعت ۹:۳۰ به‌وقت تهران، برای هرکس یک خلاصه از تسک‌های باز
    امروزش با ددلاین‌هایشان می‌فرستد.
  - sheet_sync.sync_sheet_tasks: هر چند دقیقه یک‌بار (SHEET_SYNC_INTERVAL_MINUTES) تسک‌های
    گوگل‌شیت تیم را به دیتابیس این پروژه همگام می‌کند (و برای تسک‌های تازه، خودش فوری اطلاع می‌دهد).
"""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import models
import sheet_sync
from config import (
    GERMANY_RELAY_URL,
    REMINDER_CHECK_INTERVAL_MINUTES,
    SHEET_CSV_URL,
    SHEET_SYNC_INTERVAL_MINUTES,
)
from database import SessionLocal
from notify import send_via_relay

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
                    await send_via_relay(task.assignee.telegram_chat_id, text)
                except Exception:
                    logger.exception("ارسال یادآوری برای تسک %s ناموفق بود", task.id)
        db.commit()
    finally:
        db.close()


async def send_daily_digest():
    db = SessionLocal()
    try:
        members = db.query(models.Member).filter(models.Member.telegram_chat_id.isnot(None)).all()
        for member in members:
            tasks = (
                db.query(models.Task)
                .filter(models.Task.assignee_id == member.id, models.Task.status == "pending")
                .order_by(models.Task.due_date.is_(None), models.Task.due_date)
                .all()
            )
            if not tasks:
                continue
            lines = []
            for task in tasks:
                due_text = task.due_date.strftime("%Y-%m-%d %H:%M") if task.due_date else "بدون موعد"
                lines.append(f"• {task.title} — موعد: {due_text}")
            text = "☀️ صبح بخیر! تسک‌های باز تو:\n" + "\n".join(lines)
            try:
                await send_via_relay(member.telegram_chat_id, text)
            except Exception:
                logger.exception("ارسال خلاصه‌ی روزانه برای عضو %s ناموفق بود", member.id)
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
        scheduler.add_job(send_daily_digest, CronTrigger(hour=9, minute=30, timezone="Asia/Tehran"))
    else:
        logger.warning("GERMANY_RELAY_URL تنظیم نشده؛ یادآوری‌ها و خلاصه‌ی روزانه غیرفعال می‌مانند.")

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
