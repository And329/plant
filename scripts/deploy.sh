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

ensure_overlay() {
  if lsmod | grep -q "^overlay"; then
    return
  fi
  echo "Attempting to load overlay kernel module..."
  if ! sudo modprobe overlay 2>/dev/null; then
    echo "Installing extra kernel modules for overlayfs..."
    sudo apt-get update
    sudo apt-get install -y "linux-modules-extra-$(uname -r)" || true
    if ! sudo modprobe overlay 2>/dev/null; then
      echo "Overlayfs unavailable; configuring Docker to use vfs storage driver."
      sudo mkdir -p /etc/docker
      cat <<'EOF' | sudo tee /etc/docker/daemon.json >/dev/null
{
  "storage-driver": "vfs"
}
EOF
    fi
  fi
}

ensure_overlay

if ! sudo systemctl is-active --quiet docker; then
  echo "Starting Docker daemon..."
  sudo systemctl start docker
fi
sudo systemctl restart docker >/dev/null 2>&1 || true

echo "Building and starting containers..."
docker compose up --build -d

echo "Bootstrapping demo data (safe to rerun)..."
docker compose run --rm api python -m scripts.bootstrap_demo

echo "All set! API available at http://localhost:8000/web"
