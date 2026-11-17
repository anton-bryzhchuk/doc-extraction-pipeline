"""Unit tests for JSON parsing + schema-retry logic."""
from __future__ import annotations

import json

from conftest import valid_invoice_dict
from docpipe.extract.base import Extractor
from docpipe.pipeline import extract_json, extract_with_retries

_VALID = json.dumps(valid_invoice_dict())


class Scripted(Extractor):
    name = "scripted"

    def __init__(self, texts):
        self.texts = texts
        self.calls = 0

    def extract(self, text, *, attempt=0):
        self.calls += 1
        return self.texts[min(attempt, len(self.texts) - 1)]


def test_extract_json_direct():
    assert extract_json(_VALID)["currency"] == "EUR"


def test_extract_json_from_prose():
    assert extract_json(f"Here you go:\n{_VALID}\nThanks")["currency"] == "EUR"


def test_extract_json_garbage():
    assert extract_json("not json") is None
    assert extract_json("{broken json") is None


def test_valid_on_first_attempt():
    inv, retries, err = extract_with_retries(Scripted([_VALID]), "t")
    assert inv is not None and retries == 0 and err is None


def test_recovers_after_retries():
    ext = Scripted(["{bad", "still bad", _VALID])
    inv, retries, err = extract_with_retries(ext, "t", max_retries=2)
    assert inv is not None
    assert retries == 2
    assert ext.calls == 3


def test_gives_up_after_max_retries():
    ext = Scripted(["{bad", "{bad", "{bad", _VALID])
    inv, retries, err = extract_with_retries(ext, "t", max_retries=2)
    assert inv is None
    assert retries == 2
    assert ext.calls == 3
    assert err is not None


def test_schema_invalid_currency_rejected():
    bad = valid_invoice_dict()
    bad["currency"] = "JPY"  # not allowed
    inv, retries, err = extract_with_retries(Scripted([json.dumps(bad)]), "t", max_retries=0)
    assert inv is None
    assert "schema invalid" in err
