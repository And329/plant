# Plant Automation - Web UI Frontend

Web-based user interface for the plant automation system.

## Features

- User authentication and session management
- Device dashboard and management
- Automation profile configuration
- Alert viewing and management
- Landing page

## Running Standalone

⚠️ **Currently requires backend code to be present** (see "Current State" below).

```bash
# Make sure you're in the project root with backend/ directory present
cd /home/zen/plant

# Copy .env.example to .env and configure
cp frontend-web/.env.example frontend-web/.env

# Start the service (from root directory)
cd frontend-web
docker compose up --build
```

**Note:** This mounts the backend code from `../backend/app`. For true standalone deployment, the frontend needs refactoring (see below).

## Current State & TODO

⚠️ **This service is not yet fully independent.**

Currently, it still imports backend code directly (`from app.models import ...`). To achieve true service separation:

**TODO: Refactor to use HTTP API client**
- [ ] Create `app/api_client.py` to call backend REST API
- [ ] Update routers to use API client instead of direct DB access
- [ ] Remove SQLAlchemy dependencies
- [ ] Remove backend code imports

This refactoring will make the service truly independent and enable:
- Deploying web UI without backend code
- Easier mobile app development (same API pattern)
- Independent scaling and deployment
