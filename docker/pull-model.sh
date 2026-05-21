#!/bin/sh
set -e

OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
MODEL="${OLLAMA_MODEL:-hermes3}"

echo "Очікування Ollama (${OLLAMA_HOST})..."
until ollama list >/dev/null 2>&1; do
  sleep 2
done

echo "Завантаження моделі ${MODEL} (може зайняти кілька хвилин)..."
ollama pull "${MODEL}"
echo "Модель ${MODEL} готова."
