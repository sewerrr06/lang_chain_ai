#!/bin/sh
set -e
echo "=== health ==="
curl -sf http://127.0.0.1:8000/health | python3 -m json.tool 2>/dev/null || curl -sf http://127.0.0.1:8000/health
echo ""
echo "=== Ollama tags (всередині app) ==="
docker compose exec app curl -sf --max-time 10 http://127.0.0.1:11434/api/tags | head -c 300
echo ""
