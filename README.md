# LangChain AI

Локальний RAG та FastAPI-агент на Ollama (`hermes3` за замовчуванням).

## Файли

- `rag_script.py` — індексація `data.txt` у Chroma
- `agent.py` — чат з cybersecurity system prompt
- `api.py` — FastAPI `/ask` (Docker-aware)
- `local_request.py` — CLI-клієнт для API
- `frontend/` — веб-чат (nginx у Docker)

## Docker (рекомендовано)

Потрібні: [Docker](https://docs.docker.com/get-docker/) та [Docker Compose](https://docs.docker.com/compose/).

```bash
# Опційно: скопіюйте .env.example → .env і змініть модель
cp .env.example .env

docker compose up --build
```

Перший запуск завантажить модель Ollama (може зайняти 5–15 хв).

| Сервіс   | URL                    |
|----------|------------------------|
| Фронтенд | http://localhost:8080 |
| API      | http://localhost:8000 |
| Ollama   | http://localhost:11434 |

Фронтенд проксує запити через `/api/*` → бекенд. Docker socket змонтовано в API, щоб інструмент `get_docker_status` бачив контейнери хоста.

```bash
# Зупинити
docker compose down

# Логи API
docker compose logs -f api
```

Інша модель у `.env`:

```
OLLAMA_MODEL=llama3:8b
```

## Локальний запуск (без Docker)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
ollama pull hermes3

python rag_script.py   # опційно
python api.py
```

Фронтенд без nginx: відкрийте `frontend/index.html` і в `app.js` змініть `API_BASE` на `http://localhost:8000`, або запустіть простий сервер:

```bash
cd frontend && python -m http.server 8080
```

CLI-клієнт:

```bash
SERVER_IP=127.0.0.1 python local_request.py
```
