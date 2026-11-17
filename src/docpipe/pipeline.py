"""The ingestion pipeline: hash -> extract(+retry) -> validate -> route -> persist.

Deterministic everywhere except the extraction call itself. Idempotent on file
content (SHA-256). Every state change is written to the audit log.
"""
from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .config import MAX_RETRIES, Status
from .extract.base import Extractor
from .logging_utils import get_logger, log_event, set_correlation_id
from .models import Document
from .pdf import extract_text, sha256_hex
from .routing import decide_status
from .schemas import InvoiceExtraction
from .validation import validate
from .webhook import notify_needs_review

_logger = get_logger("docpipe.pipeline")


def extract_json(text: str) -> dict | None:
    """Parse a JSON object from raw extractor text (tolerates surrounding prose)."""
    text = text.strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def extract_with_retries(
    extractor: Extractor, text: str, *, max_retries: int = MAX_RETRIES
) -> tuple[InvoiceExtraction | None, int, str | None]:
    """Return (extraction, retries_used, error). retries_used is the attempt index."""
    last_error: str | None = None
    for attempt in range(max_retries + 1):
        raw = extractor.extract(text, attempt=attempt)
        obj = extract_json(raw)
        if obj is None:
            last_error = "unparseable: no JSON object found"
            continue
        try:
            inv = InvoiceExtraction.model_validate(obj)
        except Exception as exc:
            last_error = f"schema invalid: {exc.__class__.__name__}"
            continue
        return inv, attempt, None
    return None, max_retries, last_error


def get_by_hash(session: Session, digest: str) -> Document | None:
    return session.scalar(select(Document).where(Document.sha256 == digest))


def process_upload(
    session: Session,
    filename: str,
    content: bytes,
    *,
    extractor: Extractor,
    profile: str = "good",
) -> tuple[Document, bool]:
    """Process an uploaded PDF. Returns (document, processed).

    ``processed`` is False when the file was already seen (idempotent no-op).
    """
    digest = sha256_hex(content)
    existing = get_by_hash(session, digest)
    if existing is not None:
        log_event(_logger, "upload.duplicate", document_id=existing.id, sha256=digest)
        return existing, False

    correlation_id = str(uuid4())
    set_correlation_id(correlation_id)

    doc = Document(
        sha256=digest,
        filename=filename,
        status=Status.PROCESSING,
        profile=profile,
        correlation_id=correlation_id,
        failed_rules=[],
    )
    session.add(doc)
    session.flush()  # assign id

    log_event(_logger, "pipeline.start", document_id=doc.id, filename=filename, profile=profile)
    text = extract_text(content)
    inv, retries, error = extract_with_retries(extractor, text)

    doc.retry_count = retries
    if inv is None:
        doc.status = Status.FAILED
        doc.error = error
        doc.extracted = None
        doc.failed_rules = []
    else:
        failed = validate(inv)
        doc.extracted = inv.model_dump(mode="json")
        doc.failed_rules = failed
        doc.status = decide_status(True, failed)

    audit.record(
        session, doc, actor="system", action="ingested", before=None, after=doc.to_dict()
    )
    session.flush()

    log_event(
        _logger,
        "pipeline.done",
        document_id=doc.id,
        status=doc.status,
        retries=doc.retry_count,
        failed_rules=doc.failed_rules,
    )
    if doc.status == Status.NEEDS_REVIEW:
        notify_needs_review(doc)

    return doc, True
