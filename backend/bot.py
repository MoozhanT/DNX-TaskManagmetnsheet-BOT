"""
بات تلگرام برای مدیریت تسک — داخل همان پراسه‌ی بک‌اند (با FastAPI lifespan) اجرا می‌شود.

دستورهای در دسترس:
  /start                          ثبت‌نام عضو (اولین پیام به بات)
  /addtask عنوان | تاریخ (اختیاری)  افزودن تسک برای خودِ فرستنده
  /mytasks                        لیست تسک‌های بازِ خودِ فرستنده
  /done شناسه                     تکمیل یکی از تسک‌های خودِ فرستنده

تخصیص تسک به دیگران فقط از پنل وب انجام می‌شود (برای ساده ماندن بات در نسخه‌ی اول).
"""

import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command
from aiogram.types import Message

import models
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_PROXY_URL
from database import SessionLocal
from task_utils import apply_due_date, find_task_by_short_id, format_task_line

logger = logging.getLogger(__name__)

router = Router()

# اگر توکن تنظیم نشده باشد، bot=None می‌ماند و start_polling() بی‌اثر خارج می‌شود
# (این‌طوری پنل وب و API بدون توکن هم قابل تست هستند)
# اگر TELEGRAM_PROXY_URL ست شده باشد (مثلاً وقتی تلگرام روی این سرور فیلتر است)،
# درخواست‌های بات از طریق آن پراکسی (سرویس sshproxy در docker-compose) عبور می‌کنند
_session = AiohttpSession(proxy=TELEGRAM_PROXY_URL) if TELEGRAM_PROXY_URL else None
bot = Bot(token=TELEGRAM_BOT_TOKEN, session=_session) if TELEGRAM_BOT_TOKEN else None
dp = Dispatcher()
dp.include_router(router)


def _get_or_create_member(db, message: Message) -> models.Member:
    member = db.query(models.Member).filter(models.Member.telegram_chat_id == message.chat.id).first()
    if member is None:
        member = models.Member(
            telegram_chat_id=message.chat.id,
            telegram_username=message.from_user.username if message.from_user else None,
            full_name=(message.from_user.full_name if message.from_user else str(message.chat.id)),
        )
        db.add(member)
        db.commit()
        db.refresh(member)
    return member


def _parse_due_date(text: str):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


@router.message(Command("start"))
async def cmd_start(message: Message):
    db = SessionLocal()
    try:
        member = _get_or_create_member(db, message)
        await message.answer(
            f"سلام {member.full_name}! ثبت شدی و از این به بعد یادآوری تسک‌ها برایت ارسال می‌شود.\n\n"
            "دستورهای در دسترس:\n"
            "/addtask عنوان | 2026-07-20 10:00 — افزودن تسک (تاریخ اختیاری)\n"
            "/mytasks — لیست تسک‌های باز من\n"
            "/done شناسه — تکمیل یک تسک (شناسه از /mytasks)"
        )
    finally:
        db.close()


@router.message(Command("addtask"))
async def cmd_addtask(message: Message):
    db = SessionLocal()
    try:
        member = _get_or_create_member(db, message)
        args = (message.text or "").split(maxsplit=1)
        raw = args[1] if len(args) > 1 else ""
        if not raw.strip():
            await message.answer("فرمت درست: /addtask عنوان تسک | 2026-07-20 10:00 (بخش تاریخ اختیاری است)")
            return

        if "|" in raw:
            title_part, date_part = raw.split("|", 1)
        else:
            title_part, date_part = raw, ""

        title = title_part.strip()
        if not title:
            await message.answer("عنوان تسک نمی‌تواند خالی باشد.")
            return

        due_date = None
        date_text = date_part.strip()
        if date_text:
            due_date = _parse_due_date(date_text)
            if due_date is None:
                await message.answer("فرمت تاریخ نامعتبر است. از YYYY-MM-DD یا 'YYYY-MM-DD HH:MM' استفاده کن.")
                return

        task = models.Task(title=title, assignee_id=member.id, created_by_id=member.id)
        apply_due_date(task, due_date)
        db.add(task)
        db.commit()
        db.refresh(task)
        await message.answer(f"تسک ساخته شد:\n{format_task_line(task)}")
    finally:
        db.close()


@router.message(Command("mytasks"))
async def cmd_mytasks(message: Message):
    db = SessionLocal()
    try:
        member = _get_or_create_member(db, message)
        tasks = (
            db.query(models.Task)
            .filter(models.Task.assignee_id == member.id, models.Task.status == "pending")
            .order_by(models.Task.due_date.is_(None), models.Task.due_date)
            .all()
        )
        if not tasks:
            await message.answer("تسک بازی نداری. 🎉")
            return
        lines = "\n".join(format_task_line(t) for t in tasks)
        await message.answer(f"تسک‌های باز تو:\n{lines}")
    finally:
        db.close()


@router.message(Command("done"))
async def cmd_done(message: Message):
    db = SessionLocal()
    try:
        member = _get_or_create_member(db, message)
        args = (message.text or "").split(maxsplit=1)
        short_id = args[1].strip() if len(args) > 1 else ""
        if not short_id:
            await message.answer("فرمت درست: /done شناسه (شناسه‌ای که در /mytasks دیدی)")
            return

        task = find_task_by_short_id(db, short_id)
        if not task or task.assignee_id != member.id:
            await message.answer("تسکی با این شناسه که مال خودت باشد پیدا نشد.")
            return

        task.status = "done"
        task.completed_at = datetime.utcnow()
        db.commit()
        await message.answer(f"انجام شد ✅ {task.title}")
    finally:
        db.close()


async def start_polling():
    """در FastAPI lifespan به‌عنوان یک asyncio task اجرا می‌شود."""
    if bot is None:
        logger.warning("TELEGRAM_BOT_TOKEN تنظیم نشده؛ بات تلگرام اجرا نمی‌شود (فقط API/پنل وب فعال است).")
        return
    await dp.start_polling(bot)


async def send_reminder(chat_id: int, text: str) -> None:
    if bot is None:
        return
    await bot.send_message(chat_id, text)


async def shutdown():
    if bot is not None:
        await bot.session.close()
