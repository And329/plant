FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy frontend-web code
COPY pyproject.toml ./
COPY README.md ./
COPY app ./app
COPY main.py ./

# Install dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8100

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]
