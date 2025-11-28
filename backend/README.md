# Plant Automation Backend

FastAPI + SQLAlchemy service that ingests telemetry from Raspberry Pi powered plant-care devices, automates pump/lamp control, and surfaces alerts to end users.

## Features

- Device provisioning with secret hashing and short-lived JWTs (`/auth/device`, `/auth/device/refresh`).
- Telemetry ingestion endpoint that validates sensor ownership, persists readings, and enqueues batches to the automation worker.
- Command queue for pumps/lamps with device polling + acknowledgements.
- User-facing device management (provisioning secrets, automation profile CRUD) and alert APIs.
- Redis-backed automation worker stub that consumes telemetry batches and issues commands/alerts per heuristic thresholds.

## Project Layout

```
app/
  core/          # configuration + security helpers
  db/            # SQLAlchemy base + AsyncSession factory
  models/        # ORM entities and enums
  schemas/       # Pydantic DTOs
  routers/       # FastAPI routers (auth, telemetry, devices, commands, alerts)
  services/      # automation queue + notification stubs
  workers/       # automation_worker consuming Redis stream
  main.py        # Legacy monolithic app (still useful for local prototyping)

services/
  api/               # REST API FastAPI service (auth, telemetry, etc.)
  web_ui/            # Web dashboard + landing pages
  telegram_web_app/  # Telegram Web App surface
```

## Getting Started

1. (Optional) Create and activate a virtualenv.
2. **Install dependencies** (includes the Pi client extra):
   ```bash
   pip install -e .[pi]
   ```
3. **Configure environment** by copying the sample file:
   ```bash
   cp .env.example .env
   ```
   Defaults use SQLite (`data/plant.db`) and Redis on `localhost`. Create the data directory once if you're running locally:
   ```bash
   mkdir -p data
   ```
   Set `PLANT_ADMIN_EMAILS` to a comma-separated list (e.g. `admin@example.com,ops@example.com`) so those accounts can access the admin console.
4. **Initialize the database**:
   ```bash
   python -m scripts.bootstrap_db
   ```
   Pass `--seed-demo` if you still want the sample user/device (`python -m scripts.bootstrap_db --seed-demo`). Otherwise, the database is created with no demo data and you can register through `/web/register`.
5. **Start the API service**:
   ```bash
   uvicorn services.api.main:app --reload --port 8000
   ```
6. **Start the web UI service** (landing page + dashboard) in another terminal:
   ```bash
   uvicorn services.web_ui.main:app --reload --port 8100
   ```
7. **(Optional) Start the Telegram Web App service** if you are iterating on the in-chat experience:
   ```bash
   uvicorn services.telegram_web_app.main:app --reload --port 8200
   ```
8. **Run the automation worker** in another terminal if you want automatic watering decisions:
   ```bash
   python -m app.workers.automation_worker
   ```
9. **Launch the Pi client stub** (new terminal):
   ```bash
   python clients/pi_client.py
   ```
