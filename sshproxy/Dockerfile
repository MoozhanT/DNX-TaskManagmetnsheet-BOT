# این سرویس یک تانل SSH (SOCKS5 پویا) به یک سرور خارج از کشور برقرار می‌کند تا
# بک‌اند بتواند از طریق آن به تلگرام (که ممکن است روی سرور اصلی فیلتر باشد) وصل شود.
FROM alpine:3.20

RUN apk add --no-cache autossh openssh-client

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
