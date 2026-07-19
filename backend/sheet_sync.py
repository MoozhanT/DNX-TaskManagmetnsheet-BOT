"""
همگام‌سازی یک‌طرفه از گوگل‌شیت مدیریت تسک‌های تیم به دیتابیس این پروژه.

فرض‌ها:
  - شیت با «هرکسی که لینک را دارد» قابل مشاهده است (فقط export CSV آن، بدون سرویس‌اکانت، خوانده می‌شود).
  - ستون‌های تب مربوطه به این ترتیب‌اند:
    [پرچم YES/NO, WBS Code, Company, Task/Activity, Description, Owner, Start Date, End Date, Status, ...]
  - ستون Owner اسم کوچک فارسی عضو است؛ OWNER_TELEGRAM_USERNAME آن را به یوزرنیم تلگرام وصل می‌کند.
    عضو باید قبلاً یک‌بار با /start در بات ثبت‌نام کرده باشد؛ وگرنه آن ردیف فعلاً رد می‌شود
    (در سینک بعدی، اگر ثبت‌نام کرده باشد، خودش اضافه می‌شود).
  - ستون End Date تاریخ جلالی بدون سال است (مثل «۱۵ مرداد»)؛ سال جلالی جاری فرض می‌شود.
  - تشخیص «همان تسک در سینک بعدی» از روی شماره‌ی ردیف در شیت انجام می‌شود (models.Task.sheet_row_key)،
    نه ستون WBS Code، چون WBS Code توی این شیت همیشه یکتا نیست (چند ردیف با یک عدد دیده شده).
"""

import csv
import io
import logging
import re
from datetime import datetime
from typing import Optional

import httpx
import jdatetime

import models
from config import SHEET_CSV_URL
from database import SessionLocal
from notify import send_via_relay
from task_utils import apply_due_date, first_name, format_jalali_datetime

logger = logging.getLogger(__name__)

# نگاشت اسم owner توی شیت به یوزرنیم تلگرام (بدون @، حروف کوچک برای مقایسه‌ی case-insensitive)
OWNER_TELEGRAM_USERNAME = {
    "پویا": "pouyaghahremaniii",
    "مهدی": "single_act",
    "امیر": "amirpirnazari",
    "عباس": "abbas_safaeee",
    "شایان": "sindex",
    "همایون": "homayoon43",
    "مجید": "mamokhtarnia",
    "سارا": "sarahssshh",
    "موژان": "moozhantehrani",
}

_PERSIAN_MONTHS = {
    "فروردین": 1, "اردیبهشت": 2, "خرداد": 3, "تیر": 4,
    "مرداد": 5, "شهریور": 6, "مهر": 7, "آبان": 8,
    "آذر": 9, "دی": 10, "بهمن": 11, "اسفند": 12,
}

_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

# ردیف‌هایی با این وضعیت، در پنل به‌عنوان «انجام‌شده» علامت می‌خورند
_DONE_STATUSES = {"پایان یافته", "کنسل شده"}

# ساعت پیش‌فرض موعد، وقتی شیت فقط تاریخ می‌دهد نه ساعت
_DEFAULT_DUE_HOUR = 18


def _parse_jalali_date(text: str) -> Optional[datetime]:
    """چیزی مثل '۱۵ مرداد' را با سال جلالی جاری به datetime میلادی تبدیل می‌کند."""
    text = text.translate(_DIGIT_MAP).strip()
    match = re.match(r"^(\d{1,2})\s+(\S+)$", text)
    if not match:
        return None
    day = int(match.group(1))
    month = _PERSIAN_MONTHS.get(match.group(2))
    if month is None:
        return None
    today_jalali = jdatetime.date.today()
    try:
        jalali_date = jdatetime.date(today_jalali.year, month, day)
    except ValueError:
        return None
    gregorian = jalali_date.togregorian()
    return datetime(gregorian.year, gregorian.month, gregorian.day, _DEFAULT_DUE_HOUR, 0)


async def _fetch_rows() -> list[list[str]]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(SHEET_CSV_URL)
        response.raise_for_status()
    return list(csv.reader(io.StringIO(response.text)))


async def sync_sheet_tasks() -> None:
    rows = await _fetch_rows()

    # (chat_id, اسم عضو, عنوان, موعد) برای تسک‌های تازه‌ساخته‌شده‌ی هنوز بازی که بعد از commit پیام‌شان ارسال می‌شود
    new_task_alerts: list[tuple[int, str, str, Optional[datetime]]] = []

    db = SessionLocal()
    try:
        for row_index, row in enumerate(rows):
            if len(row) < 9:
                continue
            _flag, wbs_code_raw, _company, title, description, owner, _start_date, end_date, status = row[:9]

            wbs_code = wbs_code_raw.strip()
            title = title.strip()
            owner = owner.strip()
            if not wbs_code.isdigit() or not title or not owner:
                continue  # هدر، ردیف جمع کل، یا ردیف ناقص

            username = OWNER_TELEGRAM_USERNAME.get(owner)
            if not username:
                logger.warning("owner ناشناخته در شیت (ردیف %s، WBS %s): %s", row_index, wbs_code, owner)
                continue

            member = (
                db.query(models.Member)
                .filter(models.Member.telegram_username.ilike(username))
                .first()
            )
            if not member:
                logger.info("عضو '%s' هنوز /start نزده؛ ردیف %s (WBS %s) فعلاً رد شد", owner, row_index, wbs_code)
                continue

            row_key = str(row_index)
            task = db.query(models.Task).filter(models.Task.sheet_row_key == row_key).first()
            is_new_task = task is None
            if is_new_task:
                task = models.Task(sheet_row_key=row_key, created_by_id=member.id)
                db.add(task)

            due_date = _parse_jalali_date(end_date.strip())
            if task.due_date != due_date:
                apply_due_date(task, due_date)

            status = status.strip()
            full_description = description.strip()
            if status:
                full_description = f"{full_description}\n[وضعیت در شیت: {status}]".strip()

            task.title = title
            task.description = full_description or None
            task.assignee_id = member.id

            new_status = "done" if status in _DONE_STATUSES else "pending"
            if task.status != new_status:
                task.status = new_status
                task.completed_at = datetime.utcnow() if new_status == "done" else None

            # فقط برای تسک‌های تازه و هنوز باز نوتیف بفرست؛ تسکی که از همان اول در شیت
            # «پایان یافته/کنسل شده» بوده چیز جدیدی برای اطلاع‌دادن ندارد
            if is_new_task and new_status == "pending" and member.telegram_chat_id:
                new_task_alerts.append((member.telegram_chat_id, member.full_name, title, due_date))

        db.commit()
    finally:
        db.close()

    for chat_id, member_full_name, title, due_date in new_task_alerts:
        due_text = format_jalali_datetime(due_date)
        text = f"📋 {first_name(member_full_name)} جان، یه تسک جدید از شیت برات اضافه شد:\n{title}\nموعد: {due_text}"
        try:
            await send_via_relay(chat_id, text)
        except Exception:
            logger.exception("ارسال نوتیفیکیشن تسک جدید ناموفق بود (chat_id=%s)", chat_id)
