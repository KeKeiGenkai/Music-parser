#!/bin/bash
# Обновление и перезапуск Spotify Recorder на хосте
# Запуск: ./scripts/deploy.sh
# Или: bash scripts/deploy.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "[deploy] Директория: $PROJECT_DIR"

if [ -d .git ]; then
    echo "[deploy] git pull..."
    git pull --rebase
fi

echo "[deploy] docker-compose build..."
docker-compose -f docker-compose.web.yml build --no-cache

echo "[deploy] docker-compose up -d..."
docker-compose -f docker-compose.web.yml up -d

echo "[deploy] Готово."
