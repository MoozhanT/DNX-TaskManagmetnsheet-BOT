"""ارسال پیام به سرویس بات (روی سرور دیگر، با دسترسی مستقیم به تلگرام) از طریق /relay/send.
جدا از scheduler.py و sheet_sync.py است تا هر دو بدون import چرخه‌ای از آن استفاده کنند."""

import httpx

from config import GERMANY_RELAY_URL, INTERNAL_API_KEY


async def send_via_relay(chat_id: int, text: str) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{GERMANY_RELAY_URL.rstrip('/')}/relay/send",
            json={"chat_id": chat_id, "text": text},
            headers={"X-Internal-Key": INTERNAL_API_KEY},
        )
        response.raise_for_status()
