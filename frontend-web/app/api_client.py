"""HTTP client for communicating with the Plant Automation backend API."""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx
from fastapi import Request

logger = logging.getLogger(__name__)


class APIClient:
    """HTTP client for backend API calls with JWT token management."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        """Initialize API client.

        Args:
            base_url: Backend API base URL (e.g., http://api:8000)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    def _get_auth_header(self, request: Request) -> dict[str, str]:
        """Get authorization header from session token."""
        access_token = request.session.get("access_token")
        if not access_token:
            return {}
        return {"Authorization": f"Bearer {access_token}"}

    async def _request(
        self,
        method: str,
        path: str,
        request: Request | None = None,
        **kwargs,
    ) -> httpx.Response:
        """Make HTTP request to backend API.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., /users/me)
            request: FastAPI request object for auth headers
            **kwargs: Additional arguments for httpx request

        Returns:
            httpx.Response object
        """
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})

        if request:
            headers.update(self._get_auth_header(request))

        response = await self._client.request(method, url, headers=headers, **kwargs)
        return response

    # Authentication
    async def login(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate user and get JWT tokens.

        Args:
            email: User email
            password: User password

        Returns:
            Dict with access_token, refresh_token, and user info

        Raises:
            httpx.HTTPStatusError: If authentication fails
        """
        response = await self._request(
            "POST",
            "/auth/login",
            json={"email": email, "password": password},
        )
        response.raise_for_status()
        return response.json()

    async def register(self, email: str, password: str, locale: str | None = None) -> dict[str, Any]:
        """Register new user.

        Args:
            email: User email
            password: User password
            locale: User locale (optional)

        Returns:
            User object

        Raises:
            httpx.HTTPStatusError: If registration fails
        """
        response = await self._request(
            "POST",
            "/users",
            json={"email": email, "password": password, "locale": locale},
        )
        response.raise_for_status()
        return response.json()

    async def get_current_user(self, request: Request) -> dict[str, Any]:
        """Get current user profile.

        Args:
            request: FastAPI request with auth token

        Returns:
            User object
        """
        response = await self._request("GET", "/users/me", request=request)
        response.raise_for_status()
        return response.json()

    # Devices
    async def list_devices(self, request: Request) -> list[dict[str, Any]]:
        """List all devices for authenticated user.

        Args:
            request: FastAPI request with auth token

        Returns:
            List of device objects
        """
        response = await self._request("GET", "/devices", request=request)
        response.raise_for_status()
        return response.json()

    async def get_device(self, device_id: UUID, request: Request) -> dict[str, Any]:
        """Get device details.

        Args:
            device_id: Device UUID
            request: FastAPI request with auth token

        Returns:
            Device object with sensors, actuators, and automation profile
        """
        response = await self._request("GET", f"/devices/{device_id}", request=request)
        response.raise_for_status()
        return response.json()

    async def get_device_config(self, device_id: UUID, request: Request) -> dict[str, Any]:
        """Get device config (IDs for sensors/actuators)."""
        response = await self._request("GET", f"/devices/{device_id}/config", request=request)
        response.raise_for_status()
        return response.json()

    async def create_device(
        self,
        name: str,
        request: Request,
        model: str | None = None,
        owner_email: str | None = None,
        assign_to_self: bool = True,
    ) -> dict[str, Any]:
        """Create new device (admin only).

        Args:
            name: Device name
            request: FastAPI request with auth token
            model: Device model (optional)
            owner_email: Owner email (optional)

        Returns:
            Device object with secret
        """
        payload = {"name": name}
        if model:
            payload["model"] = model
        if owner_email:
            payload["owner_email"] = owner_email
        payload["assign_to_self"] = assign_to_self

        response = await self._request("POST", "/devices", request=request, json=payload)
        response.raise_for_status()
        return response.json()

    async def delete_device(self, device_id: UUID, request: Request) -> None:
        """Delete a device."""
        response = await self._request("DELETE", f"/devices/{device_id}", request=request)
        response.raise_for_status()

    async def claim_device(self, device_id: UUID, device_secret: str, request: Request) -> dict[str, Any]:
        """Claim a device to user account.

        Args:
            device_id: Device UUID
            device_secret: Device secret
            request: FastAPI request with auth token

        Returns:
            Updated device object
        """
        response = await self._request(
            "POST",
            "/devices/claim",
            request=request,
            json={"device_id": str(device_id), "device_secret": device_secret},
        )
        response.raise_for_status()
        return response.json()

    # Automation
    async def get_automation_profile(self, device_id: UUID, request: Request) -> dict[str, Any] | None:
        """Get automation profile for device.

        Args:
            device_id: Device UUID
            request: FastAPI request with auth token

        Returns:
            Automation profile or None
        """
        response = await self._request("GET", f"/devices/{device_id}/automation", request=request)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def update_automation_profile(
        self,
        device_id: UUID,
        request: Request,
        **profile_data,
    ) -> dict[str, Any]:
        """Update automation profile for device.

        Args:
            device_id: Device UUID
            request: FastAPI request with auth token
            **profile_data: Automation profile fields

        Returns:
            Updated automation profile
        """
        response = await self._request(
            "PUT",
            f"/devices/{device_id}/automation",
            request=request,
            json=profile_data,
        )
        response.raise_for_status()
        return response.json()

    # Telemetry
    async def get_latest_readings(self, device_id: UUID, request: Request) -> dict[str, Any]:
        """Get latest sensor readings for device.

        Args:
            device_id: Device UUID
            request: FastAPI request with auth token

        Returns:
            Dict with device_id and readings list
        """
        response = await self._request("GET", f"/telemetry/latest/{device_id}", request=request)
        response.raise_for_status()
        return response.json()

    # Commands
    async def send_command(
        self,
        device_id: UUID,
        actuator_id: UUID,
        command_type: str,
        request: Request,
        duration_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Send manual command to device.

        Args:
            device_id: Device UUID
            actuator_id: Actuator UUID
            command_type: Command type (e.g., PUMP_ON, LAMP_OFF)
            request: FastAPI request with auth token
            duration_seconds: Command duration (optional)

        Returns:
            Command object
        """
        payload = {"actuator_id": str(actuator_id), "command": command_type}
        if duration_seconds is not None:
            payload["duration_seconds"] = duration_seconds

        response = await self._request(
            "POST",
            f"/commands/devices/{device_id}",
            request=request,
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    # Alerts
    async def list_alerts(self, request: Request, device_id: UUID | None = None) -> list[dict[str, Any]]:
        """List alerts for user.

        Args:
            request: FastAPI request with auth token
            device_id: Filter by device ID (optional)

        Returns:
            List of alert objects
        """
        response = await self._request("GET", "/alerts", request=request)
        response.raise_for_status()
        alerts = response.json()

        # Filter by device_id if provided
        if device_id:
            alerts = [a for a in alerts if a.get("device_id") == str(device_id)]

        return alerts

    async def resolve_alert(self, alert_id: UUID, request: Request) -> dict[str, Any]:
        """Mark alert as resolved.

        Args:
            alert_id: Alert UUID
            request: FastAPI request with auth token

        Returns:
            Updated alert object
        """
        response = await self._request("PATCH", f"/alerts/{alert_id}/resolve", request=request)
        response.raise_for_status()
        return response.json()


# Singleton instance
_api_client: APIClient | None = None


def get_api_client(base_url: str = "http://api:8000") -> APIClient:
    """Get or create API client instance.

    Args:
        base_url: Backend API base URL

    Returns:
        APIClient instance
    """
    global _api_client
    if _api_client is None:
        _api_client = APIClient(base_url)
    return _api_client
