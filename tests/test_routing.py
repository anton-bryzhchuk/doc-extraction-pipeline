"""Unit tests for routing decisions."""
from __future__ import annotations

from docpipe.config import Status
from docpipe.routing import decide_status


def test_auto_approved_when_clean():
    assert decide_status(True, []) == Status.AUTO_APPROVED


def test_needs_review_when_rules_fail():
    assert decide_status(True, ["net_plus_vat_matches_gross"]) == Status.NEEDS_REVIEW


def test_failed_when_extraction_failed():
    assert decide_status(False, []) == Status.FAILED
    assert decide_status(False, ["anything"]) == Status.FAILED
