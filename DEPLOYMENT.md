# Plant Automation System - Deployment Guide

Complete step-by-step guide to deploy the plant automation system on a new server.

## Prerequisites

- Ubuntu/Debian Linux server (20.04 LTS or newer recommended)
- Minimum 2GB RAM, 20GB disk space
- Root or sudo access
- Domain name (optional, for production)

---

## Step 1: Prepare the Server

### 1.1 Update System
```bash
sudo apt update && sudo apt upgrade -y
```

### 1.2 Install Docker
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (to run docker without sudo)
sudo usermod -aG docker $USER

# Log out and log back in for group changes to take effect
# Or run: newgrp docker
```

### 1.3 Install Docker Compose
```bash
sudo apt install docker-compose -y
```

### 1.4 Install Git
```bash
sudo apt install git -y
```

### 1.5 Install SQLite (for database management)
```bash
sudo apt install sqlite3 -y
```

---

## Step 2: Clone/Copy the Project

### Option A: Using Git (if you have a repository)
```bash
cd ~
git clone <your-repository-url> plant
cd plant
```

### Option B: Copy from Existing Server
On the **source server**:
```bash
cd /home/zen
tar -czf plant-backup.tar.gz plant/
scp plant-backup.tar.gz user@new-server:/home/user/
```

On the **new server**:
```bash
cd ~
tar -xzf plant-backup.tar.gz
cd plant
```

---

## Step 3: Configure Environment Variables

### 3.1 Backend Configuration
```bash
cd ~/plant/backend
nano .env
```

Update the following variables:
```env
# Database
DATABASE_URL=sqlite+aiosqlite:///./data/plant.db

# Security
SECRET_KEY=<generate-a-secure-random-key>
ADMIN_EMAILS=admin@yourdomain.com

# Redis (for automation worker)
REDIS_URL=redis://redis:6379/0

# CORS (update with your domain)
CORS_ORIGINS=http://localhost:3000,http://your-domain.com

# Optional: Email notifications
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your-email@gmail.com
# SMTP_PASSWORD=your-app-password
```

**Generate a secure SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3.2 Frontend Web Configuration
```bash
cd ~/plant/frontend-web
nano .env
```

Update:
```env
BACKEND_URL=http://localhost:8000
# For production, use your domain:
# BACKEND_URL=https://api.yourdomain.com
```

---

## Step 4: Set Up the Database

### 4.1 Create Data Directory
```bash
cd ~/plant/backend
mkdir -p data
```

### 4.2 Run Database Migrations
```bash
# Run migrations in order
sqlite3 data/plant.db < migrations/001_initial_schema.sql
sqlite3 data/plant.db < migrations/002_device_secret_plaintext.sql
sqlite3 data/plant.db < migrations/003_add_automation_execution_logs.sql
```

### 4.3 Verify Database
```bash
sqlite3 data/plant.db ".tables"
# Should show: actuators, alerts, automation_execution_logs, automation_profiles, commands, devices, sensors, telemetry, users
```

---

## Step 5: Build and Start Services

### 5.1 Build Docker Images
```bash
cd ~/plant/backend
docker compose build --no-cache
```

### 5.2 Start All Services
```bash
docker compose up -d
```

### 5.3 Verify Services are Running
```bash
docker compose ps
```

You should see:
- `backend-api-1` - Running (port 8000)
- `backend-redis-1` - Running
- `backend-worker-1` - Running
- `backend-sqlite-web-1` - Running (port 8081)

### 5.4 Check Logs
```bash
# Check API logs
docker compose logs api -f

# Check worker logs
docker compose logs worker -f

# Check all logs
docker compose logs -f
```

---

## Step 6: Create Admin User

### 6.1 Register Admin Account
Open your browser and go to:
```
http://your-server-ip:8000/web/register
```

Register with the email you specified in `ADMIN_EMAILS` in the `.env` file.

### 6.2 Verify Admin Access
1. Login at `http://your-server-ip:8000/web/login`
2. You should see "Admin" link in the navigation bar
3. Click Admin to access device provisioning

---

## Step 7: Configure Firewall (Production)

### 7.1 Using UFW (Ubuntu Firewall)
```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 8000/tcp  # Backend API
sudo ufw allow 3000/tcp  # Frontend (if running separately)
sudo ufw enable
```

### 7.2 Check Firewall Status
```bash
sudo ufw status
```

---

## Step 8: Set Up Reverse Proxy (Production - Optional)

For production, use Nginx as a reverse proxy with SSL.

### 8.1 Install Nginx
```bash
sudo apt install nginx -y
```

### 8.2 Create Nginx Configuration
```bash
sudo nano /etc/nginx/sites-available/plant
```

