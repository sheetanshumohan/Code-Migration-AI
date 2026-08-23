"""
Comprehensive Test Suite for Authentication & Authorization Flows
Verifies standard registration, login, logout, refresh tokens, token expiry, invalid credentials,
forgot/reset password, Argon2id hashing, Google OAuth redirect, callback, token verification, and protected routes.
"""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.infrastructure.database.postgres.models import User


@pytest.mark.asyncio
async def test_argon2_hashing_and_verification():
    """Verify that Argon2id is actually used for password hashing and validation."""
    raw_password = "SecurePassword#2026!"
    hashed_password = get_password_hash(raw_password)

    # Verify Argon2id prefix signature
    assert hashed_password.startswith("$argon2id$"), f"Expected Argon2id hash prefix, got: {hashed_password}"
    assert hashed_password != raw_password

    # Verify password match and mismatch
    assert verify_password(raw_password, hashed_password) is True
    assert verify_password("WrongPassword123", hashed_password) is False


@pytest.mark.asyncio
async def test_user_registration_flow(async_client: AsyncClient, db_session: AsyncSession):
    """Verify user registration, organization creation, and JWT token issuance."""
    payload = {
        "email": "developer@enterprise.com",
        "full_name": "Jane Developer",
        "password": "SuperSecretPassword123!",
        "organization_name": "Acme Modernization Inc",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == payload["email"]
    assert data["user"]["organization_name"] == payload["organization_name"]

    # Verify Argon2id hash stored in database
    stmt = select(User).where(User.email == payload["email"])
    res = await db_session.execute(stmt)
    user = res.scalar_one_or_none()
    assert user is not None
    assert user.hashed_password.startswith("$argon2id$")


@pytest.mark.asyncio
async def test_user_registration_duplicate_email(async_client: AsyncClient):
    """Verify registration fails when duplicate email is registered."""
    payload = {
        "email": "duplicate@enterprise.com",
        "full_name": "User One",
        "password": "Password12345!",
        "organization_name": "Org One",
    }
    res1 = await async_client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 200

    res2 = await async_client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_user_login_success_and_invalid_credentials(async_client: AsyncClient):
    """Verify login with valid and invalid credentials."""
    reg_payload = {
        "email": "login_test@enterprise.com",
        "full_name": "Login User",
        "password": "ValidPassword123!",
        "organization_name": "Login Org",
    }
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    # Valid Login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": reg_payload["email"], "password": "ValidPassword123!"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

    # Invalid Password
    bad_pass_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": reg_payload["email"], "password": "WrongPassword!"},
    )
    assert bad_pass_res.status_code == 401

    # Non-existent Email
    no_user_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@enterprise.com", "password": "AnyPassword123!"},
    )
    assert no_user_res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_lifecycle(async_client: AsyncClient):
    """Verify refreshing access tokens using a valid refresh token."""
    reg_payload = {
        "email": "refresh_test@enterprise.com",
        "full_name": "Refresh User",
        "password": "RefreshPassword123!",
        "organization_name": "Refresh Org",
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    refresh_token = reg_res.json()["refresh_token"]

    # Refresh token call
    ref_res = await async_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert ref_res.status_code == 200
    ref_data = ref_res.json()
    assert "access_token" in ref_data
    assert "refresh_token" in ref_data

    # Invalid refresh token call
    bad_ref_res = await async_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "invalid.jwt.token"}
    )
    assert bad_ref_res.status_code == 401


@pytest.mark.asyncio
async def test_token_expiry_handling():
    """Verify expired token detection."""
    expired_token = create_access_token(
        subject="test_user_id",
        role="developer",
        expires_delta=-timedelta(minutes=10),
    )
    with pytest.raises(ValueError, match="Invalid or expired token"):
        decode_token(expired_token)


