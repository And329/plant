# Nginx Reverse Proxy

Nginx configuration for routing requests to backend API and frontend services.

## Routes

- `/auth`, `/telemetry`, `/commands`, `/devices`, `/alerts`, `/users` → Backend API
- `/docs`, `/redoc`, `/openapi.json` → Backend API docs
- `/telegram` → Telegram Web App
- `/` → Web UI

## Running Standalone

```bash
docker compose up
```

## SSL Certificates

Place your SSL certificates in `certs/`:
- `fullchain.pem` - SSL certificate
- `privkey.pem` - Private key

For local development, generate self-signed certificates:

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -keyout certs/privkey.pem \
    -out certs/fullchain.pem -days 365 -nodes -subj "/CN=localhost"
```

## Configuration

Edit `default.conf` to:
- Change upstream server addresses
- Modify SSL settings
- Update server names
- Adjust routing rules
