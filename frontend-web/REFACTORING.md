# Frontend-Web Refactoring Summary

## Goal
Completely separate frontend-web from backend code and database access, using HTTP API exclusively.

## What Was Done

### 1. Created HTTP API Client (`app/api_client.py`)
- Async HTTP client using `httpx`
- JWT token management (stored in session)
- Methods for all backend API endpoints:
  - Authentication (login, register)
  - Devices (list, get, create, claim)
  - Automation profiles
  - Telemetry
  - Commands
  - Alerts

### 2. Refactored Web Router (`app/routers/web_refactored.py`)
- Replaced all database queries with HTTP API calls
- JWT-based authentication instead of database sessions
- Maintains same template rendering functionality
- All routes preserved (login, register, dashboard, device detail, etc.)

### 3. Created Standalone App Factory (`app/app_factory.py`)
- No backend dependencies
- SessionMiddleware for storing JWT tokens
- ProxyHeadersMiddleware
- Environment-based configuration

### 4. Updated Dependencies (`pyproject_refactored.toml`)
- Removed: sqlalchemy, aiosqlite, python-jose, passlib, redis, alembic, pydantic-settings
- Kept: fastapi, uvicorn, jinja2, httpx, itsdangerous, python-multipart
- Reduced from 25 to 6 dependencies

### 5. Created Standalone Dockerfile (`Dockerfile.refactored`)
- No parent directory context needed
- No volume mounts of backend code
- Self-contained build

### 6. Updated Docker Compose (`docker-compose_refactored.yml`)
- Removed backend code volume mounts
- Removed database volume mounts
- Environment variables for configuration:
  - `BACKEND_API_URL`: Backend API URL (default: http://api:8000)
  - `SESSION_SECRET_KEY`: Session encryption key
  - `DEVICE_OFFLINE_SECONDS`: Device offline threshold
  - `ADMIN_EMAILS`: Comma-separated admin emails

### 7. Added Missing Backend Endpoint
- Added `GET /telemetry/latest/{device_id}` to backend API

## Files Created (Refactored Versions)
- `app/api_client.py` - HTTP client
- `app/app_factory.py` - Standalone app factory
- `app/routers/web_refactored.py` - Refactored web router
- `app/routers/groups_refactored.py` - Updated router groups
- `main_refactored.py` - Refactored entry point
- `pyproject_refactored.toml` - Minimal dependencies
- `Dockerfile.refactored` - Standalone build
- `docker-compose_refactored.yml` - No volume mounts
- `.env.example` - Configuration template

## Next Steps

### To Apply Refactoring:
1. Backup current files:
   ```bash
   cd /home/zen/plant/frontend-web
   mv main.py main.py.bak
   mv pyproject.toml pyproject.toml.bak
   mv Dockerfile Dockerfile.bak
   mv docker-compose.yml docker-compose.yml.bak
   mv app/routers/groups.py app/routers/groups.py.bak
   mv app/routers/web.py app/routers/web.py.bak
   ```

2. Replace with refactored versions:
   ```bash
   mv main_refactored.py main.py
   mv pyproject_refactored.toml pyproject.toml
   mv Dockerfile.refactored Dockerfile
   mv docker-compose_refactored.yml docker-compose.yml
   mv app/routers/groups_refactored.py app/routers/groups.py
   mv app/routers/web_refactored.py app/routers/web.py
   ```

3. Create .env file:
   ```bash
   cp .env.example .env
   # Edit .env with actual values
   ```

4. Rebuild and test:
   ```bash
   docker compose build
   docker compose up
   ```

### Still Missing from Backend API:
1. **Settings API** - For telegram bot token management
   - GET `/settings/{key}`
   - PUT `/settings/{key}`
   - DELETE `/settings/{key}`

2. **Admin Device List** - List all devices (not just user's)
   - GET `/admin/devices`

3. **Device Provisioning** - Current endpoint doesn't return sensor/actuator IDs
   - Need to update `/devices` POST response

## Known Limitations

1. **Admin Panel**: Currently shows only user's devices, not all devices
   - Need backend admin endpoints
   
2. **Telegram Bot Token**: No API to manage settings
   - Admin panel can't save telegram token
   
3. **Device Provisioning**: Config snippet doesn't include sensor/actuator IDs
   - Backend needs to return these in provision response

## Testing Checklist

- [ ] Login works
- [ ] Registration works
- [ ] Dashboard shows devices
- [ ] Device detail page loads
- [ ] Latest sensor readings display
- [ ] Manual commands work
- [ ] Automation profile saving works
- [ ] Device claiming works
- [ ] Admin panel loads (for admin users)
- [ ] Device provisioning works

## Architecture

```
┌─────────────────┐         HTTP API          ┌─────────────────┐
│  Frontend-Web   │ ────────────────────────> │   Backend API   │
│                 │   (JWT Auth)              │                 │
│  - Templates    │                           │  - Database     │
│  - Sessions     │                           │  - Redis        │
│  - HTTP Client  │                           │  - Worker       │
└─────────────────┘                           └─────────────────┘
```

Before: Frontend directly imported backend models and accessed database
After: Frontend calls backend HTTP API with JWT tokens
