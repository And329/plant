from enum import Enum


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    PROVISIONED = "provisioned"


class SensorType(str, Enum):
    SOIL_MOISTURE = "soil_moisture"
    AIR_TEMPERATURE = "air_temperature"
    WATER_LEVEL = "water_level"


class ActuatorType(str, Enum):
    PUMP = "pump"
    LAMP = "lamp"


class CommandType(str, Enum):
    ON = "on"
    OFF = "off"
    PULSE = "pulse"


class CommandStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    ACKED = "acked"
    FAILED = "failed"


class AlertType(str, Enum):
    TEMP_HIGH = "temp_high"
    TEMP_LOW = "temp_low"
    WATER_LOW = "water_low"
    WATERING_COOLDOWN = "watering_cooldown"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"
