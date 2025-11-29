# Backend API Tests

Comprehensive test suite for the Plant Automation Backend API.

## Test Coverage

### Integration Tests (`test_integration.py`) - 8 tests ⭐ NEW!
- **Device activation and authentication workflow**
- **Telemetry ingestion and retrieval**
- Automation triggers pump on low moisture
- Automation creates temperature alerts
- User issues manual commands to actuators
- Device command lifecycle (issue, fetch, acknowledge)
- Automation rules with various sensor conditions
- Multi-device isolation

### Authentication Tests (`test_auth.py`) - 10 tests
- User registration (success, duplicate email, validation)
- User login (success, wrong credentials)
- Token-based authentication
- Current user retrieval
- Invalid token handling

### Device Management Tests (`test_devices.py`) - 12 tests
- Device provisioning (assigned, unassigned, to specific email)
- Device listing with proper isolation between users
- Device deletion (own devices, unassigned devices)
- Access control (preventing access to other users' devices)
- Device authentication with secrets
- Device configuration access control

### Automation Tests (`test_automation.py`) - 6 tests
- Automation profile creation and updates
- Partial profile updates
- Access control for automation profiles
- Profile retrieval and listing

### Admin Tests (`test_admin.py`) - 14 tests
- Admin can list unclaimed devices with `?include_unclaimed=true`
- Admin default view shows only their own devices
- Regular users cannot access unclaimed devices
- Admin can provision devices for other users
- Admin can delete unclaimed devices
- Admin isolation (admins don't see each other's devices)
- Multiple unclaimed devices listing
- Admin automation profile management
- **Device claiming workflow**: Admin provisions, user claims
- User cannot claim with wrong secret
- User cannot claim already-claimed device
- User can reclaim their own device (idempotent)
- Claim nonexistent device fails

## Running Tests

### Install Dependencies
```bash
pip install -e ".[dev]"
```

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest tests/test_auth.py
```

### Run with Coverage
```bash
pytest --cov=app --cov-report=html
```

### Run with Verbose Output
```bash
pytest -v
```

## Test Database

Tests use an in-memory SQLite database that is created and destroyed for each test session. This ensures tests are isolated and don't affect production data.

## Key Test Scenarios

### User Isolation
- Users can only see their own devices
- Users cannot access other users' device configs
- Users cannot delete other users' devices
- Users cannot modify other users' automation profiles
- Even admins are isolated from each other's devices by default

### Device Provisioning
- Devices can be provisioned as assigned or unassigned
- Devices can be assigned to specific users by email
- Unassigned devices don't appear in regular user listings
- Device secrets are properly validated during authentication

### Automation
- Automation profiles are created on first update
- Partial updates preserve existing values
- Profiles are included in device listings

### Admin Privileges
- Admins can list unclaimed devices with `?include_unclaimed=true` query parameter
- Admins can provision devices for other users by email
- Admins can delete unclaimed devices
- Regular users cannot access unclaimed devices even with query parameter
- Admin's default device list shows only their own devices (not unclaimed)

### Device Claiming Workflow
- Admin provisions unclaimed device and receives device_id + secret
- Unclaimed device appears in admin's unclaimed list
- Unclaimed device does NOT appear in regular user's list
- User claims device using device_id and secret via `/devices/claim`
- Claimed device now appears in user's device list
- Claimed device removed from admin's unclaimed list
- Security: Wrong secret prevents claiming
- Security: Cannot claim already-claimed device (belongs to another user)
- Idempotent: User can reclaim their own device

### Virtual Device Integration & Automation
- **Device Activation:** Device provisions, authenticates, and fetches commands
- **Telemetry Flow:** Device sends sensor readings, user retrieves latest values
- **Automation Triggers:** Low moisture triggers pump commands (tested structure)
- **Temperature Alerts:** High/low temps create alerts (tested structure)
- **Manual Control:** Users issue commands (pump/lamp on/off)
- **Command Lifecycle:** Commands issued → device fetches → device acknowledges
- **Status Tracking:** Command status transitions (pending → acked/failed)
- **Multi-Device Isolation:** Commands isolated per device
