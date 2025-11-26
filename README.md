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
  main.py        # FastAPI app factory
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
4. **Bootstrap demo data** (creates tables, a user, device, sensors, and automation profile):
   ```bash
   python -m scripts.bootstrap_demo
   ```
   The script prints the user credentials, device ID/secret, and sensor IDs used by the client stub.
5. **Start the API**:
   ```bash
   uvicorn app.main:app --reload
   ```
6. **Run the automation worker** in another terminal if you want automatic watering decisions:
   ```bash
   python -m app.workers.automation_worker
   ```
7. **Launch the Pi client stub** (new terminal):
   ```bash
   python clients/pi_client.py
   ```
8. **Open the web dashboard** at [http://127.0.0.1:8000/web](http://127.0.0.1:8000/web) and sign in with the demo credentials printed during bootstrapping.

### Web Dashboard

- Navigating to `/web` shows a password-protected UI where you can list devices, view latest sensor readings, and edit automation thresholds.
- Use the **Add device** form to provision additional devices directly from the UI; the new device ID + secret are displayed once and can be typed into the Pi client.
- Device detail pages show each sensor with its most recent reading plus a form to adjust the soil moisture, temperature, and watering parameters stored in the automation profile.

### Raspberry Pi Client Stub

- `clients/pi_client.py` contains a synchronous script that authenticates a device, pushes telemetry, polls `/commands`, and acknowledges executions. It deliberately leaves `get_soil_moisture`, `get_temperature`, `get_water_level`, and `_execute_command` as placeholders for your actual GPIO/ADC integrations.
- Update `API_BASE_URL`, `DEVICE_ID`, `DEVICE_SECRET`, and the hard-coded `sensor_id` UUIDs to match the device + sensor rows you provisioned via the API (the defaults already align with the bootstrap script output).
- Install client deps on the Pi (typically `pip install requests`, or `pip install -e .[pi]` locally) and run `python clients/pi_client.py`. Environment variables (`PLANT_API_BASE_URL`, `PLANT_DEVICE_ID`, etc.) override the defaults printed by the bootstrap script. The loop sends telemetry every `POLL_INTERVAL_SECONDS` and logs commands from the backend.

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
2. Build the image and start the stack (API + worker + Redis):
   ```bash
   docker compose up --build -d
   ```
3. Run the bootstrap script once to seed demo data inside the container (re-run whenever you wipe the mounted SQLite volume):
   ```bash
   docker compose run --rm api python -m scripts.bootstrap_demo
   ```
   The shared `plant-db` volume stores `data/plant.db`, so data persists across restarts.
4. Visit `http://localhost:8000/web` and log in with the demo credentials printed by the bootstrap script.

The compose file also starts the automation worker service, so watering/light rules run automatically. Adjust `docker-compose.yml` if you prefer an external PostgreSQL instance or managed Redis.

### One-command bootstrap

Run `scripts/deploy.sh` on a new machine to generate `.env` with random secrets, build the Docker images, start the stack, and seed the demo data automatically:

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```
