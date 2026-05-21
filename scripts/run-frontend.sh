#!/bin/sh
set -e
ROOT="$(dirname "$0")/.."
cd "$ROOT/frontend"

if [ ! -f config.js ]; then
  cp config.example.js config.js
  echo "Створено config.js — REMOTE API для проксі (наприклад http://100.113.28.5:8000)"
fi

PORT="${FRONTEND_PORT:-8080}"

if command -v lsof >/dev/null 2>&1 && lsof -ti:"$PORT" >/dev/null 2>&1; then
  echo "Порт ${PORT} вже зайнятий — фронтенд, ймовірно, уже працює."
  echo "Відкрийте: http://localhost:${PORT}"
  echo "URL API в чаті: http://localhost:${PORT}/api"
  echo "Зупинити: kill \$(lsof -ti:${PORT})"
  exit 0
fi

exec python3 "$ROOT/scripts/frontend_server.py"
