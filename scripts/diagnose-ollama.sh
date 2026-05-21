#!/bin/sh
set -e
echo "=== API → Ollama (127.0.0.1, спільна мережа з ollama) ==="
docker compose exec api curl -sf --max-time 10 http://127.0.0.1:11434/api/tags | head -c 200
echo ""
echo ""
echo "=== health ==="
curl -sf http://127.0.0.1:8000/health
echo ""
