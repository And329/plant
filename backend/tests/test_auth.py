"""Tests for authentication endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    """Test successful user registration."""
    response = await client.post(
        "/users",
        json={
            "email": "newuser@example.com",
            "password": "securepass123",
            "locale": "en",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["locale"] == "en"
    assert "id" in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_register_user_duplicate_email(client: AsyncClient, regular_user):
    """Test registration with duplicate email fails."""
    response = await client.post(
        "/users",
        json={
            "email": "user@example.com",
            "password": "securepass123",
            "locale": "en",
        },
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_user_short_password(client: AsyncClient):
    """Test registration with short password fails."""
    response = await client.post(
        "/users",
        json={
            "email": "newuser@example.com",
            "password": "short",
            "locale": "en",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_user_invalid_email(client: AsyncClient):
    """Test registration with invalid email fails."""
    response = await client.post(
        "/users",
        json={
            "email": "not-an-email",
            "password": "securepass123",
            "locale": "en",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, regular_user):
    """Test successful login."""
    response = await client.post(
        "/auth/login",
        json={
            "email": "user@example.com",
            "password": "user123456",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert "expires_at" in data
    assert data["user"]["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, regular_user):
    """Test login with wrong password fails."""
    response = await client.post(
        "/auth/login",
        json={
            "email": "user@example.com",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Test login with nonexistent user fails."""
    response = await client.post(
        "/auth/login",
        json={
            "email": "nobody@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(client: AsyncClient, user_token):
    """Test getting current user info."""
    response = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_get_current_user_unauthorized(client: AsyncClient):
    """Test getting current user without token fails."""
    response = await client.get("/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(client: AsyncClient):
    """Test getting current user with invalid token fails."""
    response = await client.get(
        "/users/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401
