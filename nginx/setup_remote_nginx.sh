#!/usr/bin/env bash
# Bootstrap nginx on a public box that forwards to services running elsewhere.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$ROOT_DIR/.env"

prompt() {
  local var="$1" default="$2" msg="$3" value
  value="${!var:-}"
  if [[ -z "$value" ]]; then
    read -rp "$msg [$default]: " value
    value="${value:-$default}"
  fi
  printf '%s' "$value"
}

ensure_compose() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "Using docker compose (plugin)."
    echo "docker compose"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    echo "Using docker-compose (standalone)."
    echo "docker-compose"
    return
  fi
  echo "Docker Compose is required but not found. Install Docker or docker-compose and retry." >&2
  exit 1
}

if [[ ! -f "$ROOT_DIR/certs/fullchain.pem" || ! -f "$ROOT_DIR/certs/privkey.pem" ]]; then
  echo "Missing TLS material. Place certs at:"
  echo "  $ROOT_DIR/certs/fullchain.pem"
  echo "  $ROOT_DIR/certs/privkey.pem"
  exit 1
fi

PLANT_DOMAIN=$(prompt PLANT_DOMAIN "plants.example.com" "Enter the public domain handled by nginx")
PLANT_API_ORIGIN=$(prompt PLANT_API_ORIGIN "192.168.1.50:8000" "Enter backend (API) host:port reachable from this server")
PLANT_WEB_ORIGIN=$(prompt PLANT_WEB_ORIGIN "192.168.1.50:8100" "Enter web UI host:port reachable from this server")
PLANT_TELEGRAM_ORIGIN=$(prompt PLANT_TELEGRAM_ORIGIN "192.168.1.50:8200" "Enter Telegram mini app host:port reachable from this server")
PLANT_RESOLVER=$(prompt PLANT_RESOLVER "1.1.1.1" "Enter DNS resolver for nginx (public resolver works)")
PLANT_STACK_NETWORK=$(prompt PLANT_STACK_NETWORK "plant_stack" "Docker network name to attach nginx to")

cat >"$ENV_FILE" <<EOF
PLANT_DOMAIN=$PLANT_DOMAIN
PLANT_API_ORIGIN=$PLANT_API_ORIGIN
PLANT_WEB_ORIGIN=$PLANT_WEB_ORIGIN
PLANT_TELEGRAM_ORIGIN=$PLANT_TELEGRAM_ORIGIN
PLANT_RESOLVER=$PLANT_RESOLVER
PLANT_STACK_NETWORK=$PLANT_STACK_NETWORK
EOF
echo "Wrote $ENV_FILE"

echo "Ensuring docker network $PLANT_STACK_NETWORK exists..."
docker network create "$PLANT_STACK_NETWORK" >/dev/null 2>&1 || true

COMPOSE_BIN=$(ensure_compose)

echo "Starting nginx reverse proxy..."
if [[ "$COMPOSE_BIN" == "docker compose" ]]; then
  DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose --env-file "$ENV_FILE" up -d
else
  DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker-compose --env-file "$ENV_FILE" up -d
fi

echo "nginx is up. Verify with: curl -I https://$PLANT_DOMAIN"