10. **Open the web dashboard** at [http://127.0.0.1:8100/web](http://127.0.0.1:8100/web) and sign in with the demo credentials printed during bootstrapping, or browse [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the API schema.

### Web Dashboard

- Navigating to `/web` shows a password-protected UI where you can register, sign in, list devices, view latest sensor readings, and edit automation thresholds.
- Use the **Add device** form to provision additional devices directly from the UI; the new device ID + secret are displayed once and can be typed into the Pi client.
- Use the **Claim device** form to link factory-provisioned hardware by entering its device ID + secret.
- Administrators (emails listed in `PLANT_ADMIN_EMAILS`) get an **Admin** link that opens `/web/admin`, where they can mint unclaimed devices for manufacturing and see a history of hardware awaiting assignment.
- Device detail pages show each sensor with its most recent reading plus a form to adjust the soil moisture, temperature, and watering parameters stored in the automation profile.

### Provisioning physical devices

- Manufacturing or ops can pre-create devices with unique credentials via:
  ```bash
  python -m scripts.provision_device --name "Planter 101" --model "Model A"
  ```
  The script prints the UUID + secret you should bundle with the device (along with a JSON config snippet containing sensor/actuator IDs). Include `--owner-email you@example.com` if you want to assign it immediately; otherwise it remains unclaimed until a customer uses the claim form in the dashboard. You can perform the same action through `/web/admin` if your account is listed in `PLANT_ADMIN_EMAILS`; the admin console auto-creates the default sensors and actuators for each unit.

- After assembly, flash the `device_id` + `device_secret` into the Pi client (or drop them into `/etc/plant-device.json`) and the device can authenticate via `/auth/device`.

- Customers sign up at `/web/register`, log in, and claim the unit using the printed credentials. The claim endpoint verifies the secret and assigns the device to their account without touching the factory bootstrap data.

### Raspberry Pi Client Stub

- Moved to `../device-client/pi_client.py` for a standalone drop-in. Provision a device in the Admin UI, copy the JSON snippet (now includes sensor/actuator IDs), save it as `device-client/device_config.json`, then run `python pi_client.py --config device_config.json --once` to smoke-test telemetry + commands. See `device-client/README.md` for more.

## API Highlights

- `POST /auth/device` – exchange device ID + secret for access/refresh tokens.
- `POST /telemetry` – devices push batches of sensor readings.
- `GET /commands` / `POST /commands/ack` – poll + acknowledge actuator instructions.
- `GET/POST /devices` – list + provision new devices (returns fresh secret).
- `GET/PUT /devices/{id}/automation` – configure automation thresholds & schedules.
- `GET /alerts` + `PATCH /alerts/{id}/resolve` – user alert center.

## Automation Worker

`app/workers/automation_worker.py` consumes telemetry events from Redis (`telemetry` stream) and executes basic rules:
- Below-minimum soil moisture triggers pump pulses with cooldown enforcement.
- Out-of-range air temperature raises warnings.
- Low reservoir level creates critical alerts.
- Alerts notify the placeholder `NotificationService` for future integrations.

Extend `AutomationWorker` and `NotificationService` to match production needs (advanced schedules, ML-driven watering, actual push/email integrations, etc.).

## Docker deployment

1. Copy `.env.example` to `.env` and adjust secrets, or rely on the defaults for SQLite + Redis.
2. Build the image and start the stack (API + web UI + Telegram web app + worker + Redis):
   ```bash
   docker compose up --build -d
   ```
3. Run the bootstrap script once to create tables inside the container (re-run whenever you wipe the mounted SQLite volume):
   ```bash
   docker compose run --rm api python -m scripts.bootstrap_db
   ```
   Append `--seed-demo` if you want the sample user/device for smoke testing. The shared `plant-db` volume stores `data/plant.db`, so data persists across restarts.
4. Place TLS certificates for the built-in Nginx reverse proxy:
   - Copy your production `fullchain.pem` and `privkey.pem` into `infra/nginx/certs/`.
   - For local testing, create a self-signed pair:
     ```bash
     mkdir -p infra/nginx/certs
     openssl req -x509 -newkey rsa:4096 -keyout infra/nginx/certs/privkey.pem \
         -out infra/nginx/certs/fullchain.pem -days 365 -nodes -subj "/CN=localhost"
     ```
   - Nginx listens on ports 80/443 and proxies to the API (`/auth`, `/devices`, etc.), the Telegram web app (`/telegram`), and the dashboard (`/`). Update `infra/nginx/default.conf` if you want to lock the `server_name`.
5. Visit `https://localhost/web` and log in with the demo credentials printed by the bootstrap script.

The compose file brings up the API, web UI, Telegram web app, automation worker, Redis, and the Nginx TLS proxy, so watering/light rules run automatically and traffic terminates at HTTPS. Adjust `docker-compose.yml` if you prefer a different proxy (or direct exposure), external PostgreSQL, or managed Redis.

### One-command bootstrap

Run `scripts/deploy.sh` on a new machine to generate `.env` with random secrets, build the Docker images, start the stack, and seed the demo data automatically. The script now performs `docker compose down -v` before rebuilding so the SQLite schema stays in sync with code changes:

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```
