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
  /mytasks                        لیست تسک‌های بازِ خودِ فرستنده (با دکمه‌ی انجام‌شد/تمدید)
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
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
IRAN_API_BASE_URL = os.environ.get("IRAN_API_BASE_URL", "").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")

# درخواست تمدید مهلت مستقیم اعمال نمی‌شود؛ برای این یوزرنیم‌ها (مجید، موژان) پیام تأیید
# می‌رود و فقط با تأیید یکی از آن‌ها مهلت واقعاً عوض می‌شود
APPROVER_USERNAMES = [
    u.strip() for u in os.environ.get("APPROVER_USERNAMES", "mamokhtarnia,moozhantehrani").split(",") if u.strip()
]

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

# رنگ/ایموجی وضعیت بر اساس فاصله تا موعد
STATUS_EMOJI = {"overdue": "🔴", "soon": "🟡", "later": "🟢", "none": "⚪️"}


def _due_status(due_date: Optional[datetime]) -> str:
    if due_date is None:
        return "none"
    days_left = (due_date - datetime.utcnow()).days
    if days_left < 0:
        return "overdue"
    if days_left <= 3:
        return "soon"
    return "later"


def _format_jalali_datetime(dt: datetime) -> str:
    jalali_date = jdatetime.date.fromgregorian(date=dt.date())
    month_name = _PERSIAN_MONTH_NAMES[jalali_date.month - 1]
    return f"{jalali_date.day} {month_name} {jalali_date.year} ساعت {dt.strftime('%H:%M')}"


def _first_name(full_name: str) -> str:
    return full_name.strip().split()[0] if full_name.strip() else full_name


def _short_id(task_id: str) -> str:
    return task_id.split("_", 1)[1]


def _format_task_message(task: dict) -> str:
    due = task.get("due_date")
    due_dt = datetime.fromisoformat(due) if due else None
    emoji = STATUS_EMOJI[_due_status(due_dt)]
    due_text = _format_jalali_datetime(due_dt) if due_dt else "بدون موعد"
    return f"{emoji} <b>{task['title']}</b>\n<i>موعد: {due_text}</i>"


def _build_task_keyboard(task_id: str) -> InlineKeyboardMarkup:
    short_id = _short_id(task_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ انجام شد", callback_data=f"done:{short_id}"),
            InlineKeyboardButton(text="⏳ درخواست تمدید ۷ روز", callback_data=f"extend:{short_id}"),
        ]]
    )


def _build_approval_keyboard(short_id: str, requester_chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ تأیید تمدید", callback_data=f"approveext:{short_id}:{requester_chat_id}"),
            InlineKeyboardButton(text="❌ رد درخواست", callback_data=f"rejectext:{short_id}:{requester_chat_id}"),
        ]]
    )


async def _get_approvers() -> list[dict]:
    """chat_id مسئولان تأیید (مجید، موژان) را از بک‌اند می‌گیرد؛ کسانی که هنوز /start نزده‌اند رد می‌شوند."""
    approvers = []
    for username in APPROVER_USERNAMES:
        try:
            response = await _http.get("/internal/members/lookup", params={"username": username})
            if response.status_code == 404:
                logger.warning("مسئول تأیید '%s' هنوز /start نزده", username)
                continue
            response.raise_for_status()
            approvers.append(response.json())
        except Exception:
            logger.exception("خطا در پیدا کردن مسئول تأیید '%s'", username)
    return approvers


async def _get_own_task(chat_id: int, short_id: str) -> Optional[dict]:
    """تسک باز خودِ کاربر را با شناسه‌ی کوتاه پیدا می‌کند (برای گرفتن عنوان/موعد قبل از ارسال درخواست تمدید)."""
    response = await _http.get("/internal/tasks", params={"telegram_chat_id": chat_id})
    response.raise_for_status()
    for task in response.json():
        if _short_id(task["id"]) == short_id:
            return task
    return None


def _format_task_line(task: dict) -> str:
    due = task.get("due_date")
    due_text = _format_jalali_datetime(datetime.fromisoformat(due)) if due else "بدون موعد"
    return f"• [{_short_id(task['id'])}] {task['title']} — موعد: {due_text}"


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
    task = response.json()
    await message.answer(
        f"تسک ساخته شد:\n{_format_task_message(task)}",
        parse_mode="HTML",
        reply_markup=_build_task_keyboard(task["id"]),
    )

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

    def _sort_key(t: dict):
        due = t.get("due_date")
        return datetime.fromisoformat(due) if due else datetime.max

    tasks.sort(key=_sort_key)
    await message.answer(f"📋 {name} جان، این‌ها تسک‌های باز تو هستن:")
    for task in tasks:
        await message.answer(
            _format_task_message(task),
            parse_mode="HTML",
            reply_markup=_build_task_keyboard(task["id"]),
        )


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


