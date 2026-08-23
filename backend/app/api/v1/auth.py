"""
Authentication & Authorization API Routes
Enterprise JWT authentication, Argon2id verification, Registration, and Refresh tokens.
"""


import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt as _jwt
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.config import Config
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.api.deps import RateLimiter, get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.infrastructure.database.postgres.models import Organization, User
from app.infrastructure.database.postgres.session import get_async_db

logger = get_logger("codemigration.auth")

config_data: dict[str, str] = {}
if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
    config_data["GOOGLE_CLIENT_ID"] = settings.GOOGLE_CLIENT_ID
    config_data["GOOGLE_CLIENT_SECRET"] = settings.GOOGLE_CLIENT_SECRET

starlette_config = Config(environ=config_data)
oauth = OAuth(starlette_config)

oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_id=settings.GOOGLE_CLIENT_ID or "mock-google-client-id",
    client_secret=settings.GOOGLE_CLIENT_SECRET or "mock-google-client-secret",
    client_kwargs={'scope': 'openid email profile'}
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(..., min_length=10, description="Password must be at least 10 characters")
    organization_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

@router.post("/register", response_model=TokenResponse, dependencies=[Depends(RateLimiter(requests=5, window=60))])
async def register_user(req: RegisterRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_db)) -> Any:
    """Register a new user and create an initial organization."""
    email_clean = req.email.lower().strip()
    # Check if email exists
    stmt = select(User).where(User.email.ilike(email_clean))
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    base_slug = req.organization_name.lower().replace(" ", "-")[:40]
    org_slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"
    org = Organization(name=req.organization_name, slug=org_slug)
    db.add(org)
    await db.flush()

    hashed_pwd = await run_in_threadpool(get_password_hash, req.password)
    user = User(
        organization_id=org.id,
        email=email_clean,
        full_name=req.full_name,
        hashed_password=hashed_pwd,
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(subject=user.id, role=user.role, organization_id=str(org.id))
    refresh_token = create_refresh_token(subject=user.id, organization_id=str(org.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "organization_id": str(org.id),
            "organization_name": org.name,
        },
    )


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(RateLimiter(requests=10, window=60))])
async def login_user(req: LoginRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_db)) -> Any:
    """Authenticate with email and password."""
    email_clean = req.email.lower().strip()
    stmt = select(User).where(User.email.ilike(email_clean))
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")

    is_valid = await run_in_threadpool(verify_password, req.password, user.hashed_password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")

    access_token = create_access_token(subject=user.id, role=user.role, organization_id=str(user.organization_id))
    refresh_token = create_refresh_token(subject=user.id, organization_id=str(user.organization_id))

    org_stmt = select(Organization).where(Organization.id == user.organization_id)
    org_res = await db.execute(org_stmt)
    org = org_res.scalar_one_or_none()

    # Record cryptographic audit log
    from app.core.audit import record_audit_log
    await record_audit_log(
        db=db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="login",
        resource_type="auth_session",
        resource_id=str(user.id),
        metadata={"email": user.email, "method": "password"},
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "organization_id": str(user.organization_id),
            "organization_name": org.name if org else None,
            "plan_tier": org.plan_tier if org else "free",
        },
    )

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_route(req: RefreshRequest, db: AsyncSession = Depends(get_async_db)) -> Any:
    from app.core.security import decode_token
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise ValueError("No user ID in token")
        user_id = uuid.UUID(user_id_str)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    access_token = create_access_token(subject=user.id, role=user.role, organization_id=str(user.organization_id))
    new_refresh_token = create_refresh_token(subject=user.id, organization_id=str(user.organization_id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user={"id": str(user.id), "email": user.email, "full_name": user.full_name, "role": user.role, "organization_id": str(user.organization_id)}
    )

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession = Depends(get_async_db)) -> Any:
    stmt = select(User).where(User.email == req.email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    
    reset_token = None
    if user:
        # Use a dedicated token_type='reset' claim to prevent type confusion with access tokens
        to_encode = {
            "sub": str(user.id),
            "token_type": "reset",
            "exp": datetime.now(UTC) + timedelta(minutes=15),
        }
        reset_token = _jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        logger.info(f"🔗 [PASSWORD RESET LINK GENERATED for {user.email}]: token={reset_token}")

    return {
        "message": "If that email is in our system, a reset token has been generated.",
        "reset_token": reset_token
    }



class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=10)

