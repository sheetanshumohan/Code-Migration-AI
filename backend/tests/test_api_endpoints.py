"""
Integration Tests for FastAPI Endpoints
Verifies health check, OpenAPI documentation, and API routing.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check_endpoint():
    """Verify that the health check endpoint returns 200 OK with polyglot subsystem status."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"  # type: ignore
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert data["service"] == "codemigration-api"
        assert "polyglot_persistence" in data


@pytest.mark.asyncio
async def test_openapi_schema_endpoint():
    """Verify that the OpenAPI JSON schema is generated correctly."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"  # type: ignore
    ) as client:
        response = await client.get("/api/v1/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "Code Migration AI"
