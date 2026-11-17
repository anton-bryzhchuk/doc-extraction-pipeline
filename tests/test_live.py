"""Live tests against the real Anthropic API (skipped without a key)."""
from __future__ import annotations

import pytest

from docpipe.config import anthropic_api_key
from docpipe.invoices import INVOICES_DIR, ensure_invoices, load_ground_truth
from docpipe.pdf import extract_text
from docpipe.pipeline import extract_with_retries

pytestmark = pytest.mark.live

_NO_KEY = anthropic_api_key() is None


@pytest.mark.skipif(_NO_KEY, reason="ANTHROPIC_API_KEY not set; live suite skipped")
def test_live_extraction_schema_valid():
    from docpipe.extract import make_extractor

    ensure_invoices()
    rec = load_ground_truth()[0]
    text = extract_text((INVOICES_DIR / rec["filename"]).read_bytes())
    inv, retries, err = extract_with_retries(make_extractor("anthropic"), text)
    assert inv is not None, f"live extraction did not validate: {err}"
    assert inv.currency in {"EUR", "USD", "UAH", "GBP"}
    assert len(inv.line_items) >= 1
