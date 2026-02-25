#!/bin/bash
# Обновление и перезапуск Spotify Recorder на хосте
# Запуск: ./scripts/deploy.sh
# Или: bash scripts/deploy.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "[deploy] Директория: $PROJECT_DIR"
echo "[deploy] pwd: $(pwd)"
echo "[deploy] recordings exists: $([ -d recordings ] && echo yes || echo no)"
echo "[deploy] .env exists: $([ -f .env ] && echo yes || echo no)"

if [ -d .git ]; then
    echo "[deploy] git pull..."
    NEED_STASH=0
    git diff --quiet 2>/dev/null || NEED_STASH=1
    git diff --cached --quiet 2>/dev/null || NEED_STASH=1
    if [ "$NEED_STASH" = "1" ]; then
        echo "[deploy] Локальные изменения — прячу (stash)..."
        git stash push -m "deploy $(date +%Y%m%d_%H%M%S)"
    fi
    git pull --rebase
    if [ "$NEED_STASH" = "1" ]; then
        echo "[deploy] Восстанавливаю изменения..."
        git stash pop
    fi
fi

NO_CACHE=""
[[ "${1:-}" == "--force" || "${1:-}" == "-f" ]] && NO_CACHE="--no-cache"
echo "[deploy] docker-compose build..."
docker-compose -f docker-compose.web.yml build $NO_CACHE

echo "[deploy] docker-compose up -d..."
docker-compose -f docker-compose.web.yml up -d

echo "[deploy] Готово."
