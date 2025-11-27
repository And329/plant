FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install frontend-telegram code
COPY frontend-telegram/pyproject.toml frontend-telegram/README.md ./
COPY frontend-telegram/app ./app
COPY frontend-telegram/main.py ./

RUN pip install --upgrade pip \
    && pip install --no-cache-dir .

# Note: This currently still depends on backend code being installed
# TODO: Refactor to use HTTP API client instead of direct imports

EXPOSE 8200

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8200"]
