# ── مرحله‌ی ۱: ساخت (build) با Node ──
FROM node:20-alpine AS build
WORKDIR /app

# اول فقط package.json ها را کپی می‌کنیم تا کش داکر برای npm install بهتر کار کند
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# چون فرانت پشت همین nginx سرو می‌شود، آدرس بک‌اند را عمداً خالی می‌گذاریم
# تا درخواست‌ها به‌صورت نسبی (/api/...) به همین آدرس/پورت بروند؛
# nginx.conf این مسیر را به سرویس backend پراکسی می‌کند و نیازی به CORS نیست
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ── مرحله‌ی ۲: سرو کردن فایل‌های build شده با nginx ──
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY db-viewer.htpasswd /etc/nginx/db-viewer.htpasswd

EXPOSE 80
