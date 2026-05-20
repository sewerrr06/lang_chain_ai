# LangChain AI

Локальний RAG та FastAPI-агент на Ollama (`llama3:8b`).

## Файли

- `rag_script.py` — індексація `data.txt` у Chroma
- `agent.py` — чат з cybersecurity system prompt
- `api.py` — FastAPI `/ask` (Docker-aware)
- `local_request.py` — клієнт для API

## Запуск

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
ollama pull llama3:8b
ollama pull nomic-embed-text

python rag_script.py
python api.py
```
