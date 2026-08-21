"""
FastAPI Dependency Injection Providers
Handles database sessions, JWT token decoding, authenticated user retrieval, and RBAC enforcement.
"""

import time
import typing
import uuid
from collections.abc import Callable

import redis.exceptions
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import decode_token
from app.infrastructure.database.postgres.models import User
from app.infrastructure.database.postgres.session import get_async_db

logger = get_logger("codemigration.api.deps")

get_db = get_async_db
get_async_db = get_async_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """Retrieve the currently authenticated user from JWT payload."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)

        # Prevent JWT Type Confusion: Reject refresh tokens
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type. Access token required.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except Exception:
        raise credentials_exception

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = typing.cast(User | None, result.scalar_one_or_none())

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account is deactivated",
        )
    return user


def require_roles(allowed_roles: list[str]) -> Callable:
    """RBAC Guard decorator: ensures user has one of the allowed enterprise roles."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_checker


class RateLimiter:
    """Redis-based rate limiting to prevent brute force attacks on CPU-intensive routes."""
    def __init__(self, requests: int, window: int, scope: str = "ip"):
        self.requests = requests
        self.window = window
        self.scope = scope  # "ip", "user", "org"

    async def __call__(self, request: Request) -> None:
        from app.infrastructure.database.redis.client import redis_engine

        identifier = "unknown"
        if self.scope == "ip":
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                identifier = forwarded.split(",")[0].strip()
            else:
                identifier = request.client.host if request.client else "127.0.0.1"
        else:
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                from app.core.security import decode_token
                try:
                    payload = decode_token(token)
                    if self.scope == "user":
                        identifier = payload.get("sub", "unknown")
                    elif self.scope == "org":
                        identifier = payload.get("org_id") or payload.get("organization_id") or payload.get("sub", "unknown")
                except Exception:
                    pass

        key = f"rate_limit:{self.scope}:{request.url.path}:{identifier}"

        # If Redis is unavailable, fail-open to preserve API functionality
        if not redis_engine._redis:
            return

        import redis.exceptions

        from app.core.logging import get_logger
        logger = get_logger("codemigration.api.deps")

        try:
            current = await redis_engine._redis.incr(key)
            if current == 1:
                await redis_engine._redis.expire(key, self.window)

            if current > self.requests:
                ttl = await redis_engine._redis.ttl(key)
                if ttl < 0:
                    ttl = self.window
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(ttl)}
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Redis rate limit check failed: {e}. Defaulting to allow request.")
            return

async def check_ai_rate_limit(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> None:
    """Enforces subscription-based rate limits for AI workflows."""
    from app.infrastructure.database.postgres.models import Organization

    # Get organization plan tier
    org_stmt = select(Organization).where(Organization.id == current_user.organization_id)
    org_result = await db.execute(org_stmt)
    org = org_result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=400, detail="Organization not found")

    plan_tier = org.plan_tier or "free"

    # Define limits based on plan (per 30 minutes)
    if plan_tier == "unlimited":
        return  # No rate limit for full time subscription

    limit = 10 if plan_tier == "pro" else 3
    window = 1800  # 30 minutes in seconds

    from app.infrastructure.database.redis.client import redis_engine
    if not redis_engine._redis:
        return

    current_time = int(time.time())
    key = f"rate_limit:ai_workflows:{current_user.organization_id}"

    try:
        redis_client = redis_engine._redis
        member = f"{current_time}:{uuid.uuid4().hex[:8]}"
        # Add current request with timestamp score
        await redis_client.zadd(key, {member: current_time})
        # Remove old requests outside the 30-minute window
        await redis_client.zremrangebyscore(key, 0, current_time - window)
        # Count remaining requests
        count = await redis_client.zcard(key)

        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Your plan ({plan_tier}) allows {limit} requests per 30 minutes. Upgrade your plan for higher limits.",
                headers={"Retry-After": str(window)}
            )

        # Expire key to prevent memory leak
        await redis_client.expire(key, window)
    except HTTPException:
        raise
    except Exception as e:
        from app.core.logging import get_logger
        logger = get_logger("codemigration.api.deps")
        logger.warning(f"Failed to enforce AI rate limit: {e}")

