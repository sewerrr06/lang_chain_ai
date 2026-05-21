FROM ollama/ollama:latest

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    curl \
    docker.io \
    sysstat \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt api.py ./
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV OLLAMA_HOST=0.0.0.0
ENV OLLAMA_BASE_URL=http://127.0.0.1:11434
ENV OLLAMA_MODEL=hermes3

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
