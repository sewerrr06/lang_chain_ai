# LangChain AI

Локальний RAG та FastAPI-агент на Ollama (`hermes3` за замовчуванням).

## Розгортання: сервер + локальний фронт

**На Linux-сервері** (sewers-hp / Tailscale) — лише бекенд:

```bash
cp .env.example .env

# Перший раз — завантажити hermes3 (~4.7 GB, 5–15 хв)
docker compose --profile init run --rm ollama-init

# Далі завжди лише це (без повторного pull)
docker compose up -d --build
```

API: `http://<IP_сервера>:8000`. Контейнер `api` ділить мережу з `ollama` (`127.0.0.1:11434`) — це усуває `ConnectTimeout` до `ollama:11434`.

Після деплою перевірте версію: `curl -s http://127.0.0.1:8000/health` → `"api_version":"2.5"`.

```bash
chmod +x scripts/diagnose-ollama.sh
./scripts/diagnose-ollama.sh
```

У `.env` на сервері вкажіть CORS для вашого Mac:

```
CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
```

**На Mac (локально)** — веб-чат:

```bash
cp frontend/config.example.js frontend/config.js
# У config.js — API_BASE = URL сервера (для проксі)

chmod +x scripts/run-frontend.sh
./scripts/run-frontend.sh
```

Відкрийте http://localhost:8080. У полі «API на сервері» має бути **`http://localhost:8080/api`** (локальний проксі → сервер, без CORS).

Якщо було збережено `http://100.113.28.5:8000` — змініть на `/api` або очистіть site data для localhost.

### Перевірка

```bash
curl http://100.113.28.5:8000/health
```

### Помилка `cannot stop container: permission denied`

Часто через `sudo docker` після запуску без sudo (або навпаки). На сервері:

```bash
# Один спосіб на всі команди — або завжди sudo, або без (користувач у групі docker)
sudo docker rm -f lang_chain_ai-api-1 lang_chain_ai-frontend-1 2>/dev/null
sudo docker compose up -d --build --remove-orphans
```

Довгостроково (без sudo):

```bash
sudo usermod -aG docker $USER
# вийти з SSH і зайти знову
docker compose up -d --build --remove-orphans
```

Якщо не допомогло — перезапуск демона: `sudo systemctl restart docker`, потім `docker compose up` знову.

### Сервер падає на «привіт» / будь-який запит

Часто **не вистачає RAM** для `hermes3` (~4.7 GB) + Ollama. Після запиту:

```bash
docker compose logs api --tail 50
docker compose logs ollama --tail 50
dmesg | tail -20 | grep -i oom
```

Потрібно **≥8 GB RAM** на сервері. Оновіть код (`git pull`) і перезберіть API:

```bash
docker compose up -d --build api
```

На «привіт» більше не запускається веб-пошук (раніше це перевантажувало систему).

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
