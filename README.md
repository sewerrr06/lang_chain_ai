# LangChain AI

Локальний RAG та FastAPI-агент на Ollama (`hermes3` за замовчуванням).

## Архітектура Docker (один контейнер `app`)

Ollama + API в **одному** контейнері → `127.0.0.1:11434`, без помилки `ConnectTimeout` між сервісами.

## Сервер (sewers-HP)

```bash
cp .env.example .env
docker compose down --remove-orphans
docker compose up -d --build
docker compose logs -f app
```

Перший запуск: завантаження `hermes3` (~4.7 GB). API: `http://<IP>:8000`.

Перевірка версії (має бути **2.6**):

```bash
curl -s http://127.0.0.1:8000/health
```

```bash
curl -s -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"session_id":"t1","question":"привіт"}'
```

## Локальний тест (Mac, менша модель)

```bash
chmod +x scripts/test-local.sh scripts/run-frontend.sh
./scripts/test-local.sh
```

Піднімає `llama3.2:3b` для швидшої перевірки. Продакшен на сервері: `OLLAMA_MODEL=hermes3` у `.env`.

## Фронтенд на Mac → API на сервері

```bash
cp frontend/config.example.js frontend/config.js
./scripts/run-frontend.sh
```

Браузер: http://localhost:8080 — поле API: `http://localhost:8080/api` (проксі).

## Файли

- `api.py` — FastAPI `/ask`
- `docker/entrypoint.sh` — Ollama + uvicorn
- `frontend/` — веб-чат
- `local_request.py` — CLI

## Локально без Docker

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
ollama pull hermes3
OLLAMA_BASE_URL=http://127.0.0.1:11434 python api.py
```
