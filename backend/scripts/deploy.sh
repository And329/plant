#!/usr/bin/env bash
set -euo pipefail

ensure_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found. Installing via apt..."
    sudo apt-get update
    sudo apt-get install -y python3
  fi
}

DOMAIN="${1:-}"
ADMIN_EMAILS="${2:-}"

if [[ -z "$DOMAIN" ]]; then
  read -rp "Enter your public domain (e.g. example.com): " DOMAIN
fi

if [[ -z "$ADMIN_EMAILS" ]]; then
  read -rp "Enter admin emails (comma-separated): " ADMIN_EMAILS
fi

ensure_python

ADMIN_JSON=$(ADMIN_EMAILS="$ADMIN_EMAILS" python3 - <<'PY'
import json, os
raw = os.environ.get("ADMIN_EMAILS", "")
emails = [item.strip() for item in raw.split(",") if item.strip()]
print(json.dumps(emails))
PY
)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="$ROOT_DIR/.env"
NGINX_CONF="$ROOT_DIR/infra/nginx/default.conf"

generate_secret() {
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
}

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Creating .env with random secrets..."
  ensure_python
  JWT_SECRET=$(generate_secret)
  SESSION_SECRET=$(generate_secret)
  cat > "$ENV_FILE" <<EOF
PLANT_APP_NAME=Plant Automation Backend
PLANT_ENVIRONMENT=prod
PLANT_DATABASE_URL=sqlite+aiosqlite:///./data/plant.db
PLANT_REDIS_URL=redis://redis:6379/0
PLANT_JWT_SECRET_KEY=$JWT_SECRET
PLANT_ACCESS_TOKEN_EXPIRE_MINUTES=15
PLANT_REFRESH_TOKEN_EXPIRE_MINUTES=20160
PLANT_SESSION_SECRET_KEY=$SESSION_SECRET
PLANT_ADMIN_EMAILS=$ADMIN_JSON
EOF
else
  echo ".env already exists, updating admin emails."
  python3 - "$ENV_FILE" "$ADMIN_JSON" <<'PY'
import sys, pathlib
env_path = pathlib.Path(sys.argv[1])
value = sys.argv[2]
lines = env_path.read_text().splitlines()
for idx, line in enumerate(lines):
  if line.startswith("PLANT_ADMIN_EMAILS="):
    lines[idx] = f"PLANT_ADMIN_EMAILS={value}"
    break
else:
  lines.append(f"PLANT_ADMIN_EMAILS={value}")
env_path.write_text("\n".join(lines) + "\n")
PY
fi

python3 - "$DOMAIN" "$NGINX_CONF" <<'PY'
import sys, pathlib, re
domain, path = sys.argv[1:3]
if not domain:
  sys.exit(0)
conf = pathlib.Path(path).read_text()
count = {"n": 0}
def repl(match):
  count["n"] += 1
  return f"server_name {domain};" if count["n"] <= 2 else match.group(0)
conf = re.sub(r"server_name\s+[^;]+;", repl, conf, count=2)
pathlib.Path(path).write_text(conf)
PY

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not found. Installing Docker CE..."
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

configure_vfs_storage() {
  echo "Configuring Docker to use the vfs storage driver..."
  sudo mkdir -p /etc/docker
  cat <<'EOF' | sudo tee /etc/docker/daemon.json >/dev/null
{
  "storage-driver": "vfs"
}
EOF
}

ensure_overlay() {
  if sudo modprobe overlay 2>/dev/null; then
    return
  fi
  pkg="linux-modules-extra-$(uname -r)"
  if apt-cache policy "$pkg" >/dev/null 2>&1; then
    echo "Installing $pkg to enable overlayfs..."
    sudo apt-get update
    sudo apt-get install -y "$pkg" || true
    if sudo modprobe overlay 2>/dev/null; then
      return
    fi
  fi
  echo "Overlayfs unavailable on this kernel."
  configure_vfs_storage
}

ensure_overlay

if ! sudo systemctl is-active --quiet docker; then
  echo "Starting Docker daemon..."
  sudo systemctl start docker
fi
sudo systemctl restart docker >/dev/null 2>&1 || true

CURRENT_USER="${SUDO_USER:-$USER}"
if ! id -nG "$CURRENT_USER" | tr ' ' '\n' | grep -qx "docker"; then
  echo "Adding $CURRENT_USER to docker group (re-login required)..."
  sudo usermod -aG docker "$CURRENT_USER" || true
fi

echo "Stopping existing containers and clearing volumes (fresh deploy)..."
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose down -v || true

echo "Building and starting containers..."
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose up --build -d

echo "Bootstrapping demo data (safe to rerun)..."
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose run --rm api python -m scripts.bootstrap_db

echo "All set! API is running behind Nginx. Visit https://${DOMAIN:-your-domain}/web"
