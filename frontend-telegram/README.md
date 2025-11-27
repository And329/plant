# Plant Automation - Telegram Web App Frontend

Telegram Mini App interface for the plant automation system.

## Features

- Telegram authentication via initData
- Device monitoring and control
- Telegram-specific UI optimizations

## Running Standalone

```bash
# Copy .env.example to .env and configure
cp .env.example .env

# Start the service
docker compose up --build
```

Configure `BACKEND_API_URL` in `.env` to point to your backend API.

## Current State & TODO

⚠️ **This service is not yet fully independent.**

Currently, it still imports backend code directly (`from app.models import ...`). To achieve true service separation:

**TODO: Refactor to use HTTP API client**
- [ ] Create `app/api_client.py` to call backend REST API
- [ ] Update routers to use API client instead of direct DB access
- [ ] Remove SQLAlchemy dependencies
- [ ] Remove backend code imports

This refactoring will make the service truly independent and enable:
- Deploying Telegram app without backend code
- Easier mobile app development (same API pattern)
- Independent scaling and deployment
