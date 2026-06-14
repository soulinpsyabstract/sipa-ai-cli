# SIPA AI CLI · Dockerfile · V1.0
# FastAPI + uvicorn on port 5003
# ask.sh монтируется как bind mount, не копируется внутрь

FROM python:3.12-slim

# ── Системные зависимости для ask.sh (bash + curl + jq) ──────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Python зависимости ────────────────────────────────────────────────────────
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Код приложения ────────────────────────────────────────────────────────────
COPY api.py sipa_ai_cli.py ./

# ── Директории для сессий и аудит-лога ───────────────────────────────────────
# Создаём внутри контейнера — реальные данные придут через volumes
RUN mkdir -p /home/sipa/bin/sessions/cli \
             /home/sipa/PROJECT/PAYTON_HUBS/HUB_LEGAL_FORENSIC

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:5003/health || exit 1

# ── Запуск ────────────────────────────────────────────────────────────────────
EXPOSE 5003

CMD ["python3", "-m", "uvicorn", "api:app", \
     "--host", "0.0.0.0", \
     "--port", "5003", \
     "--log-level", "info", \
     "--access-log"]
