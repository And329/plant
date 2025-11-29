# Nginx Reverse Proxy

Thin HTTPS proxy that fronts the API (`/auth`, `/telemetry`, etc.), the web UI (`/`), and the Telegram mini app (`/telegram`).

## Running

```bash
cd nginx
cp .env.example .env   # fill PLANT_*_ORIGIN with host:port targets
mkdir -p certs         # place fullchain.pem + privkey.pem here (see below)
docker network create plant_stack || true  # or point PLANT_STACK_NETWORK to an existing network
docker compose up
```

Environment variables in `.env` configure where traffic is forwarded:

| Variable | Default | Description |
| --- | --- | --- |
| `PLANT_DOMAIN` | `_` | Public domain for `server_name` (use `_` to match any) |
| `PLANT_API_ORIGIN` | `api:8000` | Host:port for the API service |
| `PLANT_WEB_ORIGIN` | `web_ui:8100` | Host:port for the web dashboard |
| `PLANT_TELEGRAM_ORIGIN` | `telegram_web_app:8200` | Host:port for Telegram web app |
| `PLANT_RESOLVER` | `127.0.0.11` | DNS resolver used for dynamic `proxy_pass` targets |
| `PLANT_STACK_NETWORK` | `plant_stack` | External Docker network to join |

For remote deployments, set each `PLANT_*_ORIGIN` to the public/private endpoint of the service (`backend.example.com:8000`, etc.). The template at `default.conf.template` is rendered by nginx's entrypoint using these variables, so you don't have to edit the config manually.

### Remote/public nginx in front of LAN services (with your existing certs)

Run this on the public machine that already has the SSL certs and public IP. The backend/frontends can stay on your LAN (e.g., 192.168.1.50).

```bash
cd nginx
cp .env.example .env  # optional; the script will overwrite with your answers
mkdir -p certs
# Place certs/fullchain.pem and certs/privkey.pem from the public box here

./setup_remote_nginx.sh
# Prompts:
# - Public domain (server_name)
# - API host:port reachable from the public box (e.g., 192.168.1.50:8000)
# - Web UI host:port (e.g., 192.168.1.50:8100)
# - Telegram host:port (e.g., 192.168.1.50:8200)
# - DNS resolver (e.g., 1.1.1.1) and docker network name (defaults ok)
```

The script writes `nginx/.env`, ensures the Docker network exists, and brings up nginx via Docker Compose. Update `PLANT_DOMAIN` in `.env` if you want a proper `server_name` instead of `_`.

## Certificates

Place your TLS material in `certs/`:

- `certs/fullchain.pem`
- `certs/privkey.pem`

For local testing you can self-sign:

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -keyout certs/privkey.pem \
    -out certs/fullchain.pem -days 365 -nodes -subj "/CN=localhost"
```

## Networking

The compose file connects to the external Docker network named in `PLANT_STACK_NETWORK`. When running all services on one host, point this to the shared network (`docker network create plant_stack`). If nginx runs on another machine, leave the network unset and just provide routable `PLANT_*_ORIGIN` hostnames/IPs.
