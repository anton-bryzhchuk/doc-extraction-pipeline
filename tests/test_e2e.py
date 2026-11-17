"""End-to-end test over a real generated invoice."""
from __future__ import annotations

from decimal import Decimal

from docpipe.config import Status
from docpipe.extract import make_extractor
from docpipe.pipeline import process_upload


def test_end_to_end_good(session, sample_invoice):
    content, rec = sample_invoice
    doc, processed = process_upload(
        session, rec["filename"], content, extractor=make_extractor("mock", profile="good")
    )
    session.commit()

    assert processed is True
    assert doc.status == Status.AUTO_APPROVED
    assert doc.failed_rules == []
    assert doc.retry_count == 0

    ex = doc.extracted
    truth = rec["data"]
    assert ex["supplier_name"] == truth["supplier_name"]
    assert ex["invoice_number"] == truth["invoice_number"]
    assert ex["currency"] == truth["currency"]
    assert Decimal(ex["gross_total"]) == Decimal(truth["gross_total"])
    assert len(ex["line_items"]) == len(truth["line_items"])