Add:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Web UI (if you build and serve frontend)
    location / {
        root /home/user/plant/frontend-web/static;
        try_files $uri $uri/ /index.html;
    }
}
```

### 8.3 Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/plant /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 8.4 Install SSL with Let's Encrypt
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

---

## Step 9: Mobile App Deployment

### 9.1 Build APK
```bash
cd ~/plant/mobile_app
flutter build apk --release
```

The APK will be at: `build/app/outputs/flutter-apk/app-release.apk`

### 9.2 Serve APK for Download
Copy the APK to a web-accessible location:
```bash
sudo mkdir -p /var/www/html/downloads
sudo cp build/app/outputs/flutter-apk/app-release.apk /var/www/html/downloads/plant-app.apk
```

Users can download from: `http://your-domain.com/downloads/plant-app.apk`

---

## Step 10: Set Up Automatic Startup

### 10.1 Enable Docker Services to Start on Boot
```bash
sudo systemctl enable docker
```

### 10.2 Create Systemd Service (Alternative to Docker Compose)
```bash
sudo nano /etc/systemd/system/plant-automation.service
```

Add:
```ini
[Unit]
Description=Plant Automation System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/user/plant/backend
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
User=user

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable plant-automation
sudo systemctl start plant-automation
```

---

## Step 11: Backup and Maintenance

### 11.1 Database Backup Script
Create a backup script:
```bash
nano ~/plant-backup.sh
```

Add:
```bash
#!/bin/bash
BACKUP_DIR=~/plant-backups
mkdir -p $BACKUP_DIR
DATE=$(date +%Y%m%d_%H%M%S)

# Backup database
cp ~/plant/backend/data/plant.db $BACKUP_DIR/plant_$DATE.db

# Keep only last 7 backups
ls -t $BACKUP_DIR/plant_*.db | tail -n +8 | xargs rm -f

echo "Backup completed: plant_$DATE.db"
```

Make executable:
```bash
chmod +x ~/plant-backup.sh
```

### 11.2 Set Up Automated Backups with Cron
```bash
crontab -e
```

Add (daily backup at 2 AM):
```
0 2 * * * /home/user/plant-backup.sh
```

### 11.3 View Logs
```bash
# API logs
docker compose logs api --tail 100

# Worker logs
docker compose logs worker --tail 100

# Follow logs in real-time
docker compose logs -f
```

### 11.4 Restart Services
```bash
cd ~/plant/backend
docker compose restart api
docker compose restart worker
```

---

## Step 12: Testing the Deployment

### 12.1 Test Backend API
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

### 12.2 Test Web UI
Open browser: `http://your-server-ip:8000/web`

### 12.3 Test Database Manager
Open browser: `http://your-server-ip:8081`

### 12.4 Test Device Provisioning
1. Login as admin
2. Go to Admin panel
3. Create a new device
4. Note the device ID and secret

---

## Troubleshooting

### Services Won't Start
```bash
# Check Docker status
sudo systemctl status docker

# Check compose logs
docker compose logs

# Rebuild and restart
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Database Errors
```bash
# Check database file permissions
ls -la ~/plant/backend/data/

# Fix permissions
chmod 644 ~/plant/backend/data/plant.db
```

### Port Already in Use
```bash
# Check what's using port 8000
sudo lsof -i :8000

# Kill the process
sudo kill -9 <PID>
```

### Worker Not Processing Automation
```bash
# Check worker logs
docker compose logs worker

# Check Redis connection
docker compose exec redis redis-cli ping
# Should return: PONG

# Restart worker
docker compose restart worker
```

### Can't Access from Outside
```bash
# Check firewall
sudo ufw status

# Check if service is listening on all interfaces
sudo netstat -tlnp | grep 8000

# Update docker-compose.yml to bind to 0.0.0.0
# ports:
#   - "0.0.0.0:8000:8000"
```

---

## Security Checklist

- [ ] Changed default SECRET_KEY
- [ ] Updated ADMIN_EMAILS to your email
- [ ] Enabled firewall (UFW)
- [ ] Set up SSL certificate (Let's Encrypt)
- [ ] Regular database backups configured
- [ ] Strong passwords for all accounts
- [ ] Disabled root SSH login (optional)
- [ ] Keep system updated: `sudo apt update && sudo apt upgrade`

---

## Quick Reference Commands

```bash
# Start services
cd ~/plant/backend && docker compose up -d

# Stop services
docker compose down

# Restart services
docker compose restart

# View logs
docker compose logs -f

# Check status
docker compose ps

# Backup database
cp ~/plant/backend/data/plant.db ~/plant-backup-$(date +%Y%m%d).db

# Access database
sqlite3 ~/plant/backend/data/plant.db

# Rebuild after code changes
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

## Support

For issues or questions:
- Check logs: `docker compose logs -f`
- Check database: `http://localhost:8081` (sqlite-web)
- Review this guide
- Check application health: `curl http://localhost:8000/health`

---

**Deployment Complete!** 🎉

Your plant automation system should now be running at:
- Web UI: `http://your-server-ip:8000/web`
- API: `http://your-server-ip:8000`
- Database Manager: `http://your-server-ip:8081`
