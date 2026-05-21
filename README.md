# LangChain AI

Локальний RAG та FastAPI-агент на Ollama (`hermes3` за замовчуванням).

## Розгортання: сервер + локальний фронт

**На Linux-сервері** (sewers-hp / Tailscale) — лише бекенд:

```bash
cp .env.example .env
docker compose up -d --build
```

Перший запуск завантажить `hermes3` (5–15 хв). API: `http://<IP_сервера>:8000`.

У `.env` на сервері вкажіть CORS для вашого Mac:

```
CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
```

**На Mac (локально)** — веб-чат:

```bash
cp frontend/config.example.js frontend/config.js
# Відредагуйте API_BASE — IP сервера (напр. Tailscale 100.113.28.5)

chmod +x scripts/run-frontend.sh
./scripts/run-frontend.sh
```

Відкрийте http://localhost:8080 — запити йдуть напряму на `http://<сервер>:8000`.

URL API можна змінити в полі «API на сервері» в сайдбарі (зберігається в браузері).

### Перевірка

```bash
curl http://100.113.28.5:8000/health
```

## Файли

- `rag_script.py` — індексація `data.txt` у Chroma
- `agent.py` — чат з cybersecurity system prompt
- `api.py` — FastAPI `/ask` (Docker-aware)
- `local_request.py` — CLI-клієнт для API
- `frontend/` — локальний веб-чат
- `docker-compose.yml` — сервер: Ollama + API
- `docker-compose.full.yml` — опційно nginx-фронт на тій же машині

## Docker: все на одній машині (опційно)

```bash
docker compose -f docker-compose.yml -f docker-compose.full.yml up --build
```

Фронт: http://localhost:8080 (проксі `/api` → бекенд).

## Локальний запуск без Docker

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
ollama pull hermes3

python api.py
```

CLI-клієнт:

```bash
SERVER_IP=100.113.28.5 python local_request.py
```
