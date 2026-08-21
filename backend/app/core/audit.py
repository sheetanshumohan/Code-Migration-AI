"""
Cryptographic Audit Logging Service
Records immutable, SHA-256 integrity-verified audit log entries for all organizational activities.
"""

import hashlib
import json
import uuid
from typing import Any

from starlette.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.infrastructure.database.postgres.models import AuditLog

logger = get_logger("codemigration.audit")


def compute_integrity_hash(
    org_id: str,
    user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str,
    metadata: dict[str, Any],
) -> str:
    """Generate deterministic SHA-256 checksum over the audit record attributes."""
    serialized_meta = json.dumps(metadata, sort_keys=True, default=str)
    raw = f"{org_id}:{user_id or 'anon'}:{action}:{resource_type}:{resource_id}:{serialized_meta}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def record_audit_log(
    db: AsyncSession,
    organization_id: uuid.UUID | str,
    action: str,
    resource_type: str,
    resource_id: str,
    user_id: uuid.UUID | str | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """
    Persist an immutable cryptographic audit record.
    Gracefully catches and logs errors so audit logging never crashes business flows.
    """
    meta = metadata or {}
    
    org_uuid = uuid.UUID(str(organization_id)) if not isinstance(organization_id, uuid.UUID) else organization_id
    user_uuid = (
        uuid.UUID(str(user_id))
        if user_id and not isinstance(user_id, uuid.UUID)
        else user_id
    )

    client_ip = ip_address
    client_ua = user_agent

    if request:
        if not client_ip:
            client_ip = request.client.host if request.client else "127.0.0.1"
        if not client_ua:
            client_ua = request.headers.get("user-agent", "WebClient")

    integrity_hash = compute_integrity_hash(
        org_id=str(org_uuid),
        user_id=str(user_uuid) if user_uuid else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata=meta,
    )

    log_entry = AuditLog(
        organization_id=org_uuid,
        user_id=user_uuid,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        log_metadata=meta,
        ip_address=client_ip or "127.0.0.1",
        user_agent=client_ua or "WebClient",
        integrity_hash=integrity_hash,
    )
    
    try:
        db.add(log_entry)
        await db.commit()
        await db.refresh(log_entry)
        logger.info(
            "Audit event recorded",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            org_id=str(org_uuid),
            hash=integrity_hash[:16],
        )
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
        try:
            await db.rollback()
        except Exception:
            pass

    return log_entry
