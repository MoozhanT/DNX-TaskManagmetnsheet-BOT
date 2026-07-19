"""تنظیمات ساده‌ی پروژه که از متغیر محیطی خوانده می‌شوند."""

import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# اگر تلگرام از سروری که این پروژه رویش اجرا می‌شود فیلتر باشد، یک پراکسی (مثلاً سرویس xray
# داخل docker-compose) این مقدار را ست می‌کند تا بات از طریق آن به تلگرام وصل شود.
# نمونه: socks5://xray:10808
TELEGRAM_PROXY_URL = os.environ.get("TELEGRAM_PROXY_URL", "")

# چند دقیقه قبل از موعد تسک، یادآوری برای مسئول تسک ارسال شود
REMINDER_OFFSET_MINUTES = int(os.environ.get("REMINDER_OFFSET_MINUTES", "60"))

# فاصله‌ی هر بار بررسی تسک‌هایی که موعد یادآوری‌شان رسیده
REMINDER_CHECK_INTERVAL_MINUTES = int(os.environ.get("REMINDER_CHECK_INTERVAL_MINUTES", "1"))
