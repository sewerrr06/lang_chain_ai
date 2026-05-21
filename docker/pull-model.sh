#!/bin/sh
set -e

OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
MODEL="${OLLAMA_MODEL:-hermes3}"

echo "Очікування Ollama (${OLLAMA_HOST})..."
until ollama list >/dev/null 2>&1; do
  sleep 2
done

if ollama list 2>/dev/null | awk '{print $1}' | grep -qx "${MODEL}"; then
  echo "Модель ${MODEL} вже є — pull пропущено."
  exit 0
fi

echo "Завантаження моделі ${MODEL} (може зайняти кілька хвилин)..."
ollama pull "${MODEL}"
echo "Модель ${MODEL} готова."
