"""
سرویس بات تلگرام «DNX Task Manager Bot» — روی سروری با دسترسی مستقیم به تلگرام اجرا می‌شود
(بک‌اند اصلی روی سرور دیگری است که ممکن است تلگرام رویش فیلتر باشد).

این سرویس:
  1. با aiogram به تلگرام poll می‌زند و دستورهای کاربر را می‌گیرد، و برای هرکدام یکی از
     مسیرهای /internal/* بک‌اند اصلی را صدا می‌زند (به‌جای دسترسی مستقیم به دیتابیس).
  2. یک API کوچک (POST /relay/send) بالا می‌آورد تا بک‌اند اصلی بتواند یادآوری تسک‌ها را
     از طریق آن برای کاربر در تلگرام ارسال کند.

دستورهای در دسترس کاربر همان‌هایی هستند که قبلاً مستقیم روی بک‌اند بودند:
  /start                          ثبت‌نام عضو (اولین پیام به بات)
  /addtask عنوان | تاریخ (اختیاری)  افزودن تسک برای خودِ فرستنده
  /mytasks                        لیست تسک‌های بازِ خودِ فرستنده
  /done شناسه                     تکمیل یکی از تسک‌های خودِ فرستنده
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import httpx
import jdatetime
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
IRAN_API_BASE_URL = os.environ.get("IRAN_API_BASE_URL", "").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")

# اختیاری: اگر ست شده باشد، تسک‌های ساخته‌شده با /addtask به تب «new task» گوگل‌شیت هم اضافه می‌شوند
# (نگاه کن به apps_script_new_task.gs.txt برای نصب طرف گوگل‌شیت)
SHEET_APPEND_URL = os.environ.get("SHEET_APPEND_URL", "")
SHEET_APPEND_SECRET = os.environ.get("SHEET_APPEND_SECRET", "")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده است")
if not IRAN_API_BASE_URL:
    raise RuntimeError("IRAN_API_BASE_URL تنظیم نشده است")
if not INTERNAL_API_KEY:
    raise RuntimeError("INTERNAL_API_KEY تنظیم نشده است")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

_http = httpx.AsyncClient(base_url=IRAN_API_BASE_URL, headers={"X-Internal-Key": INTERNAL_API_KEY}, timeout=15)


_PERSIAN_MONTH_NAMES = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def _format_jalali_datetime(dt: datetime) -> str:
    jalali_date = jdatetime.date.fromgregorian(date=dt.date())
    month_name = _PERSIAN_MONTH_NAMES[jalali_date.month - 1]
    return f"{jalali_date.day} {month_name} {jalali_date.year} ساعت {dt.strftime('%H:%M')}"


def _first_name(full_name: str) -> str:
    return full_name.strip().split()[0] if full_name.strip() else full_name


def _format_task_line(task: dict) -> str:
    due = task.get("due_date")
    due_text = _format_jalali_datetime(datetime.fromisoformat(due)) if due else "بدون موعد"
    short_id = task["id"].split("_", 1)[1]
    return f"• [{short_id}] {task['title']} — موعد: {due_text}"


def _parse_due_date(text: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


async def _append_to_new_task_sheet(*, title: str, owner: str, due_date: Optional[datetime]) -> None:
    """تسک تازه‌ساخته‌شده با /addtask را به تب «new task» گوگل‌شیت هم اضافه می‌کند (برای بررسی/تأیید دستی)."""
    if not SHEET_APPEND_URL:
        return
    payload = {
        "secret": SHEET_APPEND_SECRET,
        "title": title,
        "owner": owner,
        "end_date": _format_jalali_datetime(due_date) if due_date else "",
        "status": "پیشنهادی (از بات)",
    }
    try:
        # آدرس اجرای Apps Script با یک 302 به یک لینک محتوای امضاشده ریدایرکت می‌شود؛
        # باید همان را دنبال کنیم تا پاسخ واقعی (نه فقط ریدایرکت) را ببینیم
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.post(SHEET_APPEND_URL, json=payload)
            response.raise_for_status()
    except Exception:
        logger.exception("افزودن تسک به تب new task گوگل‌شیت ناموفق بود")


@router.message(Command("start"))
async def cmd_start(message: Message):
    response = await _http.post(
        "/internal/members/register",
        json={
            "telegram_chat_id": message.chat.id,
            "telegram_username": message.from_user.username if message.from_user else None,
            "full_name": message.from_user.full_name if message.from_user else str(message.chat.id),
        },
    )
    response.raise_for_status()
    member = response.json()
    await message.answer(
        f"سلام {_first_name(member['full_name'])} جان! ثبت شدی و از این به بعد یادآوری تسک‌ها برایت ارسال می‌شود.\n\n"
        "دستورهای در دسترس:\n"
        "/addtask عنوان | 2026-07-20 10:00 — افزودن تسک (تاریخ اختیاری)\n"
        "/mytasks — لیست تسک‌های باز من\n"
        "/done شناسه — تکمیل یک تسک (شناسه از /mytasks)"
    )


@router.message(Command("addtask"))
async def cmd_addtask(message: Message):
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

    response = await _http.post(
        "/internal/tasks",
        json={
            "telegram_chat_id": message.chat.id,
            "title": title,
            "due_date": due_date.isoformat() if due_date else None,
        },
    )
    if response.status_code == 404:
        await message.answer("اول باید /start بزنی تا ثبت‌نام بشوی.")
        return
    response.raise_for_status()
    await message.answer(f"تسک ساخته شد:\n{_format_task_line(response.json())}")

    owner_name = message.from_user.full_name if message.from_user else str(message.chat.id)
    await _append_to_new_task_sheet(title=title, owner=owner_name, due_date=due_date)


@router.message(Command("mytasks"))
async def cmd_mytasks(message: Message):
    response = await _http.get("/internal/tasks", params={"telegram_chat_id": message.chat.id})
    response.raise_for_status()
    tasks = response.json()
    name = _first_name(message.from_user.full_name) if message.from_user else ""
    if not tasks:
        await message.answer(f"{name} جان، تسک بازی نداری. 🎉")
        return
    lines = "\n".join(_format_task_line(t) for t in tasks)
    await message.answer(f"{name} جان، این‌ها تسک‌های باز تو هستن:\n{lines}")


@router.message(Command("done"))
async def cmd_done(message: Message):
    args = (message.text or "").split(maxsplit=1)
    short_id = args[1].strip() if len(args) > 1 else ""
    if not short_id:
        await message.answer("فرمت درست: /done شناسه (شناسه‌ای که در /mytasks دیدی)")
        return

    response = await _http.post(f"/internal/tasks/{short_id}/done", json={"telegram_chat_id": message.chat.id})
    if response.status_code == 404:
        await message.answer("تسکی با این شناسه که مال خودت باشد پیدا نشد.")
        return
    response.raise_for_status()
    await message.answer(f"انجام شد ✅ {response.json()['title']}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    polling_task = asyncio.create_task(dp.start_polling(bot))
    yield
    polling_task.cancel()
    await bot.session.close()
    await _http.aclose()


app = FastAPI(title="DNX Task Manager Bot — Telegram relay", lifespan=lifespan)


class RelaySendRequest(BaseModel):
    chat_id: int
    text: str


@app.post("/relay/send")
async def relay_send(payload: RelaySendRequest, x_internal_key: str = Header(default="")):
    """بک‌اند اصلی (روی سرور دیگر) برای ارسال یادآوری تسک این مسیر را صدا می‌زند."""
    if x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="دسترسی غیرمجاز")
    await bot.send_message(payload.chat_id, payload.text)
    return {"ok": True}


@app.get("/")
def root():
    return {"status": "ok", "message": "DNX Task Manager Bot — Telegram relay روشن است ✅"}
