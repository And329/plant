# Plant Device Client (Pi)

Minimal telemetry/command client for a provisioned device. Point it at your backend, paste the config from the Admin provision flow, and run.

## Quick start
1) From the Admin page, provision a device and copy the JSON snippet (it now includes `device_id`, `device_secret`, `sensor_ids`, `actuator_ids`).
2) Save it as `device-client/device_config.json` (or use the provided `device_config.example.json` as a template).
3) Install deps: `cd device-client && python -m venv .venv && . .venv/bin/activate && pip install requests`.
4) Run once to smoke-test: `python pi_client.py --config device_config.json --once`.
5) Or run continuously with the interactive console: `python pi_client.py --config device_config.json` (use `--no-cli` to disable the REPL).

## Config
- `device_config.example.json` shows the required fields. You can also override via env vars (`PLANT_API_BASE_URL`, `PLANT_DEVICE_ID`, `PLANT_DEVICE_SECRET`, `PLANT_SENSOR_SOIL_ID`, `PLANT_SENSOR_AIR_ID`, `PLANT_SENSOR_WATER_ID`, `PLANT_ACTUATOR_PUMP_ID`, `PLANT_ACTUATOR_LAMP_ID`).
- Missing values raise a clear error so you don’t accidentally run with blanks.

## Handy commands (interactive console)
- `set soil 35` / `set temp 22` / `set water 80` to override sensor readings
- `status` to print current sensors/actuators
- `send` to push telemetry + poll commands immediately
- `exit` to stop the console (client keeps running)

## What it does
- Authenticates with `/auth/device`
- Sends 3 readings: `soil_moisture`, `air_temperature`, `water_level`
- Polls `/commands`, logs them, and ACKs with feedback
- Uses intervals from config (`telemetry_interval`, `command_interval`)

Tip: For quick local dev, run the API on `http://127.0.0.1:8000` and keep the default intervals (`60s` telemetry, `5s` commands).
