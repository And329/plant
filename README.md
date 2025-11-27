# Plant Automation System

Microservices-based platform for managing Raspberry Pi-powered plant care devices. Includes REST API backend, web dashboard, Telegram bot integration, and support for mobile applications.

## Architecture

This project follows a **service-oriented architecture** where each component can be deployed independently:

- **Backend API** - Standalone REST API service
- **Frontend Web** - Web dashboard (can run separately)
- **Frontend Telegram** - Telegram Mini App (can run separately)
- **Nginx** - Reverse proxy (optional, can use any proxy)
- **Mobile App** - (Future) Will consume the same REST API

### Service Separation Benefits

- Deploy/scale services independently
- Remove services you don't need (e.g., remove Telegram if unused)
- Add new clients (mobile app) without changing backend
- Replace infrastructure (nginx) without touching services
- Better suited for cloud deployment (K8s, ECS, etc.)

## Project Structure

```
backend/              # Backend REST API (standalone)
├── app/             # API logic, models, schemas
├── data/            # SQLite database (runtime)
├── clients/         # Raspberry Pi client
├── scripts/         # DB bootstrap scripts
├── docker-compose.yml  # Run backend standalone
├── API.md           # API documentation for mobile dev
└── README.md

frontend-web/        # Web UI (standalone)
├── app/
├── docker-compose.yml  # Run web UI standalone
└── README.md

frontend-telegram/   # Telegram Mini App (standalone)
├── app/
├── docker-compose.yml
└── README.md

nginx/              # Reverse proxy (standalone)
├── default.conf
├── docker-compose.yml
└── README.md

docker-compose.yml  # Full stack for local development
```

## Quick Start (Full Stack)

Run all services together for local development:

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Generate SSL certificates (for local HTTPS)
mkdir -p nginx/certs
openssl req -x509 -newkey rsa:4096 -keyout nginx/certs/privkey.pem \
    -out nginx/certs/fullchain.pem -days 365 -nodes -subj "/CN=localhost"

# 3. Start all services
docker compose up --build

# 4. Bootstrap database (first time only)
docker compose exec api python -m scripts.bootstrap_db --seed-demo

# 5. Access the application
# - Web UI: https://localhost/web
# - API Docs: https://localhost/docs
# - Telegram: https://localhost/telegram
```

## Running Services Independently

### Backend Only

```bash
cd backend
cp .env.example .env
docker compose up --build

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

**Use case**: Mobile app development, API testing

### Web UI Only

```bash
cd frontend-web
cp .env.example .env
# Set BACKEND_API_URL=http://your-backend-url
docker compose up --build

# Web UI available at http://localhost:8100
```

**Use case**: Frontend development, separate web deployment

### Telegram Only

```bash
cd frontend-telegram
cp .env.example .env
# Set BACKEND_API_URL=http://your-backend-url
docker compose up --build

# Telegram app available at http://localhost:8200
```

**Use case**: Telegram bot development, separate deployment

### Nginx Only

```bash
cd nginx
docker compose up

# Proxy available at http://localhost:80
```

**Use case**: Using existing nginx, testing proxy config

## Mobile App Development

The backend exposes a complete REST API that mobile apps can consume. See [backend/API.md](backend/API.md) for full API documentation.

**Key endpoints:**
- `POST /auth/device` - Device authentication
- `GET /devices` - List user's devices
- `GET /telemetry/latest/{device_id}` - Latest sensor readings
- `POST /commands/{device_id}/manual` - Control devices
- `GET /alerts` - Get alerts/notifications

**Mobile app flow:**
1. User authentication (implement OAuth or session)
2. Fetch devices: `GET /devices`
3. Display telemetry: `GET /telemetry/latest/{id}`
4. Send commands: `POST /commands/{id}/manual`
5. Show alerts: `GET /alerts?unresolved_only=true`

## Features

### Backend API
- JWT-based device authentication
- Telemetry ingestion from IoT devices
- Command queue for actuators (pumps, lamps)
- Automation rules engine
- User management and alerts
- Redis-backed background worker

### Web Dashboard
- User registration and authentication
- Device management and provisioning
- Live sensor readings dashboard
- Automation profile configuration
- Alert management
- Admin panel

### Telegram Integration
- Telegram Mini App support
- Device monitoring via Telegram
- Telegram bot notifications (future)

### Raspberry Pi Client
- Stub client for development
- Device authentication
- Telemetry submission
- Command polling and execution

## Development

### Backend Development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .[dev]

# Run locally
uvicorn main:app --reload --port 8000
```

### Frontend Development

```bash
cd frontend-web  # or frontend-telegram
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Make sure backend is running, then:
uvicorn main:app --reload --port 8100
```

## Current Status & Roadmap

### ✅ Completed
- Service separation architecture
- Independent Docker compose files for each service
- Backend API with full CRUD operations
- Web UI with authentication and device management
- Telegram Mini App integration
- API documentation for mobile development

### 🚧 In Progress
- **Frontend HTTP API clients** - Currently frontends import backend code directly. Need to refactor to use HTTP API (see [frontend-web/README.md](frontend-web/README.md))

### 📋 Planned
- Mobile app (iOS/Android)
- WebSocket support for real-time updates
- Advanced automation rules (ML-based)
- Email/SMS notifications
- Multi-user device sharing
- Historical data analytics

## Configuration

Each service has its own `.env.example` file:

- `backend/.env.example` - Backend configuration
- `frontend-web/.env.example` - Web UI configuration
- `frontend-telegram/.env.example` - Telegram app configuration
- `.env.example` - Full stack configuration

Key environment variables:

```bash
# Backend
PLANT_DATABASE_URL=sqlite+aiosqlite:///data/plant.db
PLANT_REDIS_URL=redis://redis:6379/0
PLANT_ADMIN_EMAILS=admin@example.com
PLANT_SESSION_SECRET_KEY=your-secret-here

# Frontends
BACKEND_API_URL=http://api:8000
```

## Deployment

### Option 1: Full Stack (Docker Compose)

```bash
# Production docker-compose.yml
docker compose -f docker-compose.prod.yml up -d
```

### Option 2: Individual Services

Deploy each service to separate infrastructure:

```bash
# Backend to AWS ECS/Fargate
# Frontend-web to Vercel/Netlify
# Nginx to separate load balancer
```

### Option 3: Kubernetes

Each service has a Dockerfile ready for K8s deployment. Create deployment manifests for each service.

## Testing

```bash
cd backend
pip install -e .[dev]
pytest
```

## API Documentation

- Interactive Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Mobile dev guide: [backend/API.md](backend/API.md)

## License

MIT

## Support

For issues, questions, or contributions, please open an issue on GitHub.
