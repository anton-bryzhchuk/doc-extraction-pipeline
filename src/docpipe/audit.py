"""Helper for writing append-only audit-log entries."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .models import AuditLog, Document


def record(
    session: Session,
    document: Document,
    *,
    actor: str,
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> AuditLog:
    entry = AuditLog(
        document_id=document.id,
        actor=actor,
        action=action,
        before=before,
        after=after,
    )
    session.add(entry)
    return entry
