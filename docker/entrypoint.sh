#!/bin/sh
set -e

MODEL="${OLLAMA_MODEL:-hermes3}"
export OLLAMA_HOST="${OLLAMA_HOST:-0.0.0.0}"

echo "=== Запуск Ollama (фон) ==="
ollama serve &
OLLAMA_PID=$!
trap 'kill "$OLLAMA_PID" 2>/dev/null || true' EXIT INT TERM

echo "=== Очікування Ollama ==="
until ollama list >/dev/null 2>&1; do
  sleep 2
done

if ollama list 2>/dev/null | awk '{print $1}' | grep -qx "$MODEL"; then
  echo "=== Модель $MODEL вже є ==="
else
  echo "=== Завантаження $MODEL ==="
  ollama pull "$MODEL"
fi

echo "=== Старт API (uvicorn) ==="
cd /app
exec uvicorn api:app --host 0.0.0.0 --port 8000
