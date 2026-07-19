# راهنمای اجرای پروژه با Docker (ویژه‌ی ویندوز)

این راهنما توضیح می‌دهد چطور کل پروژه (بک‌اند FastAPI + بات تلگرام + پنل وب) را فقط با یک
دستور، داخل Docker بالا بیاوری.

## ۱) نصب Docker Desktop

```powershell
docker --version
docker compose version
```

اگر هر دو دستور یک شماره‌نسخه برگرداندند، همه‌چیز آماده است.

## ۲) تنظیم فایل .env

در ریشه‌ی پروژه:

```powershell
Copy-Item .env.example .env
```

فایل `.env` را باز کن و:
- مقدار `SECRET_KEY` را با یک رشته‌ی تصادفی و طولانی عوض کن (برای امضای توکن‌های ورود پنل وب):
  ```powershell
  -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 40 | % {[char]$_})
  ```
- مقدار `TELEGRAM_BOT_TOKEN` را با توکنی که از [@BotFather](https://t.me/BotFather) گرفته‌ای پر کن
  (بدون این مقدار، بک‌اند بالا می‌آید ولی بات تلگرام و یادآوری‌ها غیرفعال می‌مانند).

## ۳) ساخت فایل db-viewer.htpasswd

فرانت‌اند برای محافظت از مسیر `/db-viewer/` به یک فایل یوزر/پسورد نیاز دارد (این فایل عمداً در گیت نیست).
با OpenSSL (که همراه Git for Windows نصب می‌شود) بساز:

```powershell
$hash = & openssl passwd -apr1 "یک-رمز-دلخواه"
"admin:$hash" | Out-File -Encoding ascii frontend\db-viewer.htpasswd
```

## ۴) بالا آوردن پروژه

از ریشه‌ی پروژه:

```powershell
docker compose up --build
```

> اگر نسخه‌ی قدیمی‌تر Docker داری: `docker-compose up --build` (با خط تیره).

در پس‌زمینه:

```powershell
docker compose up --build -d
```

## ۵) آدرس‌هایی که باید در مرورگر باز کنی

| چی | آدرس |
|---|---|
| **پنل مدیریت (فرانت‌اند)** | http://localhost:8080 |
| بک‌اند به‌صورت مستقیم (اختیاری) | http://localhost:8000 |
| مستندات API (Swagger) | http://localhost:8000/docs |
| نمایشگر زنده‌ی دیتابیس (فقط‌خواندنی) | http://localhost:8080/db-viewer/ |

## ۶) ساخت اولین حساب پنل وب

به `http://localhost:8080/#/login` برو، روی «راه‌اندازی اولین حساب» بزن و یک username/password بساز.
این کار فقط یک‌بار قابل انجام است.

## ۷) دیدن لاگ‌ها

```powershell
docker compose logs -f
docker compose logs -f backend
```

## ۸) متوقف کردن پروژه

```powershell
docker compose down
```

دیتابیس (`app.db`) در volume باقی می‌ماند. برای پاک کردن کامل (شامل دیتابیس):

```powershell
docker compose down -v
```

## نکات تکمیلی

- بعد از هر تغییر در کد، دوباره `docker compose up --build` بزن.
- برای توسعه‌ی محلی با build از روی همین پوشه (به‌جای image های آماده):
  ```powershell
  docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
  ```
- اگر پورت 8080 یا 8000 اشغال است، در `docker-compose.yml` بخش `ports` را عوض کن.
