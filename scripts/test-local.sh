#!/bin/sh
set -e
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.local.yml"
PORT="${TEST_PORT:-8001}"

echo "=== Зупинка старих контейнерів ==="
docker compose -f docker-compose.local.yml down 2>/dev/null || true
docker compose down 2>/dev/null || true

echo "=== Збірка та старт (модель llama3.2:3b для швидкого тесту) ==="
$COMPOSE up -d --build

echo "=== Очікування health (до 15 хв — перший раз тягне модель) ==="
for i in $(seq 1 90); do
  if curl -sf "http://127.0.0.1:${PORT}/health" >/tmp/health.json 2>/dev/null; then
    if grep -q '"api_version":"2.6"' /tmp/health.json 2>/dev/null; then
      echo "OK health:"
      cat /tmp/health.json
      echo ""
      break
    fi
  fi
  echo "  ... $i/36"
  sleep 5
done

if ! curl -sf "http://127.0.0.1:${PORT}/health" | grep -q '2.6'; then
  echo "FAIL: API не готовий"
  $COMPOSE logs --tail 40
  exit 1
fi

echo "=== POST /ask (привіт) ==="
curl -sf -m 300 -X POST "http://127.0.0.1:${PORT}/ask" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"local_test","question":"привіт"}' | tee /tmp/ask.json
echo ""

if grep -q '"answer"' /tmp/ask.json; then
  echo "=== ТЕСТ ПРОЙДЕНО ==="
  exit 0
fi

echo "=== ТЕСТ НЕ ПРОЙДЕНО ==="
$COMPOSE logs --tail 50
exit 1
