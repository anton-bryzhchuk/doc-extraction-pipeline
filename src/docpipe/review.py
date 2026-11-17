"""Human-review actions: apply edits, re-validate, approve or reject."""
from __future__ import annotations

from sqlalchemy.orm import Session

from . import audit
from .config import Status
from .models import Document
from .schemas import InvoiceExtraction
from .validation import validate


def apply_review(
    session: Session,
    doc: Document,
    edited: dict,
    decision: str,
    *,
    actor: str = "reviewer",
) -> tuple[bool, list[str]]:
    """Apply reviewer edits and a decision. Returns (ok, failed_rules).

    Edited data is always re-validated. 'approve' only succeeds when no rule
    fails; otherwise the document stays in needs_review. 'reject' always moves
    the document to rejected.
    """
    if decision not in ("approve", "reject"):
        raise ValueError("decision must be 'approve' or 'reject'")

    before = doc.to_dict()
    inv = InvoiceExtraction.model_validate(edited)  # raises on bad schema
    failed = validate(inv)
    doc.extracted = inv.model_dump(mode="json")
    doc.failed_rules = failed

    if decision == "reject":
        doc.status = Status.REJECTED
        action = "rejected"
        ok = True
    elif failed:
        doc.status = Status.NEEDS_REVIEW
        action = "approve_blocked_revalidation_failed"
        ok = False
    else:
        doc.status = Status.APPROVED
        action = "approved"
        ok = True

    audit.record(session, doc, actor=actor, action=action, before=before, after=doc.to_dict())
    session.flush()
    return ok, failed
