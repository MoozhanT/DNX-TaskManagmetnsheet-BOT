"""تنظیمات ساده‌ی پروژه که از متغیر محیطی خوانده می‌شوند."""

import os

# کلید مشترک بین این بک‌اند و سرویس بات (telegram-bot/، روی سرور دیگری با دسترسی مستقیم
# به تلگرام) برای احراز هویت مسیرهای /internal/*
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")

# آدرس سرویس بات، برای اینکه این بک‌اند بتواند یادآوری تسک‌ها را برایش بفرستد تا در تلگرام
# ارسال شود. اگر خالی باشد، یادآوری‌ها غیرفعال می‌مانند.
GERMANY_RELAY_URL = os.environ.get("GERMANY_RELAY_URL", "")

# چند دقیقه قبل از موعد تسک، یادآوری برای مسئول تسک ارسال شود
REMINDER_OFFSET_MINUTES = int(os.environ.get("REMINDER_OFFSET_MINUTES", "60"))

# فاصله‌ی هر بار بررسی تسک‌هایی که موعد یادآوری‌شان رسیده
REMINDER_CHECK_INTERVAL_MINUTES = int(os.environ.get("REMINDER_CHECK_INTERVAL_MINUTES", "1"))
