"""Evaluation: run the whole pipeline over the synthetic invoices and score it.

Metrics: field-level accuracy, auto-approve / review / failure rates, and the
most important one -- wrongly_auto_approved: documents auto-approved whose
extracted data does not match ground truth (a wrong value that slipped through).
"""
from __future__ import annotations

import json
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .config import MONEY_TOLERANCE, REPORTS_DIR, Status
from .db import init_db, make_engine, make_session_factory
from .extract import make_extractor
from .invoices import INVOICES_DIR, ensure_invoices, load_ground_truth
from .pipeline import process_upload

_SCALAR_STR = ("supplier_name", "invoice_number", "invoice_date", "currency")
_SCALAR_NUM = ("net_total", "vat_amount", "gross_total", "vat_rate")


def _num_eq(a, b, tol: Decimal = MONEY_TOLERANCE) -> bool:
    try:
        return abs(Decimal(str(a)) - Decimal(str(b))) <= tol
    except (InvalidOperation, TypeError, ValueError):
        return False


def _field_score(pred: dict | None, truth: dict) -> tuple[int, int]:
    """Return (correct_fields, total_fields) for one invoice."""
    total = 8 + 4 * len(truth["line_items"])
    if pred is None:
        return 0, total

    correct = 0
    for k in _SCALAR_STR:
        if str(pred.get(k, "")) == str(truth[k]):
            correct += 1
    for k in _SCALAR_NUM:
        if _num_eq(pred.get(k), truth[k]):
            correct += 1

    pin = pred.get("line_items", [])
    for i, ti in enumerate(truth["line_items"]):
        pi = pin[i] if i < len(pin) else {}
        if str(pi.get("description", "")) == ti["description"]:
            correct += 1
        for nk in ("quantity", "unit_price", "line_total"):
            if _num_eq(pi.get(nk), ti.get(nk)):
                correct += 1
    return correct, total


def _is_exact(pred: dict | None, truth: dict) -> bool:
    c, t = _field_score(pred, truth)
    return c == t


def evaluate(profile: str = "good", seed: int = 2026) -> dict:
    ensure_invoices()
    gt = load_ground_truth()
    extractor = make_extractor("mock", profile=profile, seed=seed)

    tmp = Path(tempfile.mkdtemp()) / "eval.db"
    engine = make_engine(f"sqlite:///{tmp}")
    init_db(engine)
    SessionLocal = make_session_factory(engine)

    fields_correct = 0
    fields_total = 0
    counts = {Status.AUTO_APPROVED: 0, Status.NEEDS_REVIEW: 0, Status.FAILED: 0}
    retries_sum = 0
    wrongly_auto_approved = 0
    wrong_examples: list[dict] = []
    per_doc: list[dict] = []

    with SessionLocal() as session:
        for rec in gt:
            content = (INVOICES_DIR / rec["filename"]).read_bytes()
            doc, _ = process_upload(
                session, rec["filename"], content, extractor=extractor, profile=profile
            )
            session.commit()

            truth = rec["data"]
            c, t = _field_score(doc.extracted, truth)
            fields_correct += c
            fields_total += t
            retries_sum += doc.retry_count
            counts[doc.status] = counts.get(doc.status, 0) + 1

            if doc.status == Status.AUTO_APPROVED and not _is_exact(doc.extracted, truth):
                wrongly_auto_approved += 1
                if len(wrong_examples) < 6:
                    wrong_examples.append(
                        {"filename": rec["filename"], "extracted": doc.extracted}
                    )
            per_doc.append(
                {
                    "filename": rec["filename"],
                    "status": doc.status,
                    "failed_rules": doc.failed_rules or [],
                    "retries": doc.retry_count,
                    "field_correct": c,
                    "field_total": t,
                }
            )

    engine.dispose()
    n = len(gt)
    report = {
        "profile": profile,
        "seed": seed,
        "n": n,
        "field_accuracy": round(fields_correct / fields_total, 4) if fields_total else 0.0,
        "fields_correct": fields_correct,
        "fields_total": fields_total,
        "auto_approved": counts.get(Status.AUTO_APPROVED, 0),
        "needs_review": counts.get(Status.NEEDS_REVIEW, 0),
        "failed": counts.get(Status.FAILED, 0),
        "auto_approve_rate": round(counts.get(Status.AUTO_APPROVED, 0) / n, 4),
        "review_rate": round(counts.get(Status.NEEDS_REVIEW, 0) / n, 4),
        "failure_rate": round(counts.get(Status.FAILED, 0) / n, 4),
        "mean_retries": round(retries_sum / n, 4),
        "wrongly_auto_approved": wrongly_auto_approved,
        "wrongly_auto_approved_examples": wrong_examples,
        "per_doc": per_doc,
    }
    return report


def render_markdown(report: dict) -> str:
    r = report
    lines = [
        "# Evaluation report",
        "",
        f"**Profile:** `{r['profile']}` · **Invoices:** {r['n']} · **Seed:** {r['seed']}",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Field-level accuracy | {r['field_accuracy']:.2%} ({r['fields_correct']}/{r['fields_total']}) |",
        f"| Auto-approved | {r['auto_approved']} ({r['auto_approve_rate']:.0%}) |",
        f"| Needs review | {r['needs_review']} ({r['review_rate']:.0%}) |",
        f"| Failed | {r['failed']} ({r['failure_rate']:.0%}) |",
        f"| Mean JSON retries | {r['mean_retries']} |",
        f"| **Wrongly auto-approved** | **{r['wrongly_auto_approved']}** |",
        "",
    ]
    if r["wrongly_auto_approved"]:
        lines.append("> ⚠️ Wrong values slipped through auto-approval (see JSON report).")
    else:
        lines.append("> No wrong values were auto-approved.")
    lines.append("")
    return "\n".join(lines)


def write_reports(report: dict, out_dir: Path = REPORTS_DIR) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "latest.json"
    md_path = out_dir / "latest.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