@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_async_db)) -> Any:
    from app.core.security import decode_token
    try:
        payload = decode_token(req.token)
        # Validate the token is specifically a reset token (not a standard user access or refresh token)
        is_reset = (
            payload.get("token_type") == "reset"
            or payload.get("role") == "reset"
            or payload.get("type") == "reset"
        )
        if not is_reset:
            raise ValueError("Not a reset token")
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise ValueError("No user ID in token")
        user_id = uuid.UUID(user_id_str)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    hashed_pwd = await run_in_threadpool(get_password_hash, req.new_password)
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.hashed_password = hashed_pwd
    await db.commit()
    return {"message": "Password successfully reset."}

@router.post("/logout")
async def logout_user(current_user: User = Depends(get_current_user)) -> Any:
    """Logout endpoint to acknowledge session termination and audit user sign-out."""
    logger.info(f"User {current_user.id} logged out.")
    return {"message": "Successfully logged out"}


@router.get("/me")
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Return the full profile of the currently authenticated user including organization name."""
    org = await db.scalar(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "organization_id": str(current_user.organization_id),
        "organization_name": org.name if org else None,
        "plan_tier": org.plan_tier if org else "free",
        "oauth_provider": current_user.oauth_provider,
        "is_active": current_user.is_active,
    }


@router.get("/google/login")
async def google_login(request: Request):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on the server. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend environment variables.",
        )
        
    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    if origin:
        from urllib.parse import urlparse
        parsed = urlparse(origin)
        if parsed.scheme and parsed.netloc:
            request.session["frontend_url"] = f"{parsed.scheme}://{parsed.netloc}"
            
    redirect_uri = str(request.url_for('google_callback'))
    # Ensure HTTPS for production proxy deployments (Render, Cloudflare, etc.)
    if redirect_uri.startswith("http://") and "localhost" not in redirect_uri and "127.0.0.1" not in redirect_uri:
        redirect_uri = redirect_uri.replace("http://", "https://", 1)
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_async_db)):
    frontend_base = request.session.get("frontend_url") or settings.FRONTEND_URL.rstrip('/')

    try:
        token = await oauth.google.authorize_access_token(request)
        userinfo = token.get('userinfo')
        if not userinfo:
            raise ValueError("No userinfo returned from Google OAuth")
    except Exception as e:
        logger.error(f"Google Auth Error: {e}")
        return RedirectResponse(f"{frontend_base}/login?error=oauth_failed")

    email = userinfo.get("email")
    if not email:
        return RedirectResponse(f"{frontend_base}/login?error=oauth_failed")

    full_name = userinfo.get("name", "Google User")

    stmt = select(User).where(User.email == email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        org_slug = f"org-{uuid.uuid4().hex[:8]}"
        org = Organization(name=f"{full_name}'s Org", slug=org_slug)
        db.add(org)
        await db.flush()

        user = User(
            organization_id=org.id,
            email=email,
            full_name=full_name,
            oauth_provider="google",
            oauth_id=userinfo.get("sub"),
            role="admin",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    access_token = create_access_token(subject=user.id, role=user.role, organization_id=str(user.organization_id))
    refresh_token = create_refresh_token(subject=user.id, organization_id=str(user.organization_id))

    redirect_url = f"{frontend_base}/auth/callback?access_token={access_token}&refresh_token={refresh_token}"
    return RedirectResponse(redirect_url)


class GoogleVerifyRequest(BaseModel):
    id_token: str


@router.post("/google/verify", response_model=TokenResponse)
async def google_verify_token(req: GoogleVerifyRequest, db: AsyncSession = Depends(get_async_db)) -> Any:
    """Verify a Google ID token provided by frontend Google Sign-In SDK."""
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": req.id_token},
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Google OAuth ID token.",
            )
        userinfo = resp.json()

    email = userinfo.get("email")
    email_verified = userinfo.get("email_verified")
    is_verified = (email_verified is True) or (str(email_verified).lower() in ("true", "1"))
    if not email or not is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unverified email or missing email in Google OAuth token.",
        )

    full_name = userinfo.get("name", email.split("@")[0])
    stmt = select(User).where(User.email == email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        org_slug = f"org-{uuid.uuid4().hex[:8]}"
        org = Organization(name=f"{full_name}'s Org", slug=org_slug)
        db.add(org)
        await db.flush()

        user = User(
            organization_id=org.id,
            email=email,
            full_name=full_name,
            oauth_provider="google",
            oauth_id=userinfo.get("sub"),
            role="admin",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    access_token = create_access_token(
        subject=user.id, role=user.role, organization_id=str(user.organization_id)
    )
    refresh_token = create_refresh_token(
        subject=user.id, organization_id=str(user.organization_id)
    )

    # Record cryptographic audit log
    from app.core.audit import record_audit_log
    await record_audit_log(
        db=db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="login",
        resource_type="auth_session",
        resource_id=str(user.id),
        metadata={"email": user.email, "provider": "google"},
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "organization_id": str(user.organization_id),
        },
    )

