#!/bin/bash
set -e
cd /opt/dnx-taskbot
echo "==> git pull"
git pull origin main
echo "==> docker compose (telegram-bot) up -d --build --force-recreate"
docker compose -f telegram-bot/docker-compose.yml up -d --build --force-recreate
echo "==> done"
