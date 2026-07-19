#!/bin/bash
set -e
cd /opt/dnx-taskbot
echo "==> git pull"
git pull origin main
echo "==> docker build backend"
docker build -t dnx-taskbot-backend:latest ./backend
echo "==> docker build frontend"
docker build -t dnx-taskbot-frontend:latest ./frontend
echo "==> docker build db-viewer"
docker build -t dnx-taskbot-db-viewer:latest ./db-viewer
echo "==> docker compose up -d --force-recreate"
docker compose up -d --force-recreate
echo "==> done"
