"""
Pytest Test Fixtures and Global Configuration
"""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.postgres.session import Base, get_async_db
from app.main import app

# In-memory async SQLite engine for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session", autouse=True)
async def cleanup_engine():
    """Dispose the test engine at session teardown to prevent hanging threads."""
    yield
    await test_engine.dispose()


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Create fresh database tables before each test and drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """Yields an isolated async session for direct DB operations in tests."""
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient]:
    """Async HTTP test client fixture with DB dependency override."""
    async def override_get_async_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_async_db] = override_get_async_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def mock_redis_engine(monkeypatch):
    """Provide an isolated in-memory mock for redis_engine during testing."""
    storage: dict[str, Any] = {}

    async def mock_get_json(key: str) -> Any | None:
        return storage.get(key)

    async def mock_set_json(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        storage[key] = value
        return True

    async def mock_delete(key: str) -> bool:
        return storage.pop(key, None) is not None

    async def mock_publish_workflow_event(workflow_id: str, event_data: dict) -> int:
        history_key = f"workflow_events:{workflow_id}"
        storage.setdefault(history_key, []).append(event_data)
        return 1

    async def mock_get_workflow_events(workflow_id: str) -> list[dict]:
        return storage.get(f"workflow_events:{workflow_id}", [])

    async def mock_connect() -> None:
        pass

    async def mock_close() -> None:
        pass

    import stripe

    from app.core.config import settings
    from app.infrastructure.database.neo4j.driver import neo4j_engine
    from app.infrastructure.database.qdrant.client import qdrant_engine
    from app.infrastructure.database.redis.client import redis_engine
    stripe.api_key = "sk_test_mock_stripe_key_for_testing"
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_stripe_key_for_testing")

    monkeypatch.setattr(redis_engine, "get_json", mock_get_json)
    monkeypatch.setattr(redis_engine, "set_json", mock_set_json)
    monkeypatch.setattr(redis_engine, "delete", mock_delete)
    monkeypatch.setattr(redis_engine, "publish_workflow_event", mock_publish_workflow_event)
    monkeypatch.setattr(redis_engine, "get_workflow_events", mock_get_workflow_events)
    monkeypatch.setattr(redis_engine, "connect", mock_connect)
    monkeypatch.setattr(redis_engine, "close", mock_close)
    monkeypatch.setattr(redis_engine, "_ensure_redis", AsyncMock(return_value=None))

    monkeypatch.setattr(neo4j_engine, "connect", mock_connect)
    monkeypatch.setattr(neo4j_engine, "close", mock_close)
    monkeypatch.setattr(qdrant_engine, "connect", mock_connect)
    monkeypatch.setattr(qdrant_engine, "close", mock_close)


