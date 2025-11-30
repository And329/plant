#!/bin/bash

# Plant Automation System - Quick Deployment Script
# This script automates the deployment process on a new server

set -e  # Exit on error

echo "======================================"
echo "Plant Automation System - Deployment"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo -e "${RED}Please do not run as root. Run as a regular user with sudo access.${NC}"
   exit 1
fi

# Function to print status
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Step 1: Check prerequisites
echo "Step 1: Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    print_warning "Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    print_status "Docker installed. Please log out and log back in, then run this script again."
    exit 0
else
    print_status "Docker is installed"
fi

if ! command -v docker-compose &> /dev/null; then
    print_warning "Docker Compose not found. Installing..."
    sudo apt update
    sudo apt install docker-compose -y
    print_status "Docker Compose installed"
else
    print_status "Docker Compose is installed"
fi

if ! command -v sqlite3 &> /dev/null; then
    print_warning "SQLite3 not found. Installing..."
    sudo apt install sqlite3 -y
    print_status "SQLite3 installed"
else
    print_status "SQLite3 is installed"
fi

# Step 2: Configure environment
echo ""
echo "Step 2: Configuring environment..."

# Use root-level .env consumed by docker-compose.yml
if [ ! -f .env ]; then
    print_warning "Root .env not found. Creating..."

    read -p "Enter admin email address: " ADMIN_EMAIL
    SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")

    cat > .env <<EOF
# Backend config (PLANT_ prefix)
PLANT_DATABASE_URL=sqlite+aiosqlite:///./data/plant.db
PLANT_REDIS_URL=redis://redis:6379/0
PLANT_ADMIN_EMAILS=$ADMIN_EMAIL
PLANT_SESSION_SECRET_KEY=$SESSION_SECRET
PLANT_JWT_SECRET_KEY=$JWT_SECRET

# Frontends
BACKEND_API_URL=http://api:8000

# Network
PLANT_STACK_NETWORK=plant_stack
EOF
    print_status "Root .env created"
else
    print_status "Root .env already exists"
fi

# Capture admin email for instructions
ADMIN_EMAIL=$(grep -m1 '^PLANT_ADMIN_EMAILS=' .env | cut -d= -f2-)

cd backend

# Step 3: Set up database
echo ""
echo "Step 3: Setting up database..."

mkdir -p data

if [ ! -f data/plant.db ]; then
    print_status "Creating database..."

    # Run migrations in order
    if [ -f migrations/001_initial_schema.sql ]; then
        sqlite3 data/plant.db < migrations/001_initial_schema.sql 2>&1
        print_status "Applied migration: 001_initial_schema.sql"
    fi

    if [ -f migrations/002_device_secret_plaintext.sql ]; then
        sqlite3 data/plant.db < migrations/002_device_secret_plaintext.sql 2>&1 || print_warning "Migration 002 skipped (already applied or not needed)"
    fi

    if [ -f migrations/003_add_automation_execution_logs.sql ]; then
        sqlite3 data/plant.db < migrations/003_add_automation_execution_logs.sql 2>&1
        print_status "Applied migration: 003_add_automation_execution_logs.sql"
    fi

    print_status "Database created successfully"
else
    print_warning "Database already exists. To run migrations on existing database:"
    print_warning "  cd backend && sqlite3 data/plant.db < migrations/003_add_automation_execution_logs.sql"
fi

# Step 4: Build Docker images
echo ""
echo "Step 4: Building Docker images..."
print_warning "This may take a few minutes..."

cd ..

# Ensure network exists
docker network inspect plant_stack >/dev/null 2>&1 || docker network create plant_stack

docker compose build api worker web_ui nginx redis
print_status "Docker images built successfully"

# Step 5: Start services
echo ""
echo "Step 5: Starting services..."

docker compose down 2>/dev/null || true
docker compose up -d api worker web_ui nginx redis

# Wait for services to start
sleep 5

# Check service status
if docker compose ps | grep -q "Up"; then
    print_status "Services started successfully"
else
    print_error "Some services failed to start. Check logs with: docker compose logs"
    exit 1
fi

# Step 6: Display status
echo ""
echo "======================================"
echo "Deployment Complete!"
echo "======================================"
echo ""

# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}')

echo "Your plant automation system is now running!"
echo ""
echo "Web UI (frontend): http://$SERVER_IP:8100/web"
echo "API:               http://$SERVER_IP:8000"
echo "Nginx (optional):  http://$SERVER_IP:80"
echo "Database Manager:  http://$SERVER_IP:8081"
echo "Mobile App Download: http://$SERVER_IP:8000/app-download"
echo ""
echo "Next steps:"
echo "1. Register an admin account at: http://$SERVER_IP:8100/web/register"
echo "   Use the email: $ADMIN_EMAIL"
echo ""
echo "2. Login and access the Admin panel to provision devices"
echo ""
echo "Useful commands:"
echo "  View logs:        docker compose logs -f"
echo "  Restart services: docker compose restart"
echo "  Stop services:    docker compose down"
echo "  Check status:     docker compose ps"
echo ""
echo "For detailed documentation, see: DEPLOYMENT.md"
echo ""

# Create a backup script
cat > ~/plant-backup.sh <<'EOF'
#!/bin/bash
BACKUP_DIR=~/plant-backups
mkdir -p $BACKUP_DIR
DATE=$(date +%Y%m%d_%H%M%S)
PLANT_DIR=~/plant/backend

# Backup database
cp $PLANT_DIR/data/plant.db $BACKUP_DIR/plant_$DATE.db

# Keep only last 7 backups
ls -t $BACKUP_DIR/plant_*.db | tail -n +8 | xargs rm -f 2>/dev/null || true

echo "Backup completed: plant_$DATE.db"
EOF

chmod +x ~/plant-backup.sh
print_status "Backup script created at ~/plant-backup.sh"

echo ""
print_status "Deployment completed successfully! 🎉"
