"""
Integration Tests for Payment & Subscriptions Subsystem (Stripe)
Verifies checkout session creation, validation, and webhook processing for plan upgrades.
"""

from unittest.mock import patch, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.postgres.models import Organization

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def authenticated_user_token(async_client: AsyncClient) -> str:
    """Helper fixture to create a user and return an auth token."""
    payload = {
        "email": "subscriber@enterprise.com",
        "full_name": "Subscriber User",
        "password": "SecurePassword123!",
        "organization_name": "Subscription Test Org",
    }
    # Register (which logs in)
    response = await async_client.post("/api/v1/auth/register", json=payload)
    if response.status_code == 400:
        # If user already exists, just login
        login_resp = await async_client.post(
            "/api/v1/auth/login",
            data={"username": payload["email"], "password": payload["password"]},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        return str(login_resp.json()["access_token"])
    
    return str(response.json()["access_token"])


async def test_create_checkout_session_invalid_plan(async_client: AsyncClient, authenticated_user_token: str):
    """Verify that requesting an unknown plan fails with 400."""
    headers = {"Authorization": f"Bearer {authenticated_user_token}"}
    
    response = await async_client.post(
        "/api/v1/subscriptions/create-checkout-session?plan=hacker",
        headers=headers
    )
    assert response.status_code == 400
    assert "Invalid plan" in response.json()["detail"]


@patch("app.api.v1.subscriptions.stripe.checkout.Session.create")
async def test_create_checkout_session_success(mock_stripe_create, async_client: AsyncClient, authenticated_user_token: str):
    """Verify that a valid plan creates a stripe session and returns a URL."""
    # Mock the stripe API return value
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/test_url_123"
    mock_stripe_create.return_value = mock_session

    headers = {"Authorization": f"Bearer {authenticated_user_token}"}
    
    response = await async_client.post(
        "/api/v1/subscriptions/create-checkout-session?plan=pro",
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert data["url"] == "https://checkout.stripe.com/test_url_123"
    mock_stripe_create.assert_called_once()


@patch("app.api.v1.subscriptions.stripe.checkout.Session.retrieve")
async def test_confirm_checkout_session_success(mock_stripe_retrieve, async_client: AsyncClient, authenticated_user_token: str, db_session: AsyncSession):
    """Verify that confirming a paid session upgrades the user's organization plan."""
    
    # Mock the Stripe Session retrieval
    mock_session = MagicMock()
    mock_session.payment_status = "paid"
    mock_session.metadata = {"plan_tier": "pro"}
    mock_session.customer = "cus_12345"
    mock_session.subscription = "sub_12345"
    mock_session.to_dict.return_value = {
        "payment_status": "paid",
        "metadata": {"plan_tier": "pro"},
        "customer": "cus_12345",
        "subscription": "sub_12345"
    }
    mock_stripe_retrieve.return_value = mock_session

    headers = {"Authorization": f"Bearer {authenticated_user_token}"}
    
    response = await async_client.post(
        "/api/v1/subscriptions/confirm-session",
        json={"session_id": "cs_test_12345"},
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["plan_tier"] == "pro"

    # Let's fetch the user's organization from the DB to ensure plan_tier updated
    # First get the user to find org_id
    from app.infrastructure.database.postgres.models import User
    user_stmt = select(User).where(User.email == "subscriber@enterprise.com")
    user = (await db_session.execute(user_stmt)).scalar_one()
    
    org_stmt = select(Organization).where(Organization.id == user.organization_id)
    org = (await db_session.execute(org_stmt)).scalar_one()
    
    assert org.plan_tier == "pro"
    assert org.stripe_customer_id == "cus_12345"
    assert org.stripe_subscription_id == "sub_12345"


@patch("app.api.v1.subscriptions.stripe.checkout.Session.retrieve")
async def test_confirm_checkout_session_unpaid(mock_stripe_retrieve, async_client: AsyncClient, authenticated_user_token: str):
    """Verify that attempting to confirm an unpaid session is rejected."""
    
    # Mock an unpaid session
    mock_session = MagicMock()
    mock_session.to_dict.return_value = {
        "payment_status": "unpaid",
        "metadata": {"plan_tier": "pro"}
    }
    mock_stripe_retrieve.return_value = mock_session

    headers = {"Authorization": f"Bearer {authenticated_user_token}"}
    
    response = await async_client.post(
        "/api/v1/subscriptions/confirm-session",
        json={"session_id": "cs_test_unpaid_123"},
        headers=headers
    )
    
    assert response.status_code == 400
    assert "not complete" in response.json()["detail"]
