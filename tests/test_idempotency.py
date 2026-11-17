"""Idempotency: the same file content is processed only once."""
from __future__ import annotations

from sqlalchemy import func, select

from docpipe.extract import make_extractor
from docpipe.models import Document
from docpipe.pipeline import process_upload


def test_duplicate_upload_is_noop(session, sample_invoice):
    content, rec = sample_invoice
    ext = make_extractor("mock", profile="good")

    doc1, processed1 = process_upload(session, "a.pdf", content, extractor=ext)
    session.commit()
    assert processed1 is True

    doc2, processed2 = process_upload(session, "a-again.pdf", content, extractor=ext)
    session.commit()
    assert processed2 is False
    assert doc2.id == doc1.id

    count = session.scalar(select(func.count()).select_from(Document))
    assert count == 1


def test_different_content_creates_two(session, invoices):
    from docpipe.invoices import INVOICES_DIR

    ext = make_extractor("mock", profile="good")
    c0 = (INVOICES_DIR / invoices[0]["filename"]).read_bytes()
    c1 = (INVOICES_DIR / invoices[1]["filename"]).read_bytes()
    process_upload(session, "0.pdf", c0, extractor=ext)
    process_upload(session, "1.pdf", c1, extractor=ext)
    session.commit()
    assert session.scalar(select(func.count()).select_from(Document)) == 2
