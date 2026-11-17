"""Deterministic routing: map validation outcome to a document status."""
from __future__ import annotations

from .config import Status


def decide_status(extraction_ok: bool, failed_rules: list[str]) -> str:
    if not extraction_ok:
        return Status.FAILED
    if failed_rules:
        return Status.NEEDS_REVIEW
    return Status.AUTO_APPROVED
