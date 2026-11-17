"""Unit tests for the mock extractor and factory."""
from __future__ import annotations

import pytest

from docpipe.extract import PROFILES, make_extractor
from docpipe.extract.mock import MockExtractor
from docpipe.invoices import INVOICES_DIR
from docpipe.pdf import extract_text
from docpipe.pipeline import extract_json


def _texts(invoices, k=30):
    return [extract_text((INVOICES_DIR / r["filename"]).read_bytes()) for r in invoices[:k]]


def test_factory_unknown_raises():
    with pytest.raises(ValueError):
        make_extractor("nope")


def test_unknown_profile_raises():
    with pytest.raises(ValueError):
        MockExtractor(profile="banana")


def test_profiles_constant():
    assert set(PROFILES) == {"good", "noisy", "hallucinating", "malformed"}


def test_good_is_deterministic(invoices):
    text = _texts(invoices, 1)[0]
    a, b = MockExtractor("good"), MockExtractor("good")
    assert a.extract(text) == b.extract(text)


def test_noisy_differs_somewhere(invoices):
    good, noisy = MockExtractor("good"), MockExtractor("noisy")
    diffs = sum(1 for t in _texts(invoices) if good.extract(t) != noisy.extract(t))
    assert diffs > 0


def test_malformed_produces_invalid_json(invoices):
    ext = MockExtractor("malformed")
    invalid = sum(1 for t in _texts(invoices) if extract_json(ext.extract(t)) is None)
    assert invalid > 0


def test_hallucinating_changes_gross(invoices):
    good, hal = MockExtractor("good"), MockExtractor("hallucinating")
    changed = 0
    for t in _texts(invoices):
        g = extract_json(good.extract(t))
        h = extract_json(hal.extract(t))
        if g and h and g["gross_total"] != h["gross_total"]:
            changed += 1
    assert changed > 0
