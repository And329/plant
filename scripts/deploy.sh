#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="$ROOT_DIR/.env"

ensure_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found. Installing via apt..."
    sudo apt-get update
    sudo apt-get install -y python3
  fi
}

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
PLANT_ADMIN_EMAILS=[]
EOF
else
  echo ".env already exists, keeping existing secrets."
fi

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

echo "All set! Api is running at 0.0.0.0:8000"
