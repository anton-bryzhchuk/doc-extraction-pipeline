"""Pydantic contract for extracted invoice data."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import ALLOWED_CURRENCIES

CurrencyT = Literal["EUR", "USD", "UAH", "GBP"]
assert set(ALLOWED_CURRENCIES) == set(CurrencyT.__args__)  # keep in sync


class LineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str = Field(min_length=1)
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class InvoiceExtraction(BaseModel):
    """The structured result the extractor is contracted to return."""

    model_config = ConfigDict(extra="ignore")

    supplier_name: str = Field(min_length=1)
    invoice_number: str
    invoice_date: date
    currency: CurrencyT
    line_items: list[LineItem]
    net_total: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    gross_total: Decimal