@router.callback_query(F.data.startswith("done:"))
async def handle_done_callback(callback: CallbackQuery):
    short_id = callback.data.split(":", 1)[1]
    response = await _http.post(f"/internal/tasks/{short_id}/done", json={"telegram_chat_id": callback.message.chat.id})
    if response.status_code == 404:
        await callback.answer("این تسک پیدا نشد (شاید قبلاً تمام شده).", show_alert=True)
        return
    response.raise_for_status()
    title = response.json()["title"]
    await callback.message.edit_text(f"✅ <b>{title}</b>\n<i>انجام شد</i>", parse_mode="HTML")
    await callback.answer("تسک به‌عنوان انجام‌شده ثبت شد ✅")

    requester_name = callback.from_user.full_name if callback.from_user else str(callback.message.chat.id)
    for approver in await _get_approvers():
        if approver["telegram_chat_id"] == callback.message.chat.id:
            continue  # اگر خودِ مجید/موژان تسک خودشان را دان کردند، به خودشان دوباره پیام نرود
        try:
            await bot.send_message(
                approver["telegram_chat_id"],
                f"☑️ {requester_name} تسک زیر رو انجام‌شده علامت زد:\n<b>{title}</b>",
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("اطلاع‌رسانی انجام‌شدن تسک به مسئول تأیید ناموفق بود")


@router.callback_query(F.data.startswith("extend:"))
async def handle_extend_callback(callback: CallbackQuery):
    """تمدید مهلت مستقیم اعمال نمی‌شود؛ یک درخواست تأیید برای مسئولان (مجید، موژان) ارسال می‌شود."""
    short_id = callback.data.split(":", 1)[1]
    requester_chat_id = callback.message.chat.id
    task = await _get_own_task(requester_chat_id, short_id)
    if task is None:
        await callback.answer("این تسک پیدا نشد (شاید قبلاً تمام شده).", show_alert=True)
        return

    requester_name = callback.from_user.full_name if callback.from_user else str(requester_chat_id)
    due = task.get("due_date")
    due_text = _format_jalali_datetime(datetime.fromisoformat(due)) if due else "بدون موعد"
    request_text = (
        f"🙋 <b>{requester_name}</b> می‌خواد مهلت تسک زیر رو ۷ روز تمدید کنه:\n"
        f"<b>{task['title']}</b>\n"
        f"<i>موعد فعلی: {due_text}</i>"
    )

    approvers = await _get_approvers()
    if not approvers:
        await callback.answer("هیچ‌کدوم از مسئولان تأیید هنوز /start نزده‌اند؛ فعلاً امکان تمدید نیست.", show_alert=True)
        return

    sent_to_anyone = False
    for approver in approvers:
        try:
            await bot.send_message(
                approver["telegram_chat_id"],
                request_text,
                parse_mode="HTML",
                reply_markup=_build_approval_keyboard(short_id, requester_chat_id),
            )
            sent_to_anyone = True
        except Exception:
            logger.exception("ارسال درخواست تمدید به مسئول تأیید ناموفق بود")

    if sent_to_anyone:
        await callback.answer("درخواست تمدید برای تأیید ارسال شد ⏳")
    else:
        await callback.answer("ارسال درخواست تمدید ناموفق بود، دوباره امتحان کن.", show_alert=True)


@router.callback_query(F.data.startswith("approveext:"))
async def handle_approve_extend_callback(callback: CallbackQuery):
    _, short_id, requester_chat_id = callback.data.split(":")
    response = await _http.post(
        f"/internal/tasks/{short_id}/extend",
        json={"telegram_chat_id": int(requester_chat_id), "days": 7},
    )
    if response.status_code == 404:
        await callback.answer("این تسک دیگر پیدا نشد.", show_alert=True)
        return
    response.raise_for_status()
    task = response.json()
    due_text = _format_jalali_datetime(datetime.fromisoformat(task["due_date"]))
    approver_name = callback.from_user.full_name if callback.from_user else ""

    await callback.message.edit_text(
        callback.message.html_text + f"\n\n✅ <b>تأیید شد</b> توسط {approver_name}",
        parse_mode="HTML",
    )
    await callback.answer("تأیید شد ✅")

    try:
        await bot.send_message(
            int(requester_chat_id),
            f"✅ درخواست تمدید مهلت تسک <b>{task['title']}</b> تأیید شد.\nموعد جدید: <i>{due_text}</i>",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("اطلاع‌رسانی تأیید تمدید به درخواست‌دهنده ناموفق بود")


@router.callback_query(F.data.startswith("rejectext:"))
async def handle_reject_extend_callback(callback: CallbackQuery):
    _, short_id, requester_chat_id = callback.data.split(":")
    approver_name = callback.from_user.full_name if callback.from_user else ""

    await callback.message.edit_text(
        callback.message.html_text + f"\n\n❌ <b>رد شد</b> توسط {approver_name}",
        parse_mode="HTML",
    )
    await callback.answer("رد شد ❌")

    try:
        await bot.send_message(
            int(requester_chat_id),
            "❌ درخواست تمدید مهلت تسکت رد شد.",
        )
    except Exception:
        logger.exception("اطلاع‌رسانی رد تمدید به درخواست‌دهنده ناموفق بود")


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
