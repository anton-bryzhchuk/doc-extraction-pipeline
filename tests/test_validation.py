"""Unit tests for the deterministic business-rule validation."""
from __future__ import annotations

from datetime import date, timedelta

from conftest import valid_invoice_dict
from docpipe.schemas import InvoiceExtraction
from docpipe.validation import validate


def _inv(**overrides):
    data = valid_invoice_dict()
    data.update(overrides)
    return InvoiceExtraction.model_validate(data)


def test_clean_invoice_passes():
    assert validate(_inv()) == []


def test_line_items_sum_mismatch():
    failed = validate(_inv(net_total="99.00"))
    assert "line_items_sum_matches_net" in failed


def test_net_plus_vat_mismatch():
    failed = validate(_inv(gross_total="100.00"))
    assert "net_plus_vat_matches_gross" in failed


def test_vat_rate_mismatch():
    failed = validate(_inv(vat_amount="1.00"))
    assert "vat_amount_matches_rate" in failed


def test_line_total_qty_price_mismatch():
    items = valid_invoice_dict()["line_items"]
    items[0]["line_total"] = "999.00"
    # also break net so the sum rule is not the only one; but qty*price rule must fire
    failed = validate(_inv(line_items=items, net_total="1029.00", gross_total="1224.51",
                           vat_amount="195.51"))
    assert "line_totals_match_qty_price" in failed


def test_future_date_fails():
    future = (date.today() + timedelta(days=5)).isoformat()
    failed = validate(_inv(invoice_date=future))
    assert "date_not_in_future" in failed


def test_empty_invoice_number_fails():
    failed = validate(_inv(invoice_number="  "))
    assert "invoice_number_not_empty" in failed


def test_no_line_items_fails():
    failed = validate(_inv(line_items=[], net_total="0.00", vat_rate="0.19",
                           vat_amount="0.00", gross_total="0.00"))
    assert "has_line_items" in failed


def test_rounding_within_tolerance_passes():
    # vat_amount off by 1 cent -> within the 2-cent tolerance
    assert "vat_amount_matches_rate" not in validate(_inv(vat_amount="9.49"))
