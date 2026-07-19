# سرویس فقط‌خواندنی برای دیدن زنده‌ی فایل دیتابیس (app.db) از طریق مرورگر
# sqlite-web پکیج رسمی PyPI (نویسنده: coleifer، همان نویسنده‌ی peewee) است
FROM python:3.12-slim
RUN pip install --no-cache-dir sqlite-web

EXPOSE 8080

CMD ["sqlite_web", "/data/app.db", "--host", "0.0.0.0", "--port", "8080", "--read-only", "--url-prefix", "/db-viewer"]
