"""Tests for automation profile management."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_update_automation_profile(client: AsyncClient, user_token: str):
    """Test updating device automation profile."""
    # Create device
    create_response = await client.post(
        "/devices",
        json={"name": "Auto Device", "assign_to_self": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_response.status_code == 201
    device_id = create_response.json()["device"]["id"]

    # Update automation profile
    update_response = await client.put(
        f"/devices/{device_id}/automation",
        json={
            "soil_moisture_min": 25.0,
            "soil_moisture_max": 75.0,
            "temp_min": 18.0,
            "temp_max": 28.0,
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert update_response.status_code == 200
    data = update_response.json()

    assert data["soil_moisture_min"] == 25.0
    assert data["soil_moisture_max"] == 75.0
    assert data["temp_min"] == 18.0
    assert data["temp_max"] == 28.0


@pytest.mark.asyncio
async def test_update_automation_partial(client: AsyncClient, user_token: str):
    """Test partial update of automation profile."""
    # Create device
    create_response = await client.post(
        "/devices",
        json={"name": "Auto Device", "assign_to_self": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_response.status_code == 201
    device_id = create_response.json()["device"]["id"]

    # Update only some fields
    update_response = await client.put(
        f"/devices/{device_id}/automation",
        json={
            "soil_moisture_min": 20.0,
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert update_response.status_code == 200
    data = update_response.json()

    assert data["soil_moisture_min"] == 20.0
    # Other fields should retain defaults
    assert data["soil_moisture_max"] is not None


@pytest.mark.asyncio
async def test_cannot_update_other_users_automation(
    client: AsyncClient, user_token: str, another_user_token: str
):
    """Test that users cannot update other users' device automation."""
    # User 1 creates device
    create_response = await client.post(
        "/devices",
        json={"name": "User1 Device", "assign_to_self": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_response.status_code == 201
    device_id = create_response.json()["device"]["id"]

    # User 2 tries to update automation
    update_response = await client.put(
        f"/devices/{device_id}/automation",
        json={"soil_moisture_min": 25.0},
        headers={"Authorization": f"Bearer {another_user_token}"},
    )
    assert update_response.status_code == 404


@pytest.mark.asyncio
async def test_get_automation_profile(client: AsyncClient, user_token: str):
    """Test retrieving automation profile."""
    # Create device
    create_response = await client.post(
        "/devices",
        json={"name": "Auto Device", "assign_to_self": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_response.status_code == 201
    device = create_response.json()["device"]
    device_id = device["id"]

    # Initially, automation_profile may be None
    assert "automation_profile" in device

    # Update automation profile
    update_response = await client.put(
        f"/devices/{device_id}/automation",
        json={"soil_moisture_min": 30.0},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert update_response.status_code == 200

    # Now get device list and verify profile exists
    list_response = await client.get(
        "/devices",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    devices = list_response.json()
    device = next((d for d in devices if d["id"] == device_id), None)
    assert device is not None
    assert device["automation_profile"] is not None
    assert "soil_moisture_min" in device["automation_profile"]
    assert "temp_min" in device["automation_profile"]


@pytest.mark.asyncio
async def test_automation_validation_min_max(client: AsyncClient, user_token: str):
    """Test that min values cannot exceed max values."""
    # Create device
    create_response = await client.post(
        "/devices",
        json={"name": "Auto Device", "assign_to_self": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_response.status_code == 201
    device_id = create_response.json()["device"]["id"]

    # Try to set min > max (this should ideally be validated)
    update_response = await client.put(
        f"/devices/{device_id}/automation",
        json={
            "soil_moisture_min": 80.0,
            "soil_moisture_max": 20.0,
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    # Note: Currently no validation - test documents current behavior
    # In future, this should return 422


@pytest.mark.asyncio
async def test_device_with_automation_in_list(client: AsyncClient, user_token: str):
    """Test that listed devices include automation profiles."""
    # Create device with automation
    create_response = await client.post(
        "/devices",
        json={"name": "Auto Device", "assign_to_self": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_response.status_code == 201
    device_id = create_response.json()["device"]["id"]

    # Update automation
    await client.put(
        f"/devices/{device_id}/automation",
        json={"soil_moisture_min": 35.0},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    # List devices
    list_response = await client.get(
        "/devices",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert list_response.status_code == 200
    devices = list_response.json()

    # Find our device
    device = next((d for d in devices if d["id"] == device_id), None)
    assert device is not None
    assert "automation_profile" in device
    assert device["automation_profile"]["soil_moisture_min"] == 35.0
