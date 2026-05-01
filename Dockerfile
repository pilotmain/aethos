# Nexa: API, Telegram bot, and operator (scheduler) share this image.
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1

# Git: dev_job executor checks out branches; no interactive UI.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Application code
COPY app ./app
COPY scripts ./scripts
RUN mkdir -p /app/.agent_tasks /app/.runtime /app/data

EXPOSE 8000

# Default: API (operator scheduler runs in-process; see app/main.py)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
