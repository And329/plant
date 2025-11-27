# Plant Automation API Documentation

**Base URL**: `https://your-domain.com` or `http://localhost:8000` (development)

**API Documentation**: Available at `/docs` (Swagger UI) and `/redoc` (ReDoc)

## Overview

This REST API powers the Plant Automation system. All clients (Web UI, Mobile App, Telegram Bot) communicate with this API.

## Authentication

### Device Authentication

Devices (Raspberry Pi) use JWT tokens for authentication.

#### POST `/auth/device`
Authenticate a device and get access tokens.

**Request:**
```json
{
  "device_id": "uuid",
  "device_secret": "secret"
}
```

**Response:**
```json
{
  "access_token": "jwt-token",
  "refresh_token": "jwt-token",
  "token_type": "bearer"
}
```

#### POST `/auth/device/refresh`
Refresh access token using refresh token.

**Headers:**
```
Authorization: Bearer <refresh_token>
```

**Response:**
```json
{
  "access_token": "new-jwt-token",
  "token_type": "bearer"
}
```

### User Authentication

Users authenticate via session cookies (handled by web/telegram frontends).

## Endpoints

### Devices

#### GET `/devices`
List all devices for the authenticated user.

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Living Room Plant",
    "model": "Model A",
    "owner_id": "uuid",
    "is_active": true,
    "last_seen": "2024-01-01T12:00:00Z"
  }
]
```

#### POST `/devices`
Create a new device (admin only).

**Request:**
```json
{
  "name": "New Plant Device",
  "model": "Model A"
}
```

**Response:**
```json
{
  "id": "uuid",
  "secret": "device-secret",
  "name": "New Plant Device",
  "model": "Model A"
}
```

#### GET `/devices/{device_id}`
Get device details including sensors and actuators.

**Response:**
```json
{
  "id": "uuid",
  "name": "Living Room Plant",
  "sensors": [...],
  "actuators": [...],
  "automation_profile": {...}
}
```

#### GET `/devices/{device_id}/automation`
Get automation profile for a device.

#### PUT `/devices/{device_id}/automation`
Update automation profile.

**Request:**
```json
{
  "min_soil_moisture": 30.0,
  "max_soil_moisture": 70.0,
  "min_temperature": 18.0,
  "max_temperature": 28.0,
  "watering_duration_seconds": 5,
  "watering_cooldown_minutes": 60
}
```

### Telemetry

#### POST `/telemetry`
Submit sensor readings from device (requires device auth).

**Headers:**
```
Authorization: Bearer <device_access_token>
```

**Request:**
```json
{
  "readings": [
    {
      "sensor_id": "uuid",
      "value": 45.5,
      "timestamp": "2024-01-01T12:00:00Z"
    }
  ]
}
```

**Response:**
```json
{
  "accepted": 3,
  "rejected": 0
}
```

#### GET `/telemetry/latest/{device_id}`
Get latest sensor readings for a device.

**Response:**
```json
{
  "device_id": "uuid",
  "readings": [
    {
      "sensor_id": "uuid",
      "sensor_type": "soil_moisture",
      "value": 45.5,
      "timestamp": "2024-01-01T12:00:00Z"
    }
  ]
}
```

### Commands

#### GET `/commands`
Poll for pending commands (device endpoint).

**Headers:**
```
Authorization: Bearer <device_access_token>
```

**Response:**
```json
[
  {
    "id": "uuid",
    "actuator_id": "uuid",
    "command_type": "PUMP_ON",
    "duration_seconds": 5,
    "created_at": "2024-01-01T12:00:00Z"
  }
]
```

#### POST `/commands/ack`
Acknowledge command execution.

**Request:**
```json
{
  "command_id": "uuid",
  "success": true,
  "message": "Pump activated for 5 seconds"
}
```

#### POST `/commands/{device_id}/manual`
Manually trigger a command (user endpoint).

**Request:**
```json
{
  "actuator_id": "uuid",
  "command_type": "PUMP_ON",
  "duration_seconds": 3
}
```

### Alerts

#### GET `/alerts`
List alerts for authenticated user.

**Query Parameters:**
- `unresolved_only`: boolean (default: false)
- `limit`: int (default: 50)

**Response:**
```json
[
  {
    "id": "uuid",
    "device_id": "uuid",
    "severity": "warning",
    "message": "Low water reservoir",
    "is_resolved": false,
    "created_at": "2024-01-01T12:00:00Z"
  }
]
```

#### PATCH `/alerts/{alert_id}/resolve`
Mark alert as resolved.

### Users

#### GET `/users/me`
Get current user profile.

**Response:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "is_admin": false,
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### PUT `/users/me`
Update user profile.

## Mobile App Integration

### Recommended Flow

1. **User Login**: Implement OAuth or session-based auth
2. **Device List**: `GET /devices` to show user's devices
3. **Device Dashboard**:
   - `GET /devices/{id}` for device details
   - `GET /telemetry/latest/{id}` for current readings
4. **Control**:
   - `POST /commands/{device_id}/manual` to trigger actions
5. **Alerts**:
   - `GET /alerts?unresolved_only=true` for notifications
   - `PATCH /alerts/{id}/resolve` when user acknowledges

### WebSocket Support (Future)

Currently, the API uses HTTP polling. For real-time updates in mobile app:
- Poll `/telemetry/latest/{device_id}` every 30-60 seconds
- Poll `/alerts?unresolved_only=true` every 60 seconds
- Consider implementing WebSocket support for live updates

### Rate Limiting

- Device telemetry: Max 1 request per second
- User endpoints: Max 60 requests per minute
- Alerts: Max 10 requests per minute

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

**Common Status Codes:**
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Validation Error
- `500` - Internal Server Error

## Data Models

### SensorReading
```json
{
  "sensor_id": "uuid",
  "sensor_type": "soil_moisture" | "temperature" | "water_level",
  "value": 45.5,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Command
```json
{
  "id": "uuid",
  "command_type": "PUMP_ON" | "PUMP_OFF" | "LAMP_ON" | "LAMP_OFF",
  "duration_seconds": 5,
  "status": "pending" | "acknowledged" | "failed"
}
```

### AutomationProfile
```json
{
  "min_soil_moisture": 30.0,
  "max_soil_moisture": 70.0,
  "min_temperature": 18.0,
  "max_temperature": 28.0,
  "watering_duration_seconds": 5,
  "watering_cooldown_minutes": 60,
  "lamp_on_time": "07:00:00",
  "lamp_off_time": "19:00:00"
}
```

## Testing

Use the interactive API documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

Or use curl:

```bash
# Get devices
curl -X GET http://localhost:8000/devices \
  -H "Authorization: Bearer <user_token>"

# Submit telemetry
curl -X POST http://localhost:8000/telemetry \
  -H "Authorization: Bearer <device_token>" \
  -H "Content-Type: application/json" \
  -d '{"readings": [{"sensor_id": "uuid", "value": 45.5}]}'
```
