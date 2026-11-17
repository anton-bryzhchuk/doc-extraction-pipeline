"""SQLAlchemy ORM models: Document and an append-only AuditLog."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), index=True)
    profile: Mapped[str] = mapped_column(String(32), default="good")
    correlation_id: Mapped[str] = mapped_column(String(36))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    extracted: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    failed_rules: Mapped[list[str]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    audit_entries: Mapped[list[AuditLog]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="AuditLog.id"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sha256": self.sha256,
            "filename": self.filename,
            "status": self.status,
            "profile": self.profile,
            "correlation_id": self.correlation_id,
            "retry_count": self.retry_count,
            "extracted": self.extracted,
            "failed_rules": self.failed_rules or [],
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AuditLog(Base):
    """Append-only record of every state change (who, what, when, before/after)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    document: Mapped[Document] = relationship(back_populates="audit_entries")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "actor": self.actor,
            "action": self.action,
            "before": self.before,
            "after": self.after,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
