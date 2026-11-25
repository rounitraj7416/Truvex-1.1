"""Central audit logging service."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.security import utc_now
from app.db.models import AuditLog


def record_audit_event(
    db: Session,
    *,
    actor_id: Optional[int],
    actor_role: str,
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> AuditLog:
    """Append an immutable audit log record to the current database session."""
    entry = AuditLog(
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=metadata or {},
        timestamp=utc_now(),
    )
    db.add(entry)
    return entry
