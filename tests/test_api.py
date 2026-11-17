"""API tests using FastAPI's TestClient."""
from __future__ import annotations

from fastapi.testclient import TestClient

from docpipe.api import create_app
from docpipe.config import Status
from docpipe.invoices import INVOICES_DIR


def _upload(client, rec):
    content = (INVOICES_DIR / rec["filename"]).read_bytes()
    return client.post(
        "/documents",
        files={"file": (rec["filename"], content, "application/pdf")},
    )


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_upload_and_fetch(client, invoices):
    r = _upload(client, invoices[0])
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == Status.AUTO_APPROVED
    assert body["duplicate"] is False
    doc_id = body["id"]

    # idempotent re-upload
    r2 = _upload(client, invoices[0])
    assert r2.status_code == 200
    assert r2.json()["duplicate"] is True

    assert len(client.get("/documents").json()) == 1

    detail = client.get(f"/documents/{doc_id}").json()
    assert detail["id"] == doc_id
    assert "audit" in detail and len(detail["audit"]) >= 1


def test_get_missing_document_404(client):
    assert client.get("/documents/9999").status_code == 404


def test_empty_file_rejected(client):
    r = client.post("/documents", files={"file": ("x.pdf", b"", "application/pdf")})
    assert r.status_code == 400


def test_review_flow(engine, invoices):
    # A noisy profile routes some invoices to needs_review.
    app = create_app(engine=engine, profile="noisy")
    client = TestClient(app)

    review_rec = None
    for rec in invoices:
        body = _upload(client, rec).json()
        if body["status"] == Status.NEEDS_REVIEW:
            review_rec = (rec, body["id"])
            break
    assert review_rec is not None, "expected at least one needs_review under noisy"
    rec, doc_id = review_rec

    # review queue lists it
    listing = client.get("/review")
    assert listing.status_code == 200
    assert f"/review/{doc_id}" in listing.text

    # detail page renders
    assert client.get(f"/review/{doc_id}").status_code == 200

    # submit the correct (ground-truth) values and approve
    import json

    data = rec["data"]
    form = {
        "supplier_name": data["supplier_name"],
        "invoice_number": data["invoice_number"],
        "invoice_date": data["invoice_date"],
        "currency": data["currency"],
        "net_total": data["net_total"],
        "vat_rate": data["vat_rate"],
        "vat_amount": data["vat_amount"],
        "gross_total": data["gross_total"],
        "line_items": json.dumps(data["line_items"]),
        "decision": "approve",
    }
    r = client.post(f"/review/{doc_id}", data=form, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/review"

    detail = client.get(f"/documents/{doc_id}").json()
    assert detail["status"] == Status.APPROVED
    actions = [a["action"] for a in detail["audit"]]
    assert "approved" in actions
