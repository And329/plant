# Automation System Restructuring Summary

## Issues Fixed Today

### 1. Temperature Alerts Not Showing in UI
**Problem**: Alerts were being created in the database but not displaying in the web UI.

**Root Causes**:
- `AlertOut` schema was missing `device_id` field
- Template was trying to access `.value` on string enum values from JSON API

**Fixes**:
- Added `device_id: UUID` to `AlertOut` schema (`backend/app/schemas/alert.py`)
- Updated template to handle both string and enum formats (`frontend-web/app/templates/device_detail.html`)

### 2. Automation Profile Update Failing
**Problem**: Setting temperature alerts through web UI resulted in 422 errors.

**Root Causes**:
- HTML forms send empty fields as `""` not `None`, causing FastAPI validation errors
- Database model had required fields that should be nullable
- SQLAlchemy lazy loading causing MissingGreenlet errors

**Fixes**:
- Changed Form parameters to accept `str` type with proper validation (`frontend-web/app/routers/web.py`)
- Made automation profile fields nullable with defaults (`backend/app/models/entities.py`)
- Added eager loading with `selectinload()` to prevent lazy loading issues

### 3. Device Provisioning Broken
**Problem**: Creating new devices in admin panel failed with "readonly database" and validation errors.

**Fixes**:
- Fixed database file permissions (chmod 666)
- Added eager relationship loading on device refresh after creation

---

## New Modular Automation Architecture

### Overview
Restructured the automation system from a monolithic worker to a clean, modular, rule-based architecture that is:
- **Testable**: Each rule is isolated and can be tested independently
- **Debuggable**: Every rule execution includes reasoning
- **Extensible**: Adding new rules requires no changes to core worker logic
- **Clear**: Explicit dependencies and data flow

### Architecture

```
┌─────────────────────────────────────────────────┐
│ AutomationWorkerV2                              │
│  - Receives telemetry from Redis                │
│  - Builds RuleContext                           │
│  - Runs all rules                               │
│  - Collects commands/alerts                     │
│  - Logs execution (with reasoning!)             │
└─────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ Automation Rules (app/services/automation_rules.py)│
├─────────────────────────────────────────────────┤
│ ✓ SoilMoistureRule                              │
│   - Monitors soil moisture                      │
│   - Triggers watering with cooldown             │
│                                                  │
│ ✓ TemperatureAlertRule                          │
│   - Creates alerts for out-of-range temps       │
│                                                  │
│ ✓ WaterLevelAlertRule                           │
│   - Monitors reservoir level                    │
│                                                  │
│ ✓ LightCycleRule                                │
│   - Controls lamp on/off cycles                 │
└─────────────────────────────────────────────────┘
```

### Key Components

#### 1. `RuleContext` - Data provided to rules
```python
@dataclass
class RuleContext:
    device: Device
    profile: AutomationProfile
    sensor_readings: dict[SensorType, float]
    last_commands: dict[ActuatorType, Command | None]
```

#### 2. `RuleResult` - What each rule returns
```python
@dataclass
class RuleResult:
    rule_name: str
    executed: bool
    reason: str  # Human-readable explanation!
    commands: list[Command]
    alerts: list[Alert]
```

#### 3. `AutomationRule` base class
```python
class AutomationRule(ABC):
    @abstractmethod
    def can_run(self, ctx: RuleContext) -> bool:
        """Check if rule has required data"""
        
    @abstractmethod
    def evaluate(self, ctx: RuleContext) -> RuleResult:
        """Evaluate rule and return actions"""
```

### Example: Temperature Alert Rule

```python
class TemperatureAlertRule(AutomationRule):
    def can_run(self, ctx: RuleContext) -> bool:
        return (
            SensorType.AIR_TEMPERATURE in ctx.sensor_readings
            and ctx.profile.temp_min is not None
            and ctx.profile.temp_max is not None
        )
    
    def evaluate(self, ctx: RuleContext) -> RuleResult:
        temp = ctx.sensor_readings[SensorType.AIR_TEMPERATURE]
        
        if temp < ctx.profile.temp_min:
            return RuleResult(
                rule_name="temperature_alerts",
                executed=True,
                reason=f"Temperature {temp}°C < minimum {ctx.profile.temp_min}°C",
                commands=[],
                alerts=[Alert(
                    device_id=ctx.device.id,
                    type=AlertType.TEMP_LOW,
                    severity=AlertSeverity.WARN,
                    message=f"Temperature below threshold ({temp}°C)",
                )],
            )
        # ... handle temp_max, normal range
```

### Benefits

**Before (Monolithic)**:
- 200+ line `_evaluate_and_apply()` method
- All logic intertwined
- Hard to test individual rules
- No visibility into decision-making
- Complex to add new automation

