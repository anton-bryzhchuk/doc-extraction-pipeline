"""The audit log records every state change (append-only)."""
from __future__ import annotations

from sqlalchemy import select

from docpipe.config import Status
from docpipe.extract import make_extractor
from docpipe.models import AuditLog
from docpipe.pipeline import process_upload
from docpipe.review import apply_review


def _audit(session, doc_id):
    return session.scalars(
        select(AuditLog).where(AuditLog.document_id == doc_id).order_by(AuditLog.id)
    ).all()


def test_ingest_writes_audit(session, sample_invoice):
    content, rec = sample_invoice
    doc, _ = process_upload(session, "a.pdf", content, extractor=make_extractor("mock"))
    session.commit()
    entries = _audit(session, doc.id)
    assert len(entries) == 1
    assert entries[0].actor == "system"
    assert entries[0].action == "ingested"
    assert entries[0].before is None
    assert entries[0].after["status"] == doc.status


def test_review_appends_audit(session, sample_invoice):
    content, rec = sample_invoice
    doc, _ = process_upload(session, "a.pdf", content, extractor=make_extractor("mock"))
    session.commit()

    ok, failed = apply_review(session, doc, rec["data"], "approve")
    session.commit()
    assert ok and failed == []
    assert doc.status == Status.APPROVED

    entries = _audit(session, doc.id)
    assert len(entries) == 2  # append-only: ingest + approve
    assert entries[1].actor == "reviewer"
    assert entries[1].action == "approved"
    assert entries[1].before["status"] == Status.AUTO_APPROVED
    assert entries[1].after["status"] == Status.APPROVED


def test_review_approve_blocked_when_still_invalid(session, sample_invoice):
    content, rec = sample_invoice
    doc, _ = process_upload(session, "a.pdf", content, extractor=make_extractor("mock"))
    session.commit()

    broken = dict(rec["data"])
    broken["gross_total"] = "1.00"  # breaks net+vat=gross
    ok, failed = apply_review(session, doc, broken, "approve")
    session.commit()
    assert ok is False
    assert "net_plus_vat_matches_gross" in failed
    assert doc.status == Status.NEEDS_REVIEW
