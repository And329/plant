"""Test configuration and fixtures."""
import asyncio
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.deps import get_db_session
from app.models.entities import Base, User
from main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db():
    """Create a test database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    yield async_session_maker

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_db) -> AsyncGenerator[AsyncSession, None]:
    """Get a test database session."""
    async with test_db() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_db) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database override."""
    from app.core.config import Settings
    from app.deps import get_app_settings

    async def override_get_db():
        async with test_db() as session:
            yield session

    def override_get_settings():
        return Settings(admin_emails=["admin@plant.local"])

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_app_settings] = override_get_settings

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user."""
    user = User(
        id=uuid4(),
        email="admin@plant.local",
        password_hash=get_password_hash("admin123456"),
        locale="en",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> User:
    """Create a regular user."""
    user = User(
        id=uuid4(),
        email="user@example.com",
        password_hash=get_password_hash("user123456"),
        locale="en",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def another_user(db_session: AsyncSession) -> User:
    """Create another user for isolation testing."""
    user = User(
        id=uuid4(),
        email="other@example.com",
        password_hash=get_password_hash("other123456"),
        locale="en",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, admin_user: User) -> str:
    """Get an admin access token."""
    response = await client.post(
        "/auth/login",
        json={"email": "admin@plant.local", "password": "admin123456"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def user_token(client: AsyncClient, regular_user: User) -> str:
    """Get a regular user access token."""
    response = await client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "user123456"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def another_user_token(client: AsyncClient, another_user: User) -> str:
    """Get another user's access token."""
    response = await client.post(
        "/auth/login",
        json={"email": "other@example.com", "password": "other123456"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]