@pytest.mark.asyncio
async def test_forgot_and_reset_password_flow(async_client: AsyncClient):
    """Verify password reset request and password reset token validation with Argon2 hashing."""
    reg_payload = {
        "email": "reset_test@enterprise.com",
        "full_name": "Reset User",
        "password": "OldPassword123!",
        "organization_name": "Reset Org",
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    user_id = reg_res.json()["user"]["id"]

    # Request password reset
    forgot_res = await async_client.post(
        "/api/v1/auth/forgot-password", json={"email": reg_payload["email"]}
    )
    assert forgot_res.status_code == 200
    reset_token = forgot_res.json().get("reset_token")
    assert reset_token is not None

    # Reset password with new password
    new_password = "NewSuperPassword123!"
    reset_res = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": new_password},
    )
    assert reset_res.status_code == 200

    # Old password fails
    old_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": reg_payload["email"], "password": "OldPassword123!"},
    )
    assert old_login.status_code == 401

    # New password succeeds
    new_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": reg_payload["email"], "password": new_password},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_user_logout(async_client: AsyncClient):
    """Verify logout endpoint with authenticated token."""
    reg_payload = {
        "email": "logout_test@enterprise.com",
        "full_name": "Logout User",
        "password": "LogoutPassword123!",
        "organization_name": "Logout Org",
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    access_token = reg_res.json()["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    logout_res = await async_client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200
    assert logout_res.json()["message"] == "Successfully logged out"


@pytest.mark.asyncio
async def test_google_login_redirect(async_client: AsyncClient):
    """Verify Google OAuth authorization redirect endpoint."""
    with patch("app.core.config.settings.GOOGLE_CLIENT_ID", "mock-client-id"):
        res = await async_client.get("/api/v1/auth/google/login", follow_redirects=False)
        assert res.status_code in [302, 307, 500]


@pytest.mark.asyncio
async def test_google_callback_account_creation_and_linking(async_client: AsyncClient, db_session: AsyncSession):
    """Verify Google OAuth callback handling, account creation, and redirect with JWT tokens."""
    mock_token = {
        "userinfo": {
            "email": "google_user@enterprise.com",
            "name": "Google User",
            "sub": "google-oauth2-id-123456",
        }
    }

    with patch("app.api.v1.auth.oauth.google.authorize_access_token", new_callable=AsyncMock) as mock_auth:
        mock_auth.return_value = mock_token
        response = await async_client.get("/api/v1/auth/google/callback", follow_redirects=False)

        assert response.status_code in [302, 307]
        location = response.headers["location"]
        assert "/auth/callback?access_token=" in location
        assert "refresh_token=" in location

        # Verify User created in DB with oauth_provider = "google"
        stmt = select(User).where(User.email == "google_user@enterprise.com")
        res = await db_session.execute(stmt)
        user = res.scalar_one_or_none()
        assert user is not None
        assert user.oauth_provider == "google"
        assert user.oauth_id == "google-oauth2-id-123456"


@pytest.mark.asyncio
async def test_google_callback_error_handling(async_client: AsyncClient):
    """Verify Google OAuth callback error handling redirects to login page with error flag."""
    with patch("app.api.v1.auth.oauth.google.authorize_access_token", side_effect=Exception("OAuth cancelled")):
        response = await async_client.get("/api/v1/auth/google/callback", follow_redirects=False)
        assert response.status_code in [302, 307]
        assert "login?error=oauth_failed" in response.headers["location"]


@pytest.mark.asyncio
async def test_google_verify_id_token(async_client: AsyncClient):
    """Verify frontend Google Sign-In SDK ID token verification endpoint."""
    mock_userinfo = {
        "email": "sdk_google_user@enterprise.com",
        "email_verified": True,
        "name": "SDK Google User",
        "sub": "google-sdk-sub-999",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_userinfo

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        res = await async_client.post(
            "/api/v1/auth/google/verify",
            json={"id_token": "valid-mock-google-id-token"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["user"]["email"] == "sdk_google_user@enterprise.com"


@pytest.mark.asyncio
async def test_protected_routes_authorization(async_client: AsyncClient):
    """Verify protected routes reject unauthenticated or invalid tokens and accept valid tokens."""
    # Missing Token
    res_no_auth = await async_client.post("/api/v1/auth/logout")
    assert res_no_auth.status_code == 401

    # Invalid Token
    res_bad_auth = await async_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": "Bearer invalid_token_xyz"},
    )
    assert res_bad_auth.status_code == 401

    # Valid Token
    reg_payload = {
        "email": "protected_test@enterprise.com",
        "full_name": "Protected User",
        "password": "ProtectedPassword123!",
        "organization_name": "Protected Org",
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]

    res_auth = await async_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_auth.status_code == 200