**After (Modular)**:
- Each rule is ~40-60 lines
- Self-contained with clear responsibilities  
- Every rule can be unit tested
- Every execution has a reason string
- Add rules by creating new class in `ALL_RULES`

### Logging & Debugging

Each automation execution now logs:
```python
{
    "soil_moisture_control": {
        "executed": true,
        "reason": "Soil moisture 42.0% is above minimum 35.0%",
        "commands": 0,
        "alerts": 0
    },
    "temperature_alerts": {
        "executed": true,
        "reason": "Temperature 15.0°C is below minimum 18.0°C",
        "commands": 0,
        "alerts": 1
    },
    ...
}
```

**Future**: Can be saved to `AutomationExecutionLog` table for admin UI debugging panel.

---

## Files Changed

### Backend
- `app/services/automation_rules.py` - NEW: Modular rule definitions
- `app/workers/automation_worker_v2/` - NEW: Refactored worker
- `app/models/entities.py` - Made automation fields nullable, added AutomationExecutionLog
- `app/routers/devices.py` - Fixed greenlet errors with eager loading
- `app/schemas/alert.py` - Added device_id field
- `app/schemas/device.py` - Already had nullable fields
- `docker-compose.yml` - Updated worker command

### Frontend
- `frontend-web/app/routers/web.py` - Fixed form handling for empty fields
- `frontend-web/app/templates/device_detail.html` - Handle JSON vs enum values
- `device-client/test_device.json` - Updated to demo device credentials

---

## How to Add New Automation Rules

1. Create new rule class in `app/services/automation_rules.py`:
```python
class MyNewRule(AutomationRule):
    @property
    def name(self) -> str:
        return "my_rule_name"
    
    def can_run(self, ctx: RuleContext) -> bool:
        # Check if you have required data
        return SensorType.MY_SENSOR in ctx.sensor_readings
    
    def evaluate(self, ctx: RuleContext) -> RuleResult:
        # Your logic here
        return RuleResult(
            rule_name=self.name,
            executed=True,
            reason="Why this decision was made",
            commands=[...],
            alerts=[...],
        )
```

2. Add to registry:
```python
ALL_RULES: list[AutomationRule] = [
    SoilMoistureRule(),
    TemperatureAlertRule(),
    WaterLevelAlertRule(),
    LightCycleRule(),
    MyNewRule(),  # <-- Add here
]
```

3. Done! The worker automatically runs all registered rules.

---

## Future Enhancements

### Short-term
1. ✅ Basic rule system (DONE)
2. TODO: Admin UI debugging panel showing execution logs
3. TODO: Enable/disable individual rules per device
4. TODO: Rule priority/ordering

### Long-term (Advanced Algorithms)
1. **PID Controllers** for temperature/humidity regulation
2. **ML-based predictions** (e.g., predict watering needs)
3. **Weather API integration** (adjust watering based on forecast)
4. **Adaptive rules** that learn optimal thresholds
5. **Multi-device coordination** (greenhouse zones)

### Recommended Architecture for ML/Advanced:
```python
class MLPredictiveWateringRule(AutomationRule):
    def __init__(self):
        self.model = load_model("watering_predictor.pkl")
    
    def evaluate(self, ctx: RuleContext) -> RuleResult:
        # Use historical data + current readings
        prediction = self.model.predict([
            ctx.sensor_readings[SensorType.SOIL_MOISTURE],
            ctx.sensor_readings[SensorType.AIR_TEMPERATURE],
            # ... weather data, time of day, etc.
        ])
        
        if prediction > 0.7:  # High confidence needs watering
            return RuleResult(
                reason=f"ML model predicts watering needed (confidence: {prediction})",
                commands=[...],
            )
```

---

## Testing Automation

### Current Status (Working ✅)
- Temperature alerts are being created
- Alerts show in web UI
- Worker logs show rule execution with reasons
- Automation profile updates work

### To Test Manually
1. Set temperature thresholds in device settings
2. Send telemetry with out-of-range temperature
3. Check worker logs for rule execution
4. Verify alerts appear in device detail page

### Example Worker Log
```
2025-11-28 20:08:xx INFO automation-worker: Automation worker V2 starting with 4 rules
2025-11-28 20:08:xx INFO automation-worker: Rule temperature_alerts: Temperature 15.0°C below minimum 18.0°C -> 0 commands, 1 alerts
2025-11-28 20:08:xx INFO automation-worker: Device 11111111... automation: 0 commands, 1 alerts
```

---

## Database Credentials (Demo)
- User: demo@plant.local / demo1234
- Device ID: 11111111-1111-1111-1111-111111111111
- Device Secret: demo-device-secret

---

**Status**: Core refactoring complete and working. Automation logs table pending (optional feature).
