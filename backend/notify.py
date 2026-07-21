"""ارسال پیام به سرویس بات (روی سرور دیگر، با دسترسی مستقیم به تلگرام) از طریق /relay/send.
جدا از scheduler.py و sheet_sync.py است تا هر دو بدون import چرخه‌ای از آن استفاده کنند."""

from typing import Optional

import httpx

from config import GERMANY_RELAY_URL, INTERNAL_API_KEY


async def send_via_relay(
    chat_id: int,
    text: str,
    *,
    parse_mode: Optional[str] = None,
    task_id: Optional[str] = None,
    expect_reply_forward_to: Optional[int] = None,
) -> None:
    """
    parse_mode="HTML" برای پیام‌های قالب‌بندی‌شده (بولد/ایتالیک) استفاده می‌شود.
    task_id اگر داده شود، سرویس بات دکمه‌های «انجام شد»/«درخواست تمدید» را زیر پیام می‌گذارد.
    expect_reply_forward_to اگر داده شود (مثلاً برای گزارش هفتگی)، اولین پیام متنی بعدی این
    کاربر به‌عنوان پاسخ تلقی و مستقیم به این chat_id فوروارد می‌شود.
    """
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if task_id:
        payload["task_id"] = task_id
    if expect_reply_forward_to:
        payload["expect_reply_forward_to"] = expect_reply_forward_to

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{GERMANY_RELAY_URL.rstrip('/')}/relay/send",
            json=payload,
            headers={"X-Internal-Key": INTERNAL_API_KEY},
        )
        response.raise_for_status()
