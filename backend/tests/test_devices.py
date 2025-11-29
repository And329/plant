"""Tests for device provisioning and management."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Device


@pytest.mark.asyncio
async def test_provision_device_success(client: AsyncClient, user_token: str):
    """Test successful device provisioning."""
    response = await client.post(
        "/devices",
        json={
            "name": "Test Device",
            "model": "v1.0",
            "assign_to_self": True,
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 201
    data = response.json()

    assert data["device"]["name"] == "Test Device"
    assert data["device"]["model"] == "v1.0"
    assert "id" in data["device"]
    assert "secret" in data
    assert "sensor_ids" in data
    assert "actuator_ids" in data

    # Verify default sensors and actuators are created
    assert "soil_moisture" in data["sensor_ids"]
    assert "air_temperature" in data["sensor_ids"]
    assert "pump" in data["actuator_ids"]


@pytest.mark.asyncio
async def test_provision_device_unassigned(
    client: AsyncClient, user_token: str, db_session: AsyncSession
):
    """Test provisioning device without assignment."""
    response = await client.post(
        "/devices",
        json={
            "name": "Unassigned Device",
            "model": "v1.0",
            "assign_to_self": False,
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 201
    data = response.json()

    # Check device is created but unassigned
    device_id = data["device"]["id"]
    result = await db_session.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one()
    assert device.user_id is None


@pytest.mark.asyncio
async def test_provision_device_assign_to_email(
    client: AsyncClient, user_token: str, another_user, db_session: AsyncSession
):
    """Test provisioning device and assigning to specific email."""
    response = await client.post(
        "/devices",
        json={
            "name": "Assigned Device",
            "model": "v1.0",
            "owner_email": "other@example.com",
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 201
    data = response.json()

    # Check device is assigned to the specified user
    device_id = data["device"]["id"]
    result = await db_session.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one()
    assert device.user_id == another_user.id


@pytest.mark.asyncio
async def test_provision_device_invalid_owner_email(
    client: AsyncClient, user_token: str
):
    """Test provisioning device with invalid owner email fails."""
    response = await client.post(
        "/devices",
        json={
            "name": "Test Device",
            "model": "v1.0",
            "owner_email": "nonexistent@example.com",
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_devices_shows_only_owned(
    client: AsyncClient, user_token: str, another_user_token: str, db_session: AsyncSession
):
    """Test that users only see their own devices."""
    # User 1 creates a device
    response1 = await client.post(
        "/devices",
        json={"name": "User1 Device", "assign_to_self": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response1.status_code == 201
    device1_id = response1.json()["device"]["id"]

    # User 2 creates a device
    response2 = await client.post(
        "/devices",
        json={"name": "User2 Device", "assign_to_self": True},
        headers={"Authorization": f"Bearer {another_user_token}"},
    )
    assert response2.status_code == 201
    device2_id = response2.json()["device"]["id"]

    # User 1 lists devices - should only see their own
    list_response = await client.get(
        "/devices",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert list_response.status_code == 200
    devices = list_response.json()
    device_ids = [d["id"] for d in devices]

    assert device1_id in device_ids
    assert device2_id not in device_ids


@pytest.mark.asyncio
async def test_list_devices_excludes_unassigned(
    client: AsyncClient, user_token: str
):
    """Test that regular users don't see unassigned devices."""
    # Create unassigned device
    response = await client.post(
        "/devices",
        json={"name": "Unassigned Device", "assign_to_self": False},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 201
    unassigned_id = response.json()["device"]["id"]

    # List devices - should not include unassigned
    list_response = await client.get(
        "/devices",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert list_response.status_code == 200
    devices = list_response.json()
    device_ids = [d["id"] for d in devices]

    assert unassigned_id not in device_ids


@pytest.mark.asyncio
async def test_delete_own_device(client: AsyncClient, user_token: str):
    """Test deleting owned device."""
    # Create device
    create_response = await client.post(
        "/devices",
        json={"name": "To Delete", "assign_to_self": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_response.status_code == 201
    device_id = create_response.json()["device"]["id"]

    # Delete device
    delete_response = await client.delete(
        f"/devices/{device_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert delete_response.status_code == 204

    # Verify device is gone
    list_response = await client.get(
        "/devices",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    devices = list_response.json()
    device_ids = [d["id"] for d in devices]
    assert device_id not in device_ids


@pytest.mark.asyncio
async def test_delete_unassigned_device(client: AsyncClient, user_token: str):
    """Test deleting unassigned device."""
    # Create unassigned device
    create_response = await client.post(
        "/devices",
        json={"name": "Unassigned", "assign_to_self": False},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_response.status_code == 201
    device_id = create_response.json()["device"]["id"]

    # Delete device
    delete_response = await client.delete(
        f"/devices/{device_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_cannot_delete_other_users_device(
    client: AsyncClient, user_token: str, another_user_token: str
):
    """Test that users cannot delete other users' devices."""
    # User 1 creates device
    create_response = await client.post(
        "/devices",
        json={"name": "User1 Device", "assign_to_self": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_response.status_code == 201
    device_id = create_response.json()["device"]["id"]

    # User 2 tries to delete User 1's device
    delete_response = await client.delete(
        f"/devices/{device_id}",
        headers={"Authorization": f"Bearer {another_user_token}"},
    )
    assert delete_response.status_code == 404


@pytest.mark.asyncio
async def test_device_config_access_control(
    client: AsyncClient, user_token: str, another_user_token: str
):
    """Test that users cannot access other users' device configs."""
    # User 1 creates device
    create_response = await client.post(
        "/devices",
        json={"name": "User1 Device", "assign_to_self": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_response.status_code == 201
    device_id = create_response.json()["device"]["id"]

    # User 2 tries to get config
    config_response = await client.get(
        f"/devices/{device_id}/config",
        headers={"Authorization": f"Bearer {another_user_token}"},
    )
    assert config_response.status_code == 404


@pytest.mark.asyncio
async def test_device_authentication(client: AsyncClient, user_token: str):
    """Test device authentication with secret."""
    # Create device
    create_response = await client.post(
        "/devices",
        json={"name": "Auth Test", "assign_to_self": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_response.status_code == 201
    device_id = create_response.json()["device"]["id"]
    device_secret = create_response.json()["secret"]

    # Authenticate as device
    auth_response = await client.post(
        "/auth/device",
        json={
            "device_id": device_id,
            "device_secret": device_secret,
        },
    )
    assert auth_response.status_code == 200
    data = auth_response.json()
    assert "access_token" in data
    assert "device" in data
    assert data["device"]["id"] == device_id


@pytest.mark.asyncio
async def test_device_authentication_wrong_secret(client: AsyncClient, user_token: str):
    """Test device authentication with wrong secret fails."""
    # Create device
    create_response = await client.post(
        "/devices",
        json={"name": "Auth Test", "assign_to_self": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_response.status_code == 201
    device_id = create_response.json()["device"]["id"]

    # Try to authenticate with wrong secret
    auth_response = await client.post(
        "/auth/device",
        json={
            "device_id": device_id,
            "device_secret": "wrong-secret",
        },
    )
    assert auth_response.status_code == 401
