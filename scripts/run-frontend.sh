#!/bin/sh
set -e
cd "$(dirname "$0")/../frontend"

if [ ! -f config.js ]; then
  cp config.example.js config.js
  echo "Створено config.js — вкажіть URL API на сервері (наприклад http://100.113.28.5:8000)"
fi

PORT="${FRONTEND_PORT:-8080}"
echo "Фронтенд: http://localhost:${PORT}"
echo "API (з config.js): $(grep API_BASE config.js | head -1)"
exec python3 -m http.server "$PORT"
