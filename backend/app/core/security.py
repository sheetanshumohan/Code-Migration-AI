"""
Core Security Module for Code Migration AI
Argon2id password hashing, JWT token handling, and AES-256 Fernet encryption.
"""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet
from jwt.exceptions import InvalidTokenError

from app.core.config import settings

# Native Argon2id password hashing context with secure parameters
ph = PasswordHasher(
    memory_cost=65536,
    time_cost=3,
    parallelism=4,
)


def _get_encryption_key() -> bytes:
    """Derive a 32-byte URL-safe base64 Fernet key from SECRET_KEY."""
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(secret_text: str) -> str:
    """Encrypt sensitive strings (e.g. GitHub/GitLab access tokens) using AES-256."""
    if not secret_text:
        return ""
    fernet = Fernet(_get_encryption_key())
    return fernet.encrypt(secret_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted_text: str) -> str:
    """Decrypt an encrypted secret string."""
    if not encrypted_text:
        return ""
    fernet = Fernet(_get_encryption_key())
    return fernet.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against an Argon2id hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using Argon2id."""
    return ph.hash(password)


def create_access_token(
    subject: str | Any,
    role: str = "developer",
    organization_id: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
        "org_id": str(organization_id) if organization_id else None,
        "type": "access",
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: str | Any,
    organization_id: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT refresh token."""
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "org_id": str(organization_id) if organization_id else None,
        "type": "refresh",
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except InvalidTokenError as e:
        raise ValueError(f"Invalid or expired token: {str(e)}") from e
