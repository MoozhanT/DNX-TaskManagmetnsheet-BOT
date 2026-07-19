# ایمیج رسمی و سبک پایتون
FROM python:3.12-slim

WORKDIR /app

# اول فقط requirements را کپی می‌کنیم؛ اگر بعداً فقط کد عوض شود (نه وابستگی‌ها)،
# داکر همین لایه‌ی نصب‌شده را از کش استفاده می‌کند و build سریع‌تر می‌شود
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# بقیه‌ی کد پروژه
COPY . .

# پوشه‌ای که قرار است به‌عنوان volume در docker-compose مانت شود
RUN mkdir -p data

EXPOSE 8000

# نسخه‌ی production: بدون --reload
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
