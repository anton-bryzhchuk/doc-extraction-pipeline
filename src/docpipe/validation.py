"""Deterministic business-rule validation.

Each rule is a named predicate over a parsed ``InvoiceExtraction``. ``validate``
returns the list of rule names that FAILED (empty list = clean). These rules are
pure and deterministic -- reliability lives here, not in the LLM.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from .config import ALLOWED_CURRENCIES, MONEY_TOLERANCE
from .schemas import InvoiceExtraction


def _close(a: Decimal, b: Decimal, tol: Decimal = MONEY_TOLERANCE) -> bool:
    return abs(a - b) <= tol


def rule_line_items_sum_matches_net(inv: InvoiceExtraction) -> bool:
    total = sum((li.line_total for li in inv.line_items), Decimal("0"))
    return _close(total, inv.net_total)


def rule_net_plus_vat_matches_gross(inv: InvoiceExtraction) -> bool:
    return _close(inv.net_total + inv.vat_amount, inv.gross_total)


def rule_vat_amount_matches_rate(inv: InvoiceExtraction) -> bool:
    return _close(inv.vat_amount, inv.net_total * inv.vat_rate)


def rule_line_totals_match_qty_price(inv: InvoiceExtraction) -> bool:
    return all(_close(li.line_total, li.quantity * li.unit_price) for li in inv.line_items)


def rule_date_not_in_future(inv: InvoiceExtraction) -> bool:
    return inv.invoice_date <= date.today()


def rule_currency_allowed(inv: InvoiceExtraction) -> bool:
    return inv.currency in ALLOWED_CURRENCIES


def rule_invoice_number_not_empty(inv: InvoiceExtraction) -> bool:
    return bool(inv.invoice_number and inv.invoice_number.strip())


def rule_has_line_items(inv: InvoiceExtraction) -> bool:
    return len(inv.line_items) > 0


RULES: list[tuple[str, Callable[[InvoiceExtraction], bool]]] = [
    ("has_line_items", rule_has_line_items),
    ("line_items_sum_matches_net", rule_line_items_sum_matches_net),
    ("line_totals_match_qty_price", rule_line_totals_match_qty_price),
    ("net_plus_vat_matches_gross", rule_net_plus_vat_matches_gross),
    ("vat_amount_matches_rate", rule_vat_amount_matches_rate),
    ("date_not_in_future", rule_date_not_in_future),
    ("currency_allowed", rule_currency_allowed),
    ("invoice_number_not_empty", rule_invoice_number_not_empty),
]


def validate(inv: InvoiceExtraction) -> list[str]:
    """Return the names of all failing rules (empty = all passed)."""
    return [name for name, fn in RULES if not fn(inv)]
