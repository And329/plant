"""Production-ready telemetry client stub for Plant devices.

The hardware-specific sensor reading functions are left as stubs (``get_*``),
but everything else mirrors a deployable agent: configuration loading, token
management, telemetry scheduling, and command acknowledgement.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


log = logging.getLogger("pi-client")


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


DEFAULT_CONFIG = {
    "api_base_url": _env("PLANT_API_BASE_URL", "http://127.0.0.1:8000"),
    "device_id": _env("PLANT_DEVICE_ID", ""),
    "device_secret": _env("PLANT_DEVICE_SECRET", ""),
    "sensor_ids": {
        "soil_moisture": _env("PLANT_SENSOR_SOIL_ID", ""),
        "air_temperature": _env("PLANT_SENSOR_AIR_ID", ""),
        "water_level": _env("PLANT_SENSOR_WATER_ID", ""),
    },
    "actuator_ids": {
        "pump": _env("PLANT_ACTUATOR_PUMP_ID", ""),
        "lamp": _env("PLANT_ACTUATOR_LAMP_ID", ""),
    },
    "telemetry_interval": int(_env("PLANT_POLL_INTERVAL", "60")),
    "command_interval": int(_env("PLANT_COMMAND_POLL_INTERVAL", "5")),
}


@dataclass
class DeviceConfig:
    api_base_url: str
    device_id: str
    device_secret: str
    sensor_ids: dict[str, str]
    actuator_ids: dict[str, str]
    telemetry_interval: int
    command_interval: int

    @classmethod
    def load(cls, path: Path | None) -> DeviceConfig:
        data = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
        if path and path.is_file():
            with path.open() as fh:
                overrides = json.load(fh)
            data.update({k: v for k, v in overrides.items() if v is not None})
            if "sensor_ids" in overrides:
                data["sensor_ids"].update(overrides["sensor_ids"])
            if "actuator_ids" in overrides:
                data["actuator_ids"].update(overrides["actuator_ids"])
        cfg = cls(**data)
        cfg._validate()
        return cfg

    def _validate(self) -> None:
        missing = []
        for key in ("api_base_url", "device_id", "device_secret"):
            if not getattr(self, key):
                missing.append(key)
        for key, val in self.sensor_ids.items():
            if not val:
                missing.append(f"sensor_ids.{key}")
        for key, val in self.actuator_ids.items():
            if not val:
                missing.append(f"actuator_ids.{key}")
        if missing:
            missing_list = ", ".join(missing)
            raise ValueError(f"Missing config values: {missing_list}. Paste the provisioning snippet into your config file.")


@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 5


class PiClient:
    def __init__(self, config: DeviceConfig, interactive: bool = True):
        self.config = config
        self.tokens: AuthTokens | None = None
        self.session = requests.Session()
        self.sensor_values = {
            "soil_moisture": 42.0,
            "air_temperature": 23.5,
            "water_level": 75.0,
        }
        self.actuator_state = {name: "off" for name in self.config.actuator_ids if self.config.actuator_ids[name]}
        self._lock = threading.Lock()
        self._cli_thread: threading.Thread | None = None
        if interactive:
            self._cli_thread = threading.Thread(target=self._cli_loop, daemon=True)
            self._cli_thread.start()

    # --- Sensor stubs (replace with hardware integrations) --- #
    def get_soil_moisture(self) -> float:
        return self._get_sensor_value("soil_moisture")

    def get_temperature(self) -> float:
        return self._get_sensor_value("air_temperature")

    def get_water_level(self) -> float:
        return self._get_sensor_value("water_level")

    # --------------------------------------------------------- #
    def _get_sensor_value(self, key: str) -> float:
        with self._lock:
            return self.sensor_values[key]

    def _set_sensor_value(self, key: str, value: float) -> None:
        with self._lock:
            self.sensor_values[key] = value

    def _cli_loop(self) -> None:
        self._print_cli_help()
        alias_map = {
            "soil": "soil_moisture",
            "moisture": "soil_moisture",
            "temp": "air_temperature",
            "temperature": "air_temperature",
            "water": "water_level",
            "level": "water_level",
        }
        while True:
            try:
                raw = input("pi-client> ").strip()
            except EOFError:
                return
            if not raw:
                continue
            cmd, *args = raw.split()
            if cmd in {"quit", "exit"}:
                print("Stopping interactive console (client keeps running).")
                return
            if cmd == "help":
                self._print_cli_help()
            elif cmd == "set" and len(args) == 2:
                alias = args[0].lower()
                key = alias if alias in self.sensor_values else alias_map.get(alias)
                if key is None:
                    print("Unknown sensor alias.")
                    continue
                try:
                    value = float(args[1])
                except ValueError:
                    print("Value must be numeric.")
                    continue
                self._set_sensor_value(key, value)
                print(f"{key} set to {value}")
            elif cmd == "status":
                self._print_status()
            elif cmd == "send":
                print("Triggering immediate telemetry push...")
                self._cycle_once()
            else:
                print("Commands: set <sensor> <value>, status, send, help, exit")

    def _print_status(self) -> None:
        with self._lock:
            sensors = self.sensor_values.copy()
            actuators = self.actuator_state.copy()
        print("Sensors:")
        for key, value in sensors.items():
            print(f"  - {key}: {value}")
        print("Actuators:")
        if actuators:
            for key, value in actuators.items():
                print(f"  - {key}: {value}")
        else:
            print("  (no actuators configured)")

    @staticmethod
    def _print_cli_help() -> None:
        print("Interactive controls ready:")
        print("  set <sensor> <value>   -> override a sensor reading (soil/temp/water)")
        print("  status                 -> show current sensors + actuator state")
        print("  send                   -> immediately push telemetry + fetch commands")
        print("  help                   -> print this message")
        print("  exit                   -> stop the interactive console")

    # --- Networking ---
    def authenticate(self) -> None:
        payload = {
            "device_id": self.config.device_id,
            "device_secret": self.config.device_secret,
            "firmware_version": "1.0.0",
        }
        resp = self.session.post(f"{self.config.api_base_url}/auth/device", json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        expires_at = datetime.fromisoformat(data["expires_at"]).timestamp()
        self.tokens = AuthTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=expires_at,
        )
        log.info("Authenticated as device %s", self.config.device_id)

    def _ensure_token(self) -> str:
        if self.tokens is None or self.tokens.is_expired:
            self.authenticate()
        assert self.tokens is not None
        return self.tokens.access_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._ensure_token()}"}

    def push_telemetry(self) -> None:
        print("pushing telemetry as", self.config.device_id)
        now = datetime.now(timezone.utc).isoformat()
        readings = [
            {
                "sensor_id": self.config.sensor_ids["soil_moisture"],
                "timestamp": now,
                "value": self.get_soil_moisture(),
            },
            {
                "sensor_id": self.config.sensor_ids["air_temperature"],
                "timestamp": now,
                "value": self.get_temperature(),
            },
            {
                "sensor_id": self.config.sensor_ids["water_level"],
                "timestamp": now,
                "value": self.get_water_level(),
            },
        ]
        resp = self.session.post(
            f"{self.config.api_base_url}/telemetry",
            json={"readings": readings},
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        log.info("Telemetry batch accepted: %s", resp.json())

    def poll_commands(self) -> None:
        resp = self.session.get(f"{self.config.api_base_url}/commands", headers=self._headers(), timeout=10)
        resp.raise_for_status()
        for cmd in resp.json():
            log.info("Received command %s", cmd)
            self._execute_command(cmd)

    def _execute_command(self, cmd: dict[str, Any]) -> None:
        actuator_id = cmd.get("actuator_id")
        actuator_name = next(
            (name for name, ident in self.config.actuator_ids.items() if ident == actuator_id),
            actuator_id or "unknown",
        )
        command_type = cmd.get("command")
        payload = cmd.get("payload") or {}
        log.info("Executing %s -> %s (%s)", actuator_name, command_type, payload)

        with self._lock:
            if actuator_name in self.actuator_state:
                self.actuator_state[actuator_name] = command_type

        ack_payload = {
            "command_id": cmd["id"],
            "status": "acked",
            "feedback": {
                "actuator": actuator_name,
                "state": command_type,
                "observed_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        ack = self.session.post(
            f"{self.config.api_base_url}/commands/ack",
            json=ack_payload,
            headers=self._headers(),
            timeout=10,
        )
        ack.raise_for_status()

    # --- Scheduling ---
    def _cycle_once(self) -> None:
        try:
            self.push_telemetry()
            self.poll_commands()
        except requests.HTTPError as err:
            log.error("HTTP error: %s", err.response.text if err.response is not None else err)
            self.tokens = None
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Unexpected error: %s", exc)

    def run_forever(self) -> None:
        next_telemetry = time.time()
        next_command = time.time()
        while True:
            now = time.time()
            if now >= next_telemetry:
                self._safe_push_telemetry()
                next_telemetry = now + self.config.telemetry_interval
            if now >= next_command:
                self._safe_poll_commands()
                next_command = now + self.config.command_interval
            sleep_for = min(next_telemetry, next_command) - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)

    def _safe_push_telemetry(self) -> None:
        try:
            self.push_telemetry()
        except Exception:
            log.exception("Failed to send telemetry")
            self.tokens = None

    def _safe_poll_commands(self) -> None:
        try:
            self.poll_commands()
        except Exception:
            log.exception("Failed to poll commands")
            self.tokens = None

    def run_once(self) -> None:
        self._cycle_once()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plant automation telemetry client")
    parser.add_argument("--config", type=Path, default=Path("device_config.json"), help="Path to device config JSON")
    parser.add_argument("--once", action="store_true", help="Send telemetry + poll commands once and exit")
    parser.add_argument("--no-cli", action="store_true", help="Disable interactive CLI controls")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = DeviceConfig.load(args.config)
    client = PiClient(config, interactive=not args.no_cli)
    if args.once:
        client.run_once()
    else:
        client.run_forever()


if __name__ == "__main__":
    main()
