"""Mock webhook notification (logged only, no network call)."""
from __future__ import annotations

from .logging_utils import get_logger, log_event
from .models import Document

_logger = get_logger("docpipe.webhook")


def notify_needs_review(document: Document) -> None:
    log_event(
        _logger,
        "webhook.needs_review (mock)",
        event="needs_review",
        document_id=document.id,
        filename=document.filename,
        failed_rules=document.failed_rules,
    )
