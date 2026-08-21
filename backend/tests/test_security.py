"""
Unit Tests for Enterprise Security Module
Verifies Argon2id password hashing, JWT token lifecycle, and Fernet AES-256 secret encryption.
"""

from app.core.security import (
    create_access_token,
    decode_token,
    decrypt_secret,
    encrypt_secret,
    get_password_hash,
    verify_password,
)


def test_password_hashing_and_verification():
    """Verify Argon2id password hashing correctness and negative verification."""
    password = "SuperSecurePassword#2026!"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False


def test_jwt_token_generation_and_payload_decoding():
    """Verify JWT access and refresh token generation, expiration claims, and decoding."""
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    role = "admin"
    org_id = "660e8400-e29b-41d4-a716-446655440000"

    access_token = create_access_token(subject=user_id, role=role, organization_id=org_id)
    payload = decode_token(access_token)

    assert payload["sub"] == user_id
    assert payload["role"] == role
    assert payload["org_id"] == org_id
    assert payload["type"] == "access"


def test_fernet_secret_encryption_and_decryption():
    """Verify AES-256 Fernet secret encryption round-trip."""
    raw_github_token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    encrypted = encrypt_secret(raw_github_token)

    assert encrypted != raw_github_token
    decrypted = decrypt_secret(encrypted)
    assert decrypted == raw_github_token
