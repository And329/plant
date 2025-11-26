"""Raspberry Pi telemetry client stub for the Plant Automation backend."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

API_BASE_URL = os.environ.get("PLANT_API_BASE_URL", "http://127.0.0.1:8000")
DEVICE_ID = os.environ.get("PLANT_DEVICE_ID", "11111111-1111-1111-1111-111111111111")
DEVICE_SECRET = os.environ.get("PLANT_DEVICE_SECRET", "demo-device-secret")
SENSOR_IDS = {
    "soil_moisture": os.environ.get(
        "PLANT_SENSOR_SOIL_ID", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    ),
    "temperature": os.environ.get(
        "PLANT_SENSOR_TEMP_ID", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    ),
    "water_level": os.environ.get(
        "PLANT_SENSOR_WATER_ID", "cccccccc-cccc-cccc-cccc-cccccccccccc"
    ),
}
ACTUATOR_IDS = {
    "pump": os.environ.get("PLANT_ACTUATOR_PUMP_ID", "21111111-1111-1111-1111-111111111111"),
    "lamp": os.environ.get("PLANT_ACTUATOR_LAMP_ID", "31111111-1111-1111-1111-111111111111"),
}
ACTUATOR_LOOKUP = {v: k for k, v in ACTUATOR_IDS.items() if v}
SENSOR_DEFAULTS = {
    "soil_moisture": 42.0,
    "temperature": 23.5,
    "water_level": 75.0,
}
SENSOR_ALIASES = {
    "soil": "soil_moisture",
    "moisture": "soil_moisture",
    "temp": "temperature",
    "temperature": "temperature",
    "water": "water_level",
    "level": "water_level",
}
TELEMETRY_INTERVAL_SECONDS = int(os.environ.get("PLANT_POLL_INTERVAL", "60"))
COMMAND_POLL_INTERVAL_SECONDS = int(os.environ.get("PLANT_COMMAND_POLL_INTERVAL", "5"))


@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 5


class PiClient:
    def __init__(self):
        self.tokens: AuthTokens | None = None
        self.sensor_values = SENSOR_DEFAULTS.copy()
        self.actuator_state = {name: "off" for name, ident in ACTUATOR_IDS.items() if ident}
        self._lock = threading.Lock()
        self._start_cli_thread()

    # --- Sensor stubs (replace with hardware integrations) --- #
    def get_soil_moisture(self) -> float:
        return self._get_sensor_value("soil_moisture")

    def get_temperature(self) -> float:
        return self._get_sensor_value("temperature")

    def get_water_level(self) -> float:
        return self._get_sensor_value("water_level")

    # --------------------------------------------------------- #
    def _get_sensor_value(self, key: str) -> float:
        with self._lock:
            return self.sensor_values[key]

    def _set_sensor_value(self, key: str, value: float) -> None:
        with self._lock:
            self.sensor_values[key] = value

    def _start_cli_thread(self) -> None:
        thread = threading.Thread(target=self._cli_loop, daemon=True)
        thread.start()

    def _cli_loop(self) -> None:
        self._print_cli_help()
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
                self._handle_set_command(args[0], args[1])
            elif cmd == "status":
                self._print_status()
            elif cmd == "send":
                print("Triggering immediate telemetry push...")
                self._cycle_once()
            else:
                print("Commands: set <sensor> <value>, status, send, help, exit")

    def _handle_set_command(self, sensor_alias: str, raw_value: str) -> None:
        key = self._resolve_sensor(sensor_alias.lower())
        if key is None:
            print(f"Unknown sensor '{sensor_alias}'. Try soil/temp/water.")
            return
        try:
            value = float(raw_value)
        except ValueError:
            print("Value must be numeric.")
            return
        self._set_sensor_value(key, value)
        print(f"{key.replace('_', ' ').title()} set to {value}")

    def _resolve_sensor(self, alias: str) -> str | None:
        if alias in self.sensor_values:
            return alias
        return SENSOR_ALIASES.get(alias)

    def _print_status(self) -> None:
        with self._lock:
            sensor_snapshot = self.sensor_values.copy()
            actuator_snapshot = self.actuator_state.copy()
        print("Sensors:")
        for key, value in sensor_snapshot.items():
            print(f"  - {key}: {value}")
        if actuator_snapshot:
            print("Actuators:")
            for key, value in actuator_snapshot.items():
                print(f"  - {key}: {value}")

    @staticmethod
    def _print_cli_help() -> None:
        print("Interactive controls ready:")
        print("  set <sensor> <value>   -> override a sensor reading (soil/temp/water)")
        print("  status                 -> show current sensors + actuator state")
        print("  send                   -> immediately push telemetry + fetch commands")
        print("  help                   -> print this message")
        print("  exit                   -> stop the interactive console")

    def authenticate(self) -> None:
        payload = {
            "device_id": DEVICE_ID,
            "device_secret": DEVICE_SECRET,
            "firmware_version": "0.0.1",
        }
        response = requests.post(f"{API_BASE_URL}/auth/device", json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        expires_at = datetime.fromisoformat(data["expires_at"]).timestamp()
        self.tokens = AuthTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=expires_at,
        )

    def _ensure_token(self) -> str:
        if self.tokens is None or self.tokens.is_expired:
            self.authenticate()
        assert self.tokens is not None
        return self.tokens.access_token

    def _headers(self) -> dict[str, str]:
        token = self._ensure_token()
        return {"Authorization": f"Bearer {token}"}

    def push_telemetry(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        readings = [
            {
                "sensor_id": SENSOR_IDS["soil_moisture"],
                "timestamp": now,
                "value": self.get_soil_moisture(),
            },
            {
                "sensor_id": SENSOR_IDS["temperature"],
                "timestamp": now,
                "value": self.get_temperature(),
            },
            {
                "sensor_id": SENSOR_IDS["water_level"],
                "timestamp": now,
                "value": self.get_water_level(),
            },
        ]
        resp = requests.post(
            f"{API_BASE_URL}/telemetry",
            json={"readings": readings},
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        print("Telemetry batch sent", resp.json())

    def poll_commands(self) -> None:
        resp = requests.get(f"{API_BASE_URL}/commands", headers=self._headers(), timeout=10)
        resp.raise_for_status()
        for cmd in resp.json():
            print("Received command", cmd)
            self._execute_command(cmd)

    def _execute_command(self, cmd: dict[str, Any]) -> None:
        actuator_id = cmd.get("actuator_id")
        actuator_name = ACTUATOR_LOOKUP.get(actuator_id, actuator_id or "unknown_actuator")
        command_type = cmd.get("command")
        payload = cmd.get("payload") or {}

        action_desc = f"{actuator_name} -> {command_type}"
        if payload:
            action_desc += f" ({payload})"
        print(f"Executing command: {action_desc}")

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
        ack = requests.post(
            f"{API_BASE_URL}/commands/ack",
            json=ack_payload,
            headers=self._headers(),
            timeout=10,
        )
        ack.raise_for_status()

    def _cycle_once(self) -> None:
        try:
            self.push_telemetry()
            self.poll_commands()
        except requests.HTTPError as err:
            print("HTTP error", err.response.text)
            self.tokens = None
        except Exception as exc:  # noqa: BLE001
            print("Unexpected error", exc)

    def run_forever(self) -> None:
        next_telemetry = time.time()
        next_command = time.time()
        while True:
            now = time.time()
            if now >= next_telemetry:
                self._safe_push_telemetry()
                next_telemetry = now + TELEMETRY_INTERVAL_SECONDS
            if now >= next_command:
                self._safe_poll_commands()
                next_command = now + COMMAND_POLL_INTERVAL_SECONDS
            sleep_for = min(next_telemetry, next_command) - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)

    def _safe_push_telemetry(self) -> None:
        try:
            self.push_telemetry()
        except requests.HTTPError as err:
            print("HTTP error", err.response.text)
            self.tokens = None
        except Exception as exc:  # noqa: BLE001
            print("Unexpected error during telemetry", exc)

    def _safe_poll_commands(self) -> None:
        try:
            self.poll_commands()
        except requests.HTTPError as err:
            print("HTTP error", err.response.text)
            self.tokens = None
        except Exception as exc:  # noqa: BLE001
            print("Unexpected error when polling commands", exc)


def main() -> None:
    client = PiClient()
    client.run_forever()


if __name__ == "__main__":
    main()
